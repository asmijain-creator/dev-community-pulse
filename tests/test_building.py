"""Tests for Building Now: AI output validation, filters, counts, weekly trends, pain point links, routes.

Run with:  python -m pytest -q
No network, database or Gemini access is needed.
"""
import os
from datetime import date, timedelta

import pytest

os.environ.update(SUPABASE_URL="x", SUPABASE_SERVICE_ROLE_KEY="x", GEMINI_API_KEY="x", ADMIN_PASSWORD="pw")

from lib import building as B  # noqa: E402

TODAY = date(2026, 10, 13)   # a Tuesday; current week started Fri 9 Oct


def post(**kw):
    return {"id": "hn:1", "source": "hn", "origin": "show_hn", "discussion_url": "https://news.ycombinator.com/item?id=1",
            "title": "Show HN: Tidepool – a Postgres-backed job queue in Rust",
            "body": "I built Tidepool over the summer. It's in beta. Deploying to Fly.io kept failing with OOM errors.",
            "created_at": "2026-10-05T10:00:00+00:00", "score": 50, "comments": 10, **kw}


def ai(**kw):
    return {"post_id": "hn:1", "is_build_activity": True, "exclusion_reason": "", "activity_type": "open_source",
            "project_name": "Tidepool", "descriptive_title": "Postgres job queue", "summary": "A job queue.",
            "category": "Developer tools", "stage": "alpha_beta", "stage_evidence": "It's in beta",
            "technologies": [{"name": "Postgres", "type": "database"}, {"name": "Rust", "type": "language"},
                             {"name": "Redis", "type": "database"}],
            "blockers": [{"type": "deployment", "detail": "Deploys fail with out-of-memory errors",
                          "evidence": "Deploying to Fly.io kept failing with OOM errors"},
                         {"type": "performance", "detail": "Slow under load", "evidence": "it is slow under heavy load"}],
            "excerpt": "I built Tidepool over the summer.", "confidence": 0.9, **kw}


# ---------- validation of Gemini output ----------
def test_validate_keeps_only_what_the_post_supports():
    item, techs, blockers = B.validate(ai(), post(), "m")
    assert item["relevant"] and item["project_title"] == "Tidepool" and not item["title_is_ai"]
    assert item["stage"] == "alpha_beta" and item["excerpt"] == "I built Tidepool over the summer."
    explicit = {t["name"]: t["explicit"] for t in techs}
    assert explicit == {"Postgres": True, "Rust": True, "Redis": False}       # Redis isn't in the post: inferred
    assert [b["explicit"] for b in blockers] == [True, False]                   # second quote isn't verbatim


def test_unnamed_project_gets_labelled_ai_title_and_unsupported_stage_is_dropped():
    item, _, _ = B.validate(ai(project_name="Seastar", stage="launched", stage_evidence="now live for everyone",
                               excerpt="A thing that was never written"), post(), "m")
    assert item["title_is_ai"] and item["project_title"] == "Postgres job queue"
    assert item["stage"] is None and item["stage_quote"] is None
    assert item["excerpt"] is None


@pytest.mark.parametrize("kw,reason", [
    ({"is_build_activity": False}, "not_build"),
    ({"exclusion_reason": "advertisement"}, "advertisement"),
    ({"confidence": 0.2}, "low_confidence"),
])
def test_exclusions_are_kept_with_reason_and_no_details(kw, reason):
    item, techs, blockers = B.validate(ai(**kw), post(), "m")
    assert not item["relevant"] and item["exclusion_reason"] == reason and techs == blockers == []
    assert "title_is_ai" in item and item["title_is_ai"] is False                 # NOT NULL column always set


def test_build_hint_prefilter():
    assert B.looks_like_build("I built a CLI to diff Terraform plans", "")
    assert B.looks_like_build("Ask", "we're building an internal code review bot")
    assert not B.looks_like_build("How do I fix flaky GitHub Actions caches?", "Tests fail randomly")


