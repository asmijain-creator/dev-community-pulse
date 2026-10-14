"""Tests for the Share feature: snapshots, copy summary, links, privacy, revocation, expiry, permissions.

Run with:  python -m pytest -q
Uses an in-memory database (tests/fakedb.py); no network or Gemini access.
"""
import base64
import os
import re
from datetime import datetime, timedelta, timezone

import pytest

os.environ.update(SUPABASE_URL="x", SUPABASE_SERVICE_ROLE_KEY="service-secret", GEMINI_API_KEY="x", ADMIN_PASSWORD="pw")

from fastapi.testclient import TestClient  # noqa: E402

from lib import sharing as SH, workspace  # noqa: E402
from tests.fakedb import FakeDB  # noqa: E402

AUTH = {"Authorization": "Basic " + base64.b64encode(b"u:pw").decode()}
HTML = {"Accept": "text/html"}
PP, PP2 = "fatigue from reviewing ai generated code", "flaky ci tests in github actions"
NOW = datetime.now(timezone.utc).isoformat()


def tables(**over):
    t = {
        "digests": [{"week_start": "2026-10-02", "content_md": "## Summary\nOld week.", "created_at": "2026-10-03T03:00:00+00:00"},
                    {"week_start": "2026-10-09", "content_md": "## Summary\nAI review fatigue grew. [x](javascript:alert(1))",
                     "created_at": "2026-10-10T03:00:00+00:00"}],
        "weekly_metrics": [
            {"week_start": "2026-10-02", "pain_point": PP, "category": "Code Review", "mention_count": 1, "unresolved_count": 1, "engagement": 5},
            {"week_start": "2026-10-09", "pain_point": PP, "category": "Code Review", "mention_count": 3, "unresolved_count": 2, "engagement": 40},
            {"week_start": "2026-10-09", "pain_point": PP2, "category": "CI/CD", "mention_count": 1, "unresolved_count": 0, "engagement": 2},
        ],
        "posts": [
            {"id": "hn:1", "source": "hn", "title": "Ask HN: Reviewing AI PRs is exhausting", "url": "https://news.ycombinator.com/item?id=1",
             "score": 90, "comments": 40, "created_at": "2026-10-09T10:00:00+00:00", "is_unresolved": True, "sentiment": "negative",
             "category": "Code Review", "pain_point": PP, "week_start": "2026-10-09"},
            {"id": "gh:2", "source": "gh", "title": "Bot floods PRs with comments", "url": "https://github.com/x/y/issues/2",
             "score": 4, "comments": 3, "created_at": "2026-10-10T10:00:00+00:00", "is_unresolved": True, "sentiment": "negative",
             "category": "Code Review", "pain_point": PP, "week_start": "2026-10-09"},
            {"id": "gh:3", "source": "gh", "title": "Bad link thread", "url": "javascript:alert(1)",
             "score": 1, "comments": 0, "created_at": "2026-10-11T10:00:00+00:00", "is_unresolved": False, "sentiment": "neutral",
             "category": "Code Review", "pain_point": PP, "week_start": "2026-10-09"},
        ],
        "topics": [], "opportunities": [{"pain_point": PP, "status": "Investigating", "notes": "SECRET-NOTE do not share"}],
        "opportunity_insights": [], "radar_state": [], "shared_reports": [],
    }
    t.update(over)
    return t


@pytest.fixture
def env(monkeypatch):
    import api.index as w
    fake = FakeDB(tables(), missing={"build_items", "runs"},
                  defaults={"shared_reports": {"created_at": lambda: datetime.now(timezone.utc).isoformat(), "revoked_at": None,
                                               "last_accessed_at": None, "expires_at": None}})
    monkeypatch.setattr(w, "db", lambda: fake)
    workspace._checked.clear()
    return fake, TestClient(w.app)


def create(c, **data):
    data = {"kind": "pain_point", "name": PP, "visibility": "unlisted", "expires": "30", **data}
    r = c.post("/share/create", data=data, headers={**AUTH, **HTML}, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]
    rid = int(re.search(r"/reports/(\d+)", r.headers["location"]).group(1))
    page = c.get(r.headers["location"], headers={**AUTH, **HTML})
    link = re.search(r'value="(http[^"]+/r/[A-Za-z0-9_-]{43})"', page.text).group(1)
    return rid, "/r/" + link.rsplit("/r/", 1)[1], page


