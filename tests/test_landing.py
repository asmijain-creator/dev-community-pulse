"""Tests for the public landing page (/welcome): live numbers, the console feed, and rendering without a database.

Run with:  python -m pytest -q
"""
import os

os.environ.update(SUPABASE_URL="x", SUPABASE_SERVICE_ROLE_KEY="x", GEMINI_API_KEY="x")

from fastapi.testclient import TestClient  # noqa: E402

import api.index as w  # noqa: E402
from lib import views_landing as VL  # noqa: E402

HTML = {"accept": "text/html"}


def bundle():
    return {"week": "2026-10-09", "metrics": [{"pain_point": "flaky tests", "mention_count": 5},
                                             {"pain_point": "<b>slow ci</b>", "mention_count": 3}],
            "posts": [{"is_unresolved": True}, {"is_unresolved": False}, {"is_unresolved": True}]}


def test_live_numbers_and_feed_take_turns():
    builds = [{"project_title": "Tidepool", "source": "hn", "discussion_url": "https://news.ycombinator.com/item?id=1",
               "posted_at": "2026-10-10"},
              {"project_title": "Nolink", "source": "devto", "discussion_url": "javascript:alert(1)", "posted_at": "2026-10-11"}]
    live = w._landing_live(bundle(), builds)
    assert (live["pain_points"], live["mentions"], live["unresolved"], live["builds"]) == (2, 8, 2, 2)
    assert [e["kind"] for e in live["feed"]] == ["pain", "build", "pain", "build"]
    nolink = next(e for e in live["feed"] if e["label"] == "Nolink")
    assert nolink["href"] == "/building" and nolink["external"] is False


def test_page_escapes_labels_and_only_opens_external_links_in_a_new_tab():
    html = VL.landing_page(w._landing_live(bundle(), [{"project_title": "T", "source": "hn",
                                                       "discussion_url": "https://example.com/t", "posted_at": "2026-10-10"}]))
    assert "<b>slow" not in html                      # the label is escaped, never rendered as markup
    assert "&lt;b&gt;slow CI&lt;/b&gt;" in html          # and shown with its acronym restored
    assert 'href="https://example.com/t" target="_blank" rel="noopener noreferrer"' in html
    assert "week 41" in html and "Live numbers appear here" not in html


def test_page_renders_without_live_data():
    html = VL.landing_page(None)
    assert "Live numbers appear here once DevvIT is connected" in html
    assert html.count("<b>—</b>") == 4 and "Waiting for the first weekly brief" in html


def test_welcome_route_survives_a_database_failure(monkeypatch):
    def broken():
        raise RuntimeError("database unreachable")
    monkeypatch.setattr(w, "db", broken)
    r = TestClient(w.app).get("/welcome", headers=HTML)
    assert r.status_code == 200 and "Developer intelligence runtime" in r.text and "Open the dashboard" in r.text