def test_tech_key_and_mentions():
    assert B.tech_key("Next.js") == B.tech_key("NextJS") == "nextjs"
    assert B.mentioned("Next.js", "built with nextjs and supabase")
    assert not B.mentioned("Go", "we gone with Rust")


# ---------- weeks, filters, counts, trends ----------
def item(i, day, cat="Developer tools", techs=(), blockers=(), source="hn", **kw):
    return {"discussion_id": f"hn:{i}", "source": source, "posted_at": f"{day}T12:00:00+00:00", "category": cat,
            "project_title": f"Project {i}", "title_raw": "", "summary": "", "discussion_url": f"https://x/{i}",
            "techs": [{"name": t, "key": B.tech_key(t), "explicit": True} for t in techs],
            "blockers": [{"kind": k, "detail": d, "quote": d, "explicit": True} for k, d in blockers], **kw}


def test_complete_weeks_exclude_current_partial_week():
    weeks = B.complete_weeks(TODAY, 4)
    assert weeks[-1] == date(2026, 10, 2) and weeks[0] == date(2026, 9, 11)
    assert all(w.weekday() == 4 for w in weeks)


def test_filters():
    items = [item(1, "2026-10-12", techs=["Rust"]), item(2, "2026-09-01", cat="Web apps"),
             item(3, "2026-10-10", source="github", blockers=[("deployment", "deploy fails")])]
    assert [i["discussion_id"] for i in B.apply_filters(items, {"days": 7}, TODAY)] == ["hn:1", "hn:3"]
    assert [i["discussion_id"] for i in B.apply_filters(items, {"tech": "rust"}, TODAY)] == ["hn:1"]
    assert [i["discussion_id"] for i in B.apply_filters(items, {"blocker": "deployment", "source": "github"}, TODAY)] == ["hn:3"]
    assert [i["discussion_id"] for i in B.apply_filters(items, {"q": "deploy"}, TODAY)] == ["hn:3"]


def test_counts_use_only_explicit_technologies():
    it = item(1, "2026-10-12", techs=["Rust"])
    it["techs"].append({"name": "Redis", "key": "redis", "explicit": False})
    assert [c["label"] for c in B.top_counts([it], "tech")] == ["Rust"]


def _week(n, i0, day, techs):
    return [item(i0 + k, day, techs=techs) for k in range(n)]


def test_trends_growing_new_declining_over_complete_weeks():
    days = ["2026-09-12", "2026-09-19", "2026-09-26", "2026-10-03"]          # one day inside each complete week
    items = []
    for i, d in enumerate(days):
        items += _week(1, 100 * i, d, ["Rust"])                               # Rust: 1,1,1,then grows below
        items += _week(4 if i < 3 else 1, 100 * i + 10, d, ["Django"])        # Django: 4,4,4,1 -> declining
    items += _week(4, 900, days[-1], ["Rust"])                                # Rust latest week: 5
    items += _week(3, 950, days[-1], ["Bun"])                                 # Bun: only latest week -> new
    items += _week(5, 980, "2026-10-12", ["Zig"])                             # current partial week: ignored
    t = B.trends(items, TODAY, "tech")
    status = {r["label"]: r["status"] for r in t["rows"]}
    assert status == {"Rust": "growing", "Django": "declining", "Bun": "new"}
    assert t["history_ok"] and "Zig" not in status


def test_trends_need_history():
    t = B.trends(_week(3, 1, "2026-10-03", ["Rust"]), TODAY, "tech")
    assert not t["history_ok"] and t["rows"][0]["status"] == "pending"


# ---------- connections to pain points ----------
def test_blocker_matches_pain_point_with_two_shared_words():
    b = {"detail": "flaky tests in GitHub Actions", "quote": None}
    assert B.match_pain_point(b, ["flaky ci tests in github actions", "slow docker builds"])[0] == "flaky ci tests in github actions"
    assert B.match_pain_point({"detail": "docker", "quote": None}, ["slow docker builds"]) is None


