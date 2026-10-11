"""End-to-end pipeline tests with an in-memory store and fake sources/AI (no network, no keys)."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from pulse.config import Settings
from pulse.models import Post
from pulse.pipeline import ConfigError, run_digest

NOW = datetime(2026, 10, 9, 3, 0, tzinfo=timezone.utc)


def settings(**overrides) -> Settings:
    base = dict(supabase_url="x", supabase_service_key="x", gemini_api_key="x", gemini_model="m",
                resend_api_key="r", digest_email_to="sumit@example.com", digest_email_from="f",
                cron_secret="c", admin_password="p", github_token="", stackexchange_key="",
                app_url="", lookback_days=7, max_posts_per_query=15, max_classify_per_run=240,
                classify_batch_size=30)
    return Settings(**{**base, **overrides})


class FakeStore:
    def __init__(self, topics=None, busy=False):
        self.topics = topics if topics is not None else [
            {"id": 1, "category": "CI/CD", "description": "", "keywords": ["flaky tests"],
             "created_at": "2026-01-01T00:00:00+00:00"}]
        self.busy, self.posts, self.runs, self.digests, self.metrics = busy, {}, [], {}, {}

    def start_run(self, trigger):
        if self.busy:
            return None
        self.runs.append({"id": len(self.runs) + 1, "trigger": trigger, "status": "running"})
        return len(self.runs)

    def finish_run(self, run_id, status, stats, error=None):
        self.runs[run_id - 1].update(status=status, stats=stats, error=error)

    def active_topics(self):
        return self.topics

    def upsert_posts(self, rows):
        for r in rows:
            self.posts.setdefault(r["id"], {}).update(r)

    def unclassified_posts(self, since, limit):
        rows = [p for p in self.posts.values()
                if not p.get("classified_at") and datetime.fromisoformat(p["created_at"]) >= since]
        return rows[:limit]

    def save_labels(self, labels, errors):
        for pid, fields in labels.items():
            self.posts[pid].update(fields, classified_at="now")
        for pid, msg in errors.items():
            self.posts[pid]["classify_error"] = msg

    def known_labels(self, since):
        return sorted({p["pain_point"] for p in self.posts.values() if p.get("pain_point")})

    def pain_point_trends(self, cur_start, end):  # mirrors the SQL function
        prev_start = cur_start - (end - cur_start)
        out = {}
        for p in self.posts.values():
            created = datetime.fromisoformat(p["created_at"])
            if not p.get("relevant") or not p.get("pain_point") or not (prev_start <= created < end):
                continue
            row = out.setdefault((p["category"], p["pain_point"]), {
                "category": p["category"], "pain_point": p["pain_point"],
                "mentions": 0, "prev_mentions": 0, "engagement": 0, "unresolved": 0})
            if created >= cur_start:
                row["mentions"] += 1
                row["engagement"] += p["score"] + p["comments"]
                row["unresolved"] += bool(p.get("is_unresolved"))
            else:
                row["prev_mentions"] += 1
        return list(out.values())

    def examples(self, start, end, pain_points, per_point=3):
        return {pp: [] for pp in pain_points}

    def save_digest(self, period_start, period_end, content_md, stats, metrics):
        self.digests[period_end] = content_md
        self.metrics[period_end] = metrics


def make_posts(n_current, n_previous, title="Flaky tests block merges"):
    posts = {}
    for i in range(n_current + n_previous):
        age = timedelta(days=2) if i < n_current else timedelta(days=9)
        p = Post("github", str(i), f"{title} {i}", "body", f"https://x/{i}", 1, 1, NOW - age)
        posts[p.id] = p
    return posts


def fakes(posts, source_status=None, email_error=None):
    calls = {"classified": 0, "emails": 0}

    async def collect(keywords, since, s):
        return posts, source_status or {"github": {"ok": True, "queries": 1, "posts": len(posts), "errors": []}}

    async def classify(api_key, model, pending, topics, known, batch_size=30):
        calls["classified"] += len(pending)
        return {p["id"]: {"relevant": True, "category": "CI/CD", "pain_point": "flaky tests",
                          "sentiment": "negative", "is_unresolved": True, "summary": "s"} for p in pending}, {}

    async def write(api_key, model, start, end, metrics, examples, total, status):
        return f"brief with {total} posts"

    def send(*args):
        calls["emails"] += 1
        if email_error:
            raise RuntimeError(email_error)
        return "email-1"

    return dict(collect=collect, classify=classify, write=write, send=send), calls


def run(store, fns, **kw):
    return asyncio.run(run_digest("test", store=store, settings=kw.pop("settings", settings()), now=NOW, **fns, **kw))


def test_happy_path_first_run_has_week_over_week_trend():
    store = FakeStore()
    fns, calls = fakes(make_posts(n_current=6, n_previous=2))
    result = run(store, fns)
    assert result["status"] == "success"
    metric = store.metrics[NOW.date()][0]
    assert (metric["mentions"], metric["prev_mentions"], metric["trend"]) == (6, 2, "rising")
    assert calls["emails"] == 1 and store.runs[0]["status"] == "success"


def test_second_run_does_not_reclassify_or_double_count():
    store = FakeStore()
    fns, calls = fakes(make_posts(4, 0))
    run(store, fns)
    run(store, fns)  # same day, same posts (e.g. Run now after cron)
    assert calls["classified"] == 4
    assert store.metrics[NOW.date()][0]["mentions"] == 4
    assert len(store.digests) == 1


def test_concurrent_run_is_skipped():
    fns, _ = fakes(make_posts(1, 0))
    assert run(FakeStore(busy=True), fns)["status"] == "skipped"


def test_no_active_topics():
    store = FakeStore(topics=[])
    fns, _ = fakes({})
    assert run(store, fns)["reason"] == "no active topics"
    assert store.runs[0]["status"] == "skipped"


def test_email_failure_still_saves_brief():
    store = FakeStore()
    fns, _ = fakes(make_posts(2, 0), email_error="domain not verified")
    result = run(store, fns)
    assert result["status"] == "success" and result["email"].startswith("failed")
    assert NOW.date() in store.digests


def test_missing_config_is_a_clear_error():
    fns, _ = fakes({})
    with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
        run(FakeStore(), fns, settings=settings(gemini_api_key=""))


def test_classifier_crash_marks_run_failed():
    store = FakeStore()
    fns, _ = fakes(make_posts(2, 0))

    async def broken(*a, **k):
        raise RuntimeError("gemini down")

    fns["classify"] = broken
    with pytest.raises(RuntimeError):
        run(store, fns)
    assert store.runs[0]["status"] == "failed" and "gemini down" in store.runs[0]["error"]
