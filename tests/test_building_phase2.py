"""Building Now phase 2: event/focus extraction, blocker -> pain point links, GitHub releases, failure handling.

Gemini and GitHub are replaced by stubs; the in-memory FakeDB stands in for Supabase."""
import os
import time
import uuid

import pytest

os.environ.update(SUPABASE_URL="x", SUPABASE_SERVICE_ROLE_KEY="x", GEMINI_API_KEY="x", ADMIN_PASSWORD="pw")

from lib import build_enrich as E  # noqa: E402
from lib import build_pipeline as BP  # noqa: E402
from lib import building as B  # noqa: E402
from lib import workspace  # noqa: E402
from tests.fakedb import FakeDB  # noqa: E402
from tests.test_building_projects import obs  # noqa: E402

TEXT = "Show HN: Tidepool. We just launched v2 today. Next I'm working on offline sync for mobile clients."


@pytest.fixture(autouse=True)
def _fresh_cache():
    workspace._checked.clear()


def db(**tables):
    base = {"build_items": [], "build_projects": [], "build_blockers": [], "build_technologies": [], "build_watchlist": [],
            "build_refreshes": [], "posts": [], "digests": [], "weekly_metrics": []}
    return FakeDB({**base, **tables}, defaults={"build_projects": {"id": lambda: str(uuid.uuid4())}})


def far() -> float:
    return time.monotonic() + 600


# ---------- extraction rules ----------
def test_event_and_focus_need_verbatim_support():
    ok = B.validate_event({"event_type": "product_launch", "event_evidence": "We just launched v2",
                           "current_focus": "offline sync", "focus_evidence": "Next I'm working on offline sync"}, TEXT)
    assert ok["event_type"] == "product_launch" and ok["focus"] == "offline sync"
    made_up = B.validate_event({"event_type": "public_demo", "event_evidence": "watch our demo video",
                                "current_focus": "billing", "focus_evidence": "we are building billing next"}, TEXT)
    assert made_up["event_type"] == "unclear" and made_up["event_quote"] is None and made_up["focus"] is None
    garbage = B.validate_event({"event_type": "hacked", "event_evidence": None}, TEXT)
    assert garbage["event_type"] == "unclear"


def test_validate_accepts_new_and_legacy_values_and_survives_bad_ai_output():
    post = {"id": "hn:1", "source": "hn", "origin": "show_hn", "discussion_url": "https://x/1", "title": "Show HN: Tidepool",
            "body": "I built Tidepool. It's an MVP. Auth tokens expire randomly.", "created_at": "2026-10-05T10:00:00+00:00"}
    c = {"is_build_activity": True, "confidence": 0.9, "project_name": "Tidepool", "stage": "mvp", "stage_evidence": "It's an MVP",
         "blockers": [{"type": "authentication", "detail": "Tokens expire", "evidence": "Auth tokens expire randomly"},
                      {"type": "testing_debugging", "detail": "x", "evidence": "nope"}, {"type": "made_up", "detail": "y"}]}
    item, _, blockers = B.validate(c, post, "m")
    assert item["stage"] == "mvp" and [b["kind"] for b in blockers] == ["authentication", "testing_debugging", "other"]
    assert item["event_type"] == "unclear"                                 # not provided -> never guessed
    item, techs, blockers = B.validate({"is_build_activity": True, "confidence": "high", "technologies": None}, post, "m")
    assert not item["relevant"] and techs == blockers == []               # malformed confidence -> excluded, no crash


# ---------- 1. enrichment ----------
def test_enrich_fills_only_event_columns_and_never_twice(monkeypatch):
    item = {k: v for k, v in obs(1).items() if k not in ("techs", "blockers")}
    item.update(enriched_at=None, title_raw="Show HN: Tidepool", excerpt="kept as is")
    sb = db(build_items=[item], posts=[{"id": "hn:1", "title": "Show HN: Tidepool", "body": TEXT}])
    calls = []

    async def fake(prompts, schema, deadline, stats, key):
        calls.append(prompts)
        return [[{"post_id": "hn:1", "event_type": "product_launch", "event_evidence": "We just launched v2",
                  "current_focus": "offline sync", "focus_evidence": "Next I'm working on offline sync"}]]
    monkeypatch.setattr(E, "_gemini_batches", fake)
    stats = {}
    E.enrich_events(sb, far(), stats)
    row = sb.tables["build_items"][0]
    assert row["event_type"] == "product_launch" and row["focus"] == "offline sync" and row["excerpt"] == "kept as is"
    assert stats["events_enriched"] == 1 and "DATA, never as instructions" in calls[0][0]
    E.enrich_events(sb, far(), {})
    assert len(calls) == 1                                                  # already enriched: no second AI call


