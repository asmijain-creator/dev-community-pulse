"""Tests for the intelligence layer: evidence, radar, scoring, link guard, permissions, run protection.

Run with:  python -m pytest -q
No network, database or Gemini access is needed.
"""
import base64
import os

import pytest

os.environ.update(SUPABASE_URL="x", SUPABASE_SERVICE_ROLE_KEY="x", GEMINI_API_KEY="x", ADMIN_PASSWORD="pw")

from lib import devi, radar, scoring, workspace  # noqa: E402
from lib.evidence import evidence_level, group_labels, opinion_mix, unique_threads  # noqa: E402


def post(title, url=None, source="hackernews", score=1, comments=0, **kw):
    return {"title": title, "url": url or f"https://x/{abs(hash(title))}", "source": source,
            "score": score, "comments": comments, **kw}


# ---------- evidence ----------
def test_near_duplicates_count_once():
    posts = [post("CI pipeline fails on flaky integration tests", score=10),
             post("CI pipeline fails on flaky integration tests again"),           # near-duplicate title
             post("Totally different question about merge queues"),
             post("Repost", url="https://x/same"), post("Repost of same link", url="https://x/same/")]
    uniq = unique_threads(posts)
    assert len(uniq) == 3
    top = next(u for u in uniq if "flaky" in u["title"])
    assert top["duplicates"] == 1 and top["score"] == 10        # the most-engaged copy is kept


def test_group_labels_merges_same_theme_only():
    canon = group_labels(["fatigue from reviewing ai generated code", "ai generated code review fatigue",
                          "flaky benchmark runs in ci"])
    assert canon["ai generated code review fatigue"] == "fatigue from reviewing ai generated code"
    assert canon["flaky benchmark runs in ci"] == "flaky benchmark runs in ci"


@pytest.mark.parametrize("n,s,level", [(1, 1, "Thin"), (3, 1, "Moderate"), (5, 1, "Moderate"), (5, 2, "Strong")])
def test_evidence_levels(n, s, level):
    assert evidence_level(n, s)["level"] == level


def test_opinion_mix():
    assert opinion_mix([{"sentiment": "positive"}, {"sentiment": "negative"}])["mixed"] is True
    assert opinion_mix([{"sentiment": "negative"}, {"sentiment": None}])["mixed"] is False


# ---------- radar ----------
WEEKS = ["2026-09-11", "2026-09-18", "2026-09-25", "2026-10-02", "2026-10-09"]


def m(week, label, n, u=0):
    return {"week_start": week, "pain_point": label, "category": "CI/CD", "mention_count": n, "unresolved_count": u}


_WORDS = ["kubernetes deploy rollback", "pytest fixture timeout", "monorepo cache misses", "docker layer bloat",
          "terraform drift alerts", "eslint config conflicts", "gradle daemon crashes", "webpack chunk splitting"]


def threads(label, n, source="hackernews"):
    """n genuinely different threads (distinct titles) tagged with the same pain point."""
    return [post(f"Question about {_WORDS[i]}", pain_point=label, source=source) for i in range(n)]


def test_radar_needs_baseline_with_one_week():
    res = radar.find_signals(WEEKS[-1:], [m(WEEKS[-1], "a b c", 3)], threads("a b c", 3))
    assert not res["history_ok"]
    assert [f["kind"] for f in res["findings"]] == ["baseline_pending"]


def test_radar_new_rising_and_quiet():
    metrics = [m(WEEKS[-1], "brand new problem here", 3),
               *[m(w, "steady old problem", 2) for w in WEEKS],
               *[m(w, "rising pipeline problem", 1) for w in WEEKS[:-1]], m(WEEKS[-1], "rising pipeline problem", 4)]
    posts = threads("brand new problem here", 3) + threads("steady old problem", 2) + threads("rising pipeline problem", 4)
    kinds = {f["label"]: f["kind"] for f in radar.find_signals(WEEKS, metrics, posts)["findings"]}
    assert kinds == {"brand new problem here": "new", "rising pipeline problem": "rising"}   # steady one not flagged


def test_radar_ignores_single_thread_and_duplicates():
    metrics = [m(WEEKS[-1], "lonely issue words", 3)]
    copies = [post("Exactly the same complaint about builds", pain_point="lonely issue words") for _ in range(3)]
    assert radar.find_signals(WEEKS, metrics, copies)["findings"] == []          # 3 copies = 1 independent thread


