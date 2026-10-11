from fastapi.testclient import TestClient

from api.index import app
from pulse import config


def client(monkeypatch, **env):
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY", "CRON_SECRET", "ADMIN_PASSWORD"):
        monkeypatch.setenv(key, env.get(key, ""))
    config.get_settings.cache_clear()
    return TestClient(app)


def test_cron_requires_secret(monkeypatch):
    c = client(monkeypatch, CRON_SECRET="s3cret")
    assert c.get("/api/run-digest").status_code == 401
    assert c.get("/api/run-digest", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_cron_refuses_when_secret_unset(monkeypatch):
    c = client(monkeypatch)
    assert c.get("/api/run-digest", headers={"Authorization": "Bearer "}).status_code == 401


def test_admin_pages_need_password(monkeypatch):
    c = client(monkeypatch, ADMIN_PASSWORD="pw")
    assert c.get("/topics").status_code == 401
    assert c.post("/run", auth=("sumit", "nope")).status_code == 401


def test_admin_disabled_without_password(monkeypatch):
    assert client(monkeypatch).get("/topics", auth=("a", "b")).status_code == 403


def test_health_reports_missing_config(monkeypatch):
    body = client(monkeypatch).get("/api/health").json()
    assert body["ok"] is False and "GEMINI_API_KEY" in body["missing"]


BRIEF_MD = """# Developer Community Pulse
**Week 2026-10-02 → 2026-10-09** · 12 relevant discussions

⚠️ **github** was unavailable this week, so its discussions are missing.

## TL;DR
- [Flaky tests](https://github.com/x) are up.

## Top pain points
1. **flaky tests**: 6

## Unresolved and underserved
- Nobody has a fix for flaky retries.

## Objections to watch
- "AI reviews are noisy."

## Suggested actions for sprint planning
1. Ship **retry hints**.
2. Interview 3 teams.
3. Brief sales.

## The numbers

| a | b |
|---|---|
| 1 | 2 |"""


class PageStore:
    def __init__(self, digest=True):
        self.digest = {"period_start": "2026-10-02", "period_end": "2026-10-09", "created_at": "2026-10-09T03:01:00",
                       "content_md": BRIEF_MD,
                       "stats": {"relevant_this_week": 12, "posts_collected": 80, "email": "sent",
                                 "source_status": {"hackernews": {"ok": True, "posts": 30, "errors": []},
                                                   "github": {"ok": False, "posts": 0, "errors": ["x"]}}}} if digest else None
    metric = {"pain_point": "flaky tests", "category": "CI/CD", "mentions": 6, "prev_mentions": 2,
              "change_pct": 200.0, "trend": "rising", "engagement": 40, "unresolved": 3}

    def latest_digest(self): return self.digest
    def get_digest(self, period_end): return self.digest if period_end == "2026-10-09" else None
    def list_digests(self): return [self.digest] if self.digest else []
    def digest_metrics(self, period_end): return [self.metric]
    def metric_history(self, points):
        return [{"period_end": "2026-10-09", "pain_point": "flaky tests", "category": "CI/CD", "mentions": 6,
                 "trend": "rising", "unresolved": 3}] if "flaky tests" in points else []
    def pain_point_posts(self, name):
        return [{"source": "github", "title": "Retries hide flakes", "url": "https://github.com/x/1", "summary": "s",
                 "is_unresolved": True, "sentiment": "negative", "score": 3, "comments": 4,
                 "created_at": "2026-10-05T10:00:00+00:00", "category": "CI/CD"}] if name == "flaky tests" else []
    def recent_runs(self, limit=8): return [{"started_at": "2026-10-09T03:00:01", "trigger": "cron", "status": "failed",
                                             "error": "boom", "stats": {"seconds": 4.2}}]
    def all_topics(self): return [{"id": 1, "category": "CI/CD", "description": "d", "keywords": ["flaky tests"], "active": True}]
    def active_topics(self): return self.all_topics()


def test_pages_render(monkeypatch):
    import api.index as web
    c = client(monkeypatch, ADMIN_PASSWORD="pw")
    monkeypatch.setattr(web, "store", lambda: PageStore())
    home = c.get("/?msg=hello")
    assert home.status_code == 200
    for text in ("In 30 seconds", "Flaky tests", "📈 Rising", "Nobody has a fix", "AI reviews are noisy",
                 'type="checkbox"', "<strong>retry hints</strong>", "+200%", "⚠ GitHub"):
        assert text in home.text, text
    assert "<script>" not in home.text.split("<body>")[1].split("<script>")[0]  # no injected scripts in content
    assert c.get("/history", follow_redirects=False).status_code == 301
    assert "Week of 2026-10-09" in c.get("/archive").text
    assert "Week of 2026-10-09" in c.get("/digest/2026-10-09").text
    assert c.get("/digest/2020-01-01").status_code == 404
    points = c.get("/pain-points").text
    assert "flaky tests" in points.lower() and "Unresolved" in points
    detail = c.get("/pain-point", params={"name": "flaky tests"})
    assert detail.status_code == 200 and "Retries hide flakes" in detail.text and "Mentions by week" in detail.text
    assert c.get("/pain-point", params={"name": "nope"}).status_code == 404
    assert "boom" in c.get("/runs").text
    assert "CI/CD" in c.get("/topics", auth=("sumit", "pw")).text


def test_empty_and_setup_states(monkeypatch):
    import api.index as web
    c = client(monkeypatch, ADMIN_PASSWORD="pw")
    monkeypatch.setattr(web, "store", lambda: PageStore(digest=False))
    assert "Generate first brief" in c.get("/").text
    monkeypatch.undo()
    setup = client(monkeypatch).get("/")  # no Supabase/Gemini settings
    assert setup.status_code == 503 and "SUPABASE_URL" in setup.text


def test_label_filter_keeps_acronyms():
    from api.index import label
    assert label("review latency on large prs") == "Review latency on large PRs"
    assert label("false positives in ai code review") == "False positives in AI code review"
    assert label("ci/cd secrets") == "CI/CD secrets"