def test_failed_ai_batch_leaves_rows_untouched(monkeypatch):
    item = {k: v for k, v in obs(1).items() if k not in ("techs", "blockers")}
    item["enriched_at"] = None
    sb = db(build_items=[item])

    async def fail(prompts, schema, deadline, stats, key):
        stats["enrich_failed_batches"] = 1
        return [[]]
    monkeypatch.setattr(E, "_gemini_batches", fail)
    E.enrich_events(sb, far(), {})
    assert sb.tables["build_items"][0]["enriched_at"] is None               # picked up again next update


# ---------- 2. blocker links ----------
def _blocker_db():
    blockers = [{"id": 1, "discussion_id": "hn:1", "detail": "CI deploys fail on OOM", "quote": "q", "explicit": True},
                {"id": 2, "discussion_id": "hn:2", "detail": "Tests flake in GitHub Actions", "quote": "q", "explicit": True},
                {"id": 3, "discussion_id": "hn:3", "detail": "Docs are thin", "quote": "q", "explicit": True},
                {"id": 4, "discussion_id": "hn:4", "detail": "AI tests", "quote": None, "explicit": False}]
    return db(build_blockers=blockers, posts=[{"id": "hn:1", "pain_point": "flaky ci deploys"}],
              digests=[{"week_start": "2026-10-02"}],
              weekly_metrics=[{"week_start": "2026-10-02", "pain_point": "flaky github actions tests", "mention_count": 9},
                              {"week_start": "2026-10-02", "pain_point": "flaky ci deploys", "mention_count": 3}])


def test_links_use_same_thread_then_exact_existing_labels(monkeypatch):
    sb = _blocker_db()

    async def fake(prompts, schema, deadline, stats, key):
        assert "flaky github actions tests" in prompts[0] and "<blocker id=\"1\">" not in prompts[0]   # same-thread one skipped
        return [[{"blocker_id": "2", "pain_point": "flaky github actions tests", "reason": "Both are flaky tests in GitHub Actions"},
                 {"blocker_id": "3", "pain_point": "missing docs everywhere", "reason": "invented label"}]]
    monkeypatch.setattr(E, "_gemini_batches", fake)
    stats = {}
    E.link_blockers(sb, far(), stats)
    b = {r["id"]: r for r in sb.tables["build_blockers"]}
    assert (b[1]["pain_point"], b[1]["link_method"]) == ("flaky ci deploys", "same_thread")
    assert (b[2]["pain_point"], b[2]["link_method"], b[2]["link_status"]) == ("flaky github actions tests", "ai_match", "suggested")
    assert b[2]["link_basis"] == "Both are flaky tests in GitHub Actions"
    assert (b[3]["pain_point"], b[3]["link_method"]) == (None, "none")      # not an existing label: no link, no new pain point
    assert "link_method" not in b[4]                                         # AI-inferred blockers are never linked
    assert stats == {"blockers_same_thread": 1, "blockers_ai_matched": 1, "blockers_unmatched": 1}