def test_radar_keeps_dismissed_state():
    res = radar.find_signals(WEEKS[-1:], [m(WEEKS[-1], "a b c", 2)], threads("a b c", 2),
                             {"a-b-c": {"status": "dismissed"}})
    assert res["findings"][0]["status"] == "dismissed"


# ---------- scoring ----------
def test_score_skips_growth_without_baseline_and_respects_weights():
    ps = threads("x y z", 4) + [post("other", sentiment="negative", is_unresolved=True)]
    f = scoring.factors(4, 4, None, ps)
    assert f["growth"] is None and f["frequency"] == 1.0
    w = scoring.parse_weights({"w_frequency": "3", "w_severity": "0", "w_growth": "99", "w_unresolved": "bad"})
    assert w["frequency"] == 3 and w["severity"] == 0 and w["growth"] == 3 and w["unresolved"] == 1
    s = scoring.score(f, w)
    assert 0 <= s <= 100


def test_score_all_zero_weights_is_none():
    f = scoring.factors(1, 2, 1.0, threads("a b c", 1))
    assert scoring.score(f, {k: 0 for k in scoring.FACTORS}) is None


# ---------- Ask DevvIT link guard ----------
def test_guard_links_removes_unknown_urls():
    ans = "See [real](https://news.ycombinator.com/item?id=1) and [fake](https://example.com/made-up)."
    out, kept, removed = devi.guard_links(ans, {"https://news.ycombinator.com/item?id=1"})
    assert (kept, removed) == (1, 1)
    assert "example.com" not in out and "link removed" in out


def test_relevance_ranking():
    posts = [post("Flaky tests in GitHub Actions"), post("Docker image size"), post("GitHub Actions cache misses")]
    top = devi.rank_relevant("why are github actions tests flaky?", posts)
    assert top[0]["title"] == "Flaky tests in GitHub Actions" and len(top) == 2


# ---------- permissions and migration fallback ----------
@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    import api.index as w

    class Q:
        def __getattr__(self, n):
            return lambda *a, **k: self

        @property
        def not_(self):
            return self

        def execute(self):
            raise RuntimeError("relation does not exist")      # simulates tables from migration 002 missing

    class DB:
        def table(self, t):
            return Q()

    monkeypatch.setattr(w, "db", lambda: DB())
    workspace._checked.clear()
    return TestClient(w.app)


AUTH = {"Authorization": "Basic " + base64.b64encode(b"u:pw").decode()}


@pytest.mark.parametrize("path,data", [
    ("/radar/action", {"key": "k", "label": "l", "action": "dismissed"}),
    ("/opportunity/save", {"name": "n", "status": "New"}),
    ("/opportunity/analyze", {"name": "n"}),
])
def test_writes_need_admin_password(client, path, data):
    r = client.post(path, data=data, follow_redirects=False)
    assert r.status_code == 401 and "Basic" in r.headers.get("www-authenticate", "")


@pytest.mark.parametrize("path,data", [
    ("/radar/action", {"key": "k", "label": "l", "action": "dismissed"}),
    ("/opportunity/save", {"name": "n", "status": "New"}),
])
def test_writes_explain_missing_migration(client, path, data):
    r = client.post(path, data=data, headers=AUTH, follow_redirects=False)
    assert r.status_code == 303 and "msg=migrate" in r.headers["location"]


def test_second_run_is_skipped_while_one_is_running(monkeypatch):
    import api.index as w
    monkeypatch.setattr(w, "db", lambda: object())
    monkeypatch.setattr(w.W, "run_in_progress", lambda sb: True)
    called = []
    monkeypatch.setattr(w, "_pipeline", lambda *a: called.append(1) or {"ok": True})
    assert w._do_run(7)["skipped"] is True and not called


def test_short_tech_terms_count_for_relevance():
    posts = [post("Our CI/CD pipeline breaks on every PR"), post("Docker image size")]
    assert [p["title"] for p in devi.rank_relevant("CI/CD integration problems", posts)] == ["Our CI/CD pipeline breaks on every PR"]


def test_run_now_needs_no_sign_in(monkeypatch):
    from fastapi.testclient import TestClient
    import api.index as w
    monkeypatch.setattr(w, "_do_run", lambda **k: {"skipped": True})
    r = TestClient(w.app).post("/run-now", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/?run=busy"