# ---------- share one pain point ----------
def test_share_pain_point_creates_snapshot_link(env):
    fake, c = env
    rid, path, page = create(c)
    assert "Report created" in page.text and "Copy link" in page.text
    r = c.get(path, headers=HTML)                                   # no credentials: like a logged-out browser
    assert r.status_code == 200
    t = r.text
    assert "Fatigue from reviewing AI generated code" in t and "https://news.ycombinator.com/item?id=1" in t
    assert "javascript:" not in t                                  # unsafe source link dropped
    assert "SECRET-NOTE" not in t and "Investigating" not in t     # private notes and internal status never shared
    markup = re.sub(r"<style>.*?</style>", "", t, flags=re.S)      # shared CSS mentions dashboard parts in comments
    assert "<form" not in markup and "/run-now" not in markup and 'id="devi' not in markup.lower()   # read-only page
    assert 'class="topnav"' not in markup and "/reports" not in markup
    assert r.headers["cache-control"].startswith("no-store") and "noindex" in r.headers["x-robots-tag"]
    row = fake.tables["shared_reports"][0]
    token = path.rsplit("/", 1)[1]
    assert token not in str(row) and row["token_hash"] == SH.token_hash(token)   # only the hash is stored


def test_snapshot_does_not_change_when_data_changes(env):
    fake, c = env
    _, path, _ = create(c)
    fake.tables["posts"][0]["title"] = "Renamed later"
    assert "Ask HN: Reviewing AI PRs is exhausting" in c.get(path, headers=HTML).text


def test_share_opportunity_separates_evidence_from_ai(env):
    fake, c = env
    fake.tables["opportunity_insights"] = [{"pain_point": PP, "week_start": "2026-10-09", "created_at": NOW, "content": {
        "problem_statement": "Reviewers drown in AI PRs.", "segment": [{"text": "Senior reviewers", "evidence": [{"title": "t", "url": "https://news.ycombinator.com/item?id=1"}]}],
        "existing_solutions": [], "limitations": [], "unmet_needs": [{"text": "Uncited need", "evidence": []}],
        "experiments": ["Risk-based PR triage"], "interview_questions": ["How many AI PRs per week?"]}}]
    _, path, _ = create(c, kind="opportunity")
    t = c.get(path, headers=HTML).text
    assert "Priority score" in t and "not validated demand" in t and "How the score is calculated" in t
    assert "AI-generated hypotheses" in t and "Risk-based PR triage" in t and "Senior reviewers" in t
    assert "Uncited need" not in t                                  # AI claims without a source are dropped
    assert "Risks and assumptions" in t and "SECRET-NOTE" not in t


def test_copy_summary_text(env):
    _, c = env
    r = c.get("/api/share/summary", params={"kind": "pain_point", "name": PP})
    assert r.status_code == 200
    text = r.json()["text"]
    assert text.startswith("*Fatigue from reviewing AI generated code*") and "Why it matters" in text
    assert "https://news.ycombinator.com/item?id=1" in text and "Trend:" in text
    assert c.get("/api/share/summary", params={"kind": "pain_point", "name": "nope"}).status_code == 404


def test_summary_with_link_after_creation(env):
    _, c = env
    rid, path, page = create(c)
    assert "Full report: http" in page.text and path in page.text


# ---------- combined report ----------
def test_combined_report_keeps_order_and_reports_missing(env):
    _, c = env
    prev = c.get("/reports/new", params={"pp": [PP2, "made up"], "op": [PP]}, headers={**AUTH, **HTML})
    assert prev.status_code == 200 and "Report preview" in prev.text and "Made up" in prev.text
    data = {"kind": "combined", "title": "Q4 <b>review</b>", "intro": "Why we care.\x07", "item": [f"op:{PP}", f"pp:{PP2}"],
            "trends": "1", "visibility": "unlisted", "expires": "7"}
    r = c.post("/share/create", data=data, headers={**AUTH, **HTML}, follow_redirects=False)
    rid = int(r.headers["location"].split("/")[2].split("?")[0])
    page = c.get(f"/reports/{rid}", headers={**AUTH, **HTML}).text
    path = "/r/" + re.search(r"/r/([A-Za-z0-9_-]{43})", page).group(1)
    t = c.get(path, headers=HTML).text
    assert "Q4 &lt;b&gt;review&lt;/b&gt;" in t and "\x07" not in t           # title stays plain text
    assert t.index("Product opportunities") < t.index("Key pain points")       # owner's order is kept
    assert "Emerging trends" in t


