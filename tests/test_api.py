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


class PageStore:
    digest = {"period_start": "2026-10-02", "period_end": "2026-10-09", "created_at": "x",
              "content_md": "# Pulse\n\n## TL;DR\n- [flaky tests](https://github.com/x) up\n\n| a | b |\n|---|---|\n| 1 | 2 |",
              "stats": {"relevant_this_week": 12, "posts_collected": 80, "email": "sent"}}
    metric = {"pain_point": "flaky tests", "category": "CI/CD", "mentions": 6, "prev_mentions": 2,
              "change_pct": 200.0, "trend": "rising", "engagement": 40, "unresolved": 3}

    def latest_digest(self): return self.digest
    def get_digest(self, period_end): return self.digest if period_end == "2026-10-09" else None
    def list_digests(self): return [self.digest]
    def digest_metrics(self, period_end): return [self.metric]
    def metric_history(self, points): return [{"period_end": "2026-10-09", "pain_point": "flaky tests", "mentions": 6}]
    def recent_runs(self): return [{"started_at": "2026-10-09T03:00:01", "trigger": "cron", "status": "failed", "error": "boom"}]
    def all_topics(self): return [{"id": 1, "category": "CI/CD", "description": "d", "keywords": ["flaky tests"], "active": True}]


def test_pages_render(monkeypatch):
    import api.index as web
    c = client(monkeypatch, ADMIN_PASSWORD="pw")
    monkeypatch.setattr(web, "store", lambda: PageStore())
    home = c.get("/?msg=hello")
    assert home.status_code == 200 and "flaky tests" in home.text and "<table>" in home.text
    assert c.get("/history").status_code == 200
    assert "+200%" in c.get("/digest/2026-10-09").text
    assert c.get("/digest/2020-01-01").status_code == 404
    assert "CI/CD" in c.get("/topics", auth=("sumit", "pw")).text
