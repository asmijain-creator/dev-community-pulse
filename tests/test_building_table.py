"""Tests for the Building Now projects table prototype: sample data contract, data boundary and the page route.

Run with:  python -m pytest -q
No network, database or Gemini access is needed (the route must not touch the database at all).
"""
import json
import os
import re

os.environ.update(SUPABASE_URL="x", SUPABASE_SERVICE_ROLE_KEY="x", GEMINI_API_KEY="x")

from fastapi.testclient import TestClient  # noqa: E402

from lib import building_data as BD, building_fixture as F  # noqa: E402

HTML = {"accept": "text/html"}


def _client(monkeypatch):
    import api.index as w

    def no_db():
        raise AssertionError("the prototype table must not query the database")
    monkeypatch.setattr(w, "db", no_db)
    return TestClient(w.app)


def _embedded(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="bt-data">(.*?)</script>', html, re.S)
    assert m, "sample data JSON is embedded in the page"
    return json.loads(m.group(1))


# ---------- sample data ----------
def test_sample_covers_the_ui_edge_cases():
    ps = F.PROJECTS
    assert 12 <= len(ps) <= 15
    assert len({p["id"] for p in ps}) == len(ps)
    assert any(len(p["name"]) > 60 for p in ps)                           # long project name
    assert any(not p["builderName"] and not p["builderUsername"] for p in ps)   # missing builder
    assert any(p["buildStage"] == "unknown" for p in ps)
    assert any(p["blockers"] is None for p in ps)                         # no blocker information
    assert any(p["blockers"] == [] for p in ps)                           # checked, none reported
    assert any(p["activityTrend"] == "insufficient" for p in ps)
    assert any(len(p["currentFocus"] or "") > 200 for p in ps)            # long focus text
    assert any(len(p["techStack"]) > 3 for p in ps)                       # "+N" tag overflow
    assert {p["activityTrend"] for p in ps} == set(BD.TRENDS)


def test_sample_links_are_placeholders_only():
    urls = [u for p in F.PROJECTS for u in (p["sourceUrl"], p["projectUrl"], p["repositoryUrl"], p["builderProfileUrl"]) if u]
    urls += [e["sourceUrl"] for p in F.PROJECTS for e in p["timeline"] if e["sourceUrl"]]
    assert urls and all(u.startswith("https://example.com/") for u in urls)


# ---------- data boundary ----------
def test_load_projects_marks_the_data_as_sample():
    d = BD.load_projects()
    assert d["isSample"] is True and d["source"] == "sample" and d["asOf"] == F.AS_OF
    assert len(d["projects"]) == len(F.PROJECTS)


def test_clean_handles_missing_and_unexpected_values():
    p = BD._clean({"id": "x", "name": "X", "buildStage": "shipped", "activityTrend": "viral", "techStack": ["Go", "", None],
                   "sourceUrl": "javascript:alert(1)", "blockers": [{"title": "t", "evidenceType": "guess"}, {"title": ""}],
                   "timeline": [{"collectedAt": "2026-01-01"}, {"collectedAt": "2026-03-01", "sourceUrl": "ftp://x"}]})
    assert p["buildStage"] == "unknown" and p["activityTrend"] == "insufficient"
    assert p["techStack"] == ["Go"] and p["sourceUrl"] is None
    assert p["blockers"] == [{"title": "t", "evidenceType": "inferred"}]       # untitled blocker dropped
    assert [e["collectedAt"] for e in p["timeline"]] == ["2026-03-01", "2026-01-01"]   # newest first
    assert p["timeline"][0]["sourceUrl"] is None and p["isWatched"] is False


def test_clean_keeps_none_and_empty_blockers_apart():
    assert BD._clean({"blockers": None})["blockers"] is None
    assert BD._clean({"blockers": []})["blockers"] == []


# ---------- route ----------
def test_table_page_renders_without_a_database(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/building/table", headers=HTML)
    assert r.status_code == 200
    t = r.text
    assert "Building Now" in t and "Prototype · sample data." in t
    assert 'placeholder="Search projects, technologies or builders..."' in t
    for label in ("Project", "Builder", "Category", "Tech stack", "Build stage", "Current focus", "Blockers",
                  "Activity", "Last observed", "Actions"):
        assert f">{label}<" in t
    assert _embedded(t)["projects"] == BD.load_projects()["projects"]


def test_state_parameter_is_validated(monkeypatch):
    c = _client(monkeypatch)
    for s in ("loading", "empty", "error"):
        assert f'data-state="{s}"' in c.get(f"/building/table?state={s}", headers=HTML).text
    assert 'data-state=""' in c.get('/building/table?state="><script>', headers=HTML).text


def test_embedded_json_cannot_close_the_script_tag(monkeypatch):
    import lib.building_data as data
    monkeypatch.setattr(data.F, "PROJECTS", [{**F.PROJECTS[0], "name": "</script><script>alert(1)</script>"}])
    t = _client(monkeypatch).get("/building/table", headers=HTML).text
    assert "</script><script>alert(1)" not in t
    assert _embedded(t)["projects"][0]["name"] == "</script><script>alert(1)</script>"