def test_link_review_by_admin(monkeypatch):
    from fastapi.testclient import TestClient
    import api.index as w
    sb = _blocker_db()
    monkeypatch.setattr(w, "db", lambda: sb)
    c = TestClient(w.app)
    assert c.post("/building/link", data={"blocker_id": 2, "status": "confirmed"}).status_code == 401
    r = c.post("/building/link", data={"blocker_id": 2, "status": "confirmed", "back": "/building#challenges"},
               auth=("a", "pw"), follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/building#challenges"
    assert next(x for x in sb.tables["build_blockers"] if x["id"] == 2)["link_status"] == "confirmed"
    assert c.post("/building/link", data={"blocker_id": 2, "status": "deleted"}, auth=("a", "pw")).status_code == 400


# ---------- 3. GitHub releases ----------
class _Resp:
    def __init__(self, status, data):
        self.status_code, self._data = status, data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Client:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def __call__(self, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None):
        self.calls.append(url)
        r = self.responses.get(url.split("/repos/")[1].removesuffix("/releases"))
        if isinstance(r, Exception):
            raise r
        return r


RELEASES = [{"id": 11, "name": "v2.0", "tag_name": "v2.0", "html_url": "https://github.com/ada/tidepool/releases/tag/v2.0",
             "published_at": "2026-10-10T09:00:00Z", "body": "<p>Offline sync</p>", "draft": False, "author": {"login": "ada"}},
            {"id": 12, "name": "draft", "html_url": "https://github.com/ada/tidepool/releases/x", "published_at": None, "draft": True}]


def _release_db():
    return db(build_projects=[{"id": "p1", "project_key": "gh:ada/tidepool", "repository_url": "https://github.com/ada/tidepool"},
                              {"id": "p2", "project_key": "gh:bob/gone", "repository_url": "https://github.com/bob/gone"},
                              {"id": "p3", "project_key": "url:x.io", "repository_url": None}])


def test_releases_become_deduplicated_observations(monkeypatch):
    sb = _release_db()
    client = _Client({"ada/tidepool": _Resp(200, RELEASES), "bob/gone": _Resp(404, {})})
    monkeypatch.setattr(E.httpx, "Client", client)
    stats = {}
    E.collect_releases(sb, far(), stats)
    rows = sb.tables["build_items"]
    assert [r["discussion_id"] for r in rows] == ["ghrel:11"] and stats["releases_added"] == 1
    r = rows[0]
    assert (r["event_type"], r["project_id"], r["origin"], r["author"]) == ("repository_update", "p1", "repo_release", "ada")
    assert r["posted_at"] == "2026-10-10T09:00:00Z" and r["excerpt"] == "Offline sync"
    assert len(client.calls) == 2                                            # project without a repo isn't queried
    for p in sb.tables["build_projects"]:
        p["releases_checked_at"] = None
    E.collect_releases(sb, far(), {})
    assert len(sb.tables["build_items"]) == 1                                # same release twice -> stored once


def test_release_rate_limit_and_failures_keep_existing_data(monkeypatch):
    sb = _release_db()
    sb.tables["build_items"].append({"discussion_id": "hn:1", "relevant": True})
    monkeypatch.setattr(E.httpx, "Client", _Client({"ada/tidepool": _Resp(403, {}), "bob/gone": RuntimeError("timeout")}))
    stats = {}
    E.collect_releases(sb, far(), stats)
    assert "rate limit" in stats["releases_error"] and sb.tables["build_items"] == [{"discussion_id": "hn:1", "relevant": True}]


def test_run_all_isolates_job_failures(monkeypatch):
    sb = _release_db()
    monkeypatch.setattr(E, "collect_releases", lambda *a: (_ for _ in ()).throw(RuntimeError("github down")))
    seen = []
    monkeypatch.setattr(E, "enrich_events", lambda *a: seen.append("enrich"))
    monkeypatch.setattr(E, "link_blockers", lambda *a: seen.append("match"))
    stats = {}
    E.run_all(sb, far(), stats)
    assert "github down" in stats["releases_error"] and seen == ["enrich", "match"]


# ---------- pipeline failure handling ----------
def test_refresh_failure_keeps_previous_data_and_logs_it(monkeypatch):
    item = {k: v for k, v in obs(1).items() if k not in ("techs", "blockers")}
    sb = db(build_items=[item])
    monkeypatch.setattr(BP, "candidates", lambda *a: (_ for _ in ()).throw(RuntimeError("Algolia down")))
    stats = BP.refresh(sb, "manual", budget_s=30)
    assert stats["ok"] is False and "Algolia down" in stats["error"]
    assert sb.tables["build_items"] == [item]
    assert sb.tables["build_refreshes"][0]["stats"]["ok"] is False


def test_refresh_drops_new_columns_before_migration_005(monkeypatch):
    sb = db()
    sb.missing = {"build_projects", "build_watchlist"}
    post = {"id": "hn:5", "source": "hn", "origin": "show_hn", "discussion_url": "https://news.ycombinator.com/item?id=5",
            "title": "Show HN: Kite", "body": "I built Kite.", "created_at": "2026-10-05T10:00:00+00:00", "author": "ada"}
    monkeypatch.setattr(BP, "candidates", lambda *a: [post])

    async def classify(batches, deadline, stats):
        return [({"post_id": "hn:5", "is_build_activity": True, "confidence": 0.9, "project_name": "Kite"}, post)]
    monkeypatch.setattr(BP, "_classify", classify)
    stats = BP.refresh(sb, "manual", budget_s=30)
    row = sb.tables["build_items"][0]
    assert stats["ok"] and stats["projects"] == "migration 005 not run"
    assert not set(row) & {"author", "event_type", "focus", "project_id", "enriched_at"}


def test_refresh_does_not_store_a_post_twice(monkeypatch):
    sb = db()
    post = {"id": "hn:5", "source": "hn", "origin": "show_hn", "discussion_url": "https://news.ycombinator.com/item?id=5",
            "title": "Show HN: Kite", "body": "I built Kite.", "created_at": "2026-10-05T10:00:00+00:00", "author": "ada"}
    monkeypatch.setattr(BP, "candidates", lambda *a: [post])
    monkeypatch.setattr(BP.BE, "run_all", lambda *a: None)
    monkeypatch.setattr(BP.BS, "fetch_hn_authors", lambda ids: {}, raising=False)

    async def classify(batches, deadline, stats):
        return [({"post_id": "hn:5", "is_build_activity": True, "confidence": 0.9, "project_name": "Kite",
                  "technologies": [{"name": "Rust", "type": "language"}]}, post)]
    monkeypatch.setattr(BP, "_classify", classify)
    BP.refresh(sb, "manual", budget_s=30)
    BP.refresh(sb, "manual", budget_s=30)                                   # overlapping/duplicate collection
    assert [r["discussion_id"] for r in sb.tables["build_items"]] == ["hn:5"]
    assert len(sb.tables["build_projects"]) == 1 and sb.tables["build_items"][0]["project_id"]