def test_combined_needs_at_least_one_real_item(env):
    _, c = env
    r = c.post("/share/create", data={"kind": "combined", "item": ["pp:made up"], "visibility": "unlisted", "expires": "7"},
               headers={**AUTH, **HTML})
    assert r.status_code == 400


def test_weekly_report_share(env):
    _, c = env
    _, path, _ = create(c, kind="weekly", name="2026-10-09")
    t = c.get(path, headers=HTML).text
    assert "Developer intelligence report · week of 2026-10-09" in t and "Top pain points" in t
    assert 'href="javascript' not in t


# ---------- permissions, privacy, revocation, expiry ----------
@pytest.mark.parametrize("method,path", [("post", "/share/create"), ("get", "/reports"), ("get", "/reports/new"),
                                         ("post", "/reports/1001/revoke"), ("post", "/reports/1001/update")])
def test_owner_actions_need_no_sign_in(env, method, path):
    _, c = env
    r = getattr(c, method)(path, data={"kind": "pain_point", "name": PP} if method == "post" else None) if method == "post" else c.get(path)
    assert r.status_code != 401 and "www-authenticate" not in r.headers


def test_private_report_opens_without_password(env):
    _, c = env
    _, path, _ = create(c, visibility="private")
    assert c.get(path, headers=HTML).status_code == 200


def test_revoked_link_stops_working(env):
    _, c = env
    rid, path, _ = create(c)
    assert c.post(f"/reports/{rid}/revoke", headers={**AUTH, **HTML}, follow_redirects=False).status_code == 303
    r = c.get(path, headers=HTML)
    assert r.status_code == 410 and "no longer shared" in r.text and "Fatigue" not in r.text
    assert c.post(f"/reports/{rid}/update", data={"visibility": "unlisted"}, headers={**AUTH, **HTML}).status_code == 409


def test_expired_link_stops_working(env):
    fake, c = env
    rid, path, _ = create(c)
    fake.tables["shared_reports"][0]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    r = c.get(path, headers=HTML)
    assert r.status_code == 410 and "expired" in r.text
    c.post(f"/reports/{rid}/update", data={"visibility": "unlisted", "expires": "never"}, headers={**AUTH, **HTML})
    assert c.get(path, headers=HTML).status_code == 200            # the owner can extend it again


def test_invalid_and_guessed_tokens(env):
    _, c = env
    create(c)
    assert c.get("/r/short", headers=HTML).status_code == 404
    assert c.get("/r/" + "A" * 43, headers=HTML).status_code == 404


def test_recipients_cannot_edit(env):
    _, c = env
    _, path, _ = create(c)
    assert c.post(path, data={"title": "hacked"}).status_code == 405


def test_missing_sources_do_not_break_reports(env):
    fake, c = env
    fake.tables["posts"] = []
    _, path, _ = create(c)
    t = c.get(path, headers=HTML).text
    assert "No source links are stored" in t and "Observed" in t and "Unavailable" in t


def test_without_migration_sharing_explains_itself(env):
    fake, c = env
    fake.missing.add("shared_reports")
    workspace._checked.clear()
    r = c.post("/share/create", data={"kind": "pain_point", "name": PP}, headers={**AUTH, **HTML})
    assert r.status_code == 503 and "004_shared_reports.sql" in r.text
    assert c.get("/r/" + "A" * 43, headers=HTML).status_code == 404
    assert c.get("/share/print", params={"kind": "pain_point", "name": PP}).status_code == 200   # export still works


def test_expiry_parsing():
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    assert SH.expiry("never", now) is None and SH.expiry("7", now) == now + timedelta(days=7)
    assert SH.expiry("2026-10-20", now) == datetime(2026, 10, 21, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        SH.expiry("2026-01-01", now)
    with pytest.raises(ValueError):
        SH.expiry("soon", now)


def test_links_are_stable_and_unguessable():
    nonce, tok, th = SH.new_link()
    assert SH.token_for(nonce) == tok and SH.valid_token(tok) and len(tok) == 43
    assert SH.new_link()[1] != tok


def test_existing_pages_still_render_with_share_buttons(env):
    _, c = env
    for path in ["/", "/pain-points", f"/pain-point?name={PP}", "/opportunities", f"/opportunity?name={PP}"]:
        r = c.get(path, headers=HTML)
        assert r.status_code == 200, path
        assert 'data-share-kind=' in r.text and 'id="shbox"' in r.text, path
    assert c.get("/radar", headers=HTML).status_code == 200 and c.get("/building", headers=HTML).status_code == 200
