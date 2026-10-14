"""Tests for the Building Now build brief: grouping rules, counts, examples and rendering.

Run with:  python -m pytest -q
No network, database or Gemini access is needed.
"""
import os

os.environ.update(SUPABASE_URL="x", SUPABASE_SERVICE_ROLE_KEY="x", GEMINI_API_KEY="x")

from lib import building as B, views_build as VB  # noqa: E402

NO_TREND = {"rows": [], "history_ok": False}


def item(i: int, **kw) -> dict:
    return {"discussion_id": f"hn:{i}", "discussion_url": f"https://news.ycombinator.com/item?id={i}",
            "project_title": f"Project {i}", "category": "Developer tools", "activity_type": "side_project",
            "stage": None, "score": 0, "comments": 0, "summary": None, "techs": [], "blockers": [], **kw}


def test_phase_uses_the_stated_stage_first():
    assert B.phase(item(1, stage="idea", activity_type="product")) == "ideating"
    assert B.phase(item(2, stage="prototype", activity_type="experiment")) == "building"
    assert B.phase(item(3, activity_type="experiment")) == "ideating"
    assert B.phase(item(4, activity_type="product")) == "building"
    assert B.phase(item(5, activity_type=None)) == "building"


def test_brief_counts_groups_and_shipping():
    items = [item(1, stage="launched"), item(2, stage="alpha_beta"), item(3, stage="prototype"),
             item(4, stage="idea", category="AI agents & LLM apps"), item(5, activity_type="experiment")]
    b = B.brief(items, NO_TREND, NO_TREND)
    assert b["total"] == 5
    assert b["building"]["n"] == 3 and b["building"]["shipping"] == 2
    assert b["ideating"]["n"] == 2 and b["ideating"]["shipping"] == 0
    assert b["categories"][0] == {"key": "Developer tools", "label": "Developer tools", "n": 4}


def test_examples_are_the_most_engaged_discussions():
    items = [item(1, score=5), item(2, score=50, comments=10), item(3, comments=20), item(4, score=1)]
    ex = B.brief(items, NO_TREND, NO_TREND)["building"]["examples"]
    assert [e["discussion_id"] for e in ex] == ["hn:2", "hn:3", "hn:1"]


def test_only_quoted_blockers_and_new_or_growing_trends_count():
    items = [item(1, blockers=[{"kind": "deployment", "detail": "OOM on deploy", "quote": "kept failing with OOM", "explicit": True},
                               {"kind": "performance", "detail": "probably slow", "quote": None, "explicit": False}])]
    tech = {"rows": [{"key": "rust", "label": "Rust", "status": "growing"}, {"key": "go", "label": "Go", "status": "stable"}],
            "history_ok": True}
    cat = {"rows": [{"key": "Security", "label": "Security", "status": "new"}], "history_ok": True}
    b = B.brief(items, tech, cat)
    assert [g["kind"] for g in b["blockers"]] == ["deployment"]
    assert [(r["label"], r["kind"]) for r in b["emerging"]] == [("Security", "category"), ("Rust", "tech")]


def test_render_is_empty_without_discussions():
    assert VB._brief(B.brief([], NO_TREND, NO_TREND), {"days": 30}, "last 30 days") == ""


def test_render_states_counts_and_escapes_titles():
    items = [item(1, stage="launched", project_title="<script>x</script>", score=9,
                  blockers=[{"kind": "deployment", "detail": "d", "quote": "deploys time out", "explicit": True}]),
             item(2, stage="idea")]
    html = VB._brief(B.brief(items, NO_TREND, NO_TREND), {"days": 30}, "last 30 days")
    assert "Build brief" in html and "<b>2</b> project discussions" in html
    assert "<b>1</b> about something they are building (1 launched, in beta or maintained)" in html
    assert "<b>1</b> at the idea or experiment stage" in html
    assert "deployment failures (1)" in html and "“deploys time out”" in html
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html
    assert "(with the current filters)" in VB._brief(B.brief(items, NO_TREND, NO_TREND), {"days": 30, "q": "rust"}, "last 30 days")