def test_builds_for_pain_point_reasons():
    same = item(1, "2026-10-12", pain_point="slow docker builds")
    by_blocker = item(2, "2026-10-12", blockers=[("performance", "docker builds are slow")])
    by_tech = item(3, "2026-10-12", techs=["Docker"])
    unrelated = item(4, "2026-10-12", techs=["Rust"])
    rows = B.builds_for_pain_point("slow docker builds", [same, by_blocker, by_tech, unrelated])
    assert [(r["item"]["discussion_id"], r["suggested"]) for r in rows] == [("hn:1", False), ("hn:2", True), ("hn:3", True)]


def test_pain_points_for_tech_counts_threads_mentioning_it():
    threads = [{"title": "Supabase auth breaks", "body": "", "pain_point": "auth issues"},
               {"title": "x", "body": "using supabase edge", "pain_point": "auth issues"},
               {"title": "unrelated", "body": "", "pain_point": "other"}]
    rows = B.pain_points_for_tech("Supabase", threads)
    assert rows[0]["pain_point"] == "auth issues" and len(rows[0]["threads"]) == 2 and len(rows) == 1


# ---------- routes ----------
class _Q:
    def __init__(self, data, fail=False):
        self.data, self.fail = data, fail

    def __getattr__(self, n):
        return lambda *a, **k: self

    @property
    def not_(self):
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError("relation does not exist")
        return self


@pytest.fixture
def app(monkeypatch):
    from fastapi.testclient import TestClient
    import api.index as w
    from lib import workspace
    workspace._checked.clear()
    return w, TestClient(w.app)


def test_building_page_explains_missing_migration(app, monkeypatch):
    w, c = app

    class DB:
        def table(self, t):
            return _Q([], fail=t.startswith("build_"))
    monkeypatch.setattr(w, "db", lambda: DB())
    r = c.get("/building")
    assert r.status_code == 200 and "003_building_now.sql" in r.text and 'href="/building" class="on"' in r.text


def test_building_page_renders_real_rows_and_filters(app, monkeypatch):
    w, c = app
    rows = [item(1, "2026-10-12", techs=["Rust"], blockers=[("deployment", "deploys fail on Fly")]),
            item(2, "2026-10-11", cat="Web apps", techs=["Next.js"])]
    for r in rows:
        r.update(relevant=True, in_posts=False, title_is_ai=True, excerpt=None, confidence=0.8, activity_type="tool",
                 classified_at="2026-10-12T00:00:00+00:00")
    data = {"items": rows, "classified": 5, "excluded": {"not_build": 3}, "refreshes": []}

    class DB:
        def table(self, t):
            return _Q([])
    monkeypatch.setattr(w, "db", lambda: DB())
    monkeypatch.setattr(w.BP, "load", lambda sb, days=100: {**data, "items": [dict(r) for r in rows]})
    real = B.complete_weeks
    monkeypatch.setattr(w.BLD, "complete_weeks", lambda today, n=4: real(TODAY, n))
    r = c.get("/building?days=0")
    assert r.status_code == 200
    assert "Project 1" in r.text and "Project 2" in r.text and "AI-generated title" in r.text
    assert "https://x/1" in r.text and "Deployment failures" in r.text
    r = c.get("/building?days=0&tech=rust&category=Bogus")
    assert "Project 1" in r.text and "Project 2" not in r.text


def test_refresh_is_skipped_while_a_run_is_going(app, monkeypatch):
    w, c = app

    class DB:
        def table(self, t):
            return _Q([])
    monkeypatch.setattr(w, "db", lambda: DB())
    monkeypatch.setattr(w.W, "run_in_progress", lambda sb: True)
    monkeypatch.setattr(w.BP, "refresh", lambda *a, **k: pytest.fail("must not run"))
    r = c.post("/building/refresh", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/building?updated=busy"
