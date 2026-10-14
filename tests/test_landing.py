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
    assert "Live numbers appear here" not in html


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


def test_weeks_count_from_the_first_brief():
    from lib import views as V
    try:
        V.set_first_week("2026-10-09")
        assert V._week_no("2026-10-09") == 0                 # the first brief has no baseline: Week 0
        assert V._week_no("2026-10-16") == 1 and V._week_no("2026-11-06") == 4
        assert "week 0" in VL.landing_page({"week": "2026-10-09", "feed": []})
        V.set_first_week(None)
        assert V._week_no("2026-12-04") == 0                 # unknown first week: never shows a calendar week
    finally:
        V.set_first_week(None)


def test_loading_screen_is_on_every_page_and_hidden_at_rest():
    from lib import views as V
    for html in (V._page("T", "<main></main>"), VL.landing_page(None)):
        assert html.count('id="boot"') == 1
        assert 'class="boot off"' in html                 # a loaded page never starts behind the loader
    assert "[data-run],[data-brefresh]" in V.LOADER        # forms with their own progress keep it
    assert "z-index: 48" in V.LOADER and "z-index: 50" in V.BASE_CSS   # stays under the Run now progress window


def test_logo_has_a_glow_running_along_the_pulse():
    from lib import views as V
    logo = V._logo()
    assert logo.count('pathLength="100"') == 2 and 'class="lm-glow"' in logo and 'class="lm-base"' in logo
    page, landing = V._page("T", "<main></main>"), VL.landing_page(None)
    assert 'class="sb-brand" href="/" aria-label="DevvIT home"><span class="logo-mark"' in page
    assert '<div class="boot-logo"><span class="logo-mark"' in page               # loading screen
    assert 'class="lp-brand" href="/welcome" aria-label="DevvIT"><span class="logo-mark"' in landing
    assert "@keyframes lm-run" in V.BASE_CSS and "prefers-reduced-motion: reduce) { .lm-glow { animation: none" in V.BASE_CSS
