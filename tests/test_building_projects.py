"""Building Now projects (migration 005): identity, history, freshness, trends, metrics, filters, the
Trending Stack, Builder Challenges, project sync, watchlist and routes.

Run with:  python -m pytest -q        No network, database or Gemini access is needed.
"""
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

os.environ.update(SUPABASE_URL="x", SUPABASE_SERVICE_ROLE_KEY="x", GEMINI_API_KEY="x", ADMIN_PASSWORD="pw")

from lib import build_config as C  # noqa: E402
from lib import build_projects as P  # noqa: E402
from lib.building import tech_key  # noqa: E402
from tests.fakedb import FakeDB  # noqa: E402

NOW = datetime.now(timezone.utc)


def ago(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def obs(i, days=1, *, title="Tidepool", ai_title=False, author="ada", source="hn", origin="show_hn", project_url=None,
        techs=(), inferred=(), blockers=(), stage=None, comments=3, collected=None, **kw):
    """One stored observation (a build_items row joined with its technologies and blockers)."""
    return {"discussion_id": f"{source}:{i}", "source": source, "origin": origin, "relevant": True,
            "discussion_url": f"https://news.ycombinator.com/item?id={i}", "project_url": project_url,
            "title_raw": f"Show HN: {title}", "project_title": title, "title_is_ai": ai_title, "author": author,
            "posted_at": ago(days), "classified_at": collected or ago(max(days - 0.5, 0)), "category": "Developer tools",
            "summary": f"{title} summary", "stage": stage, "stage_quote": "now in beta" if stage else None,
            "excerpt": None, "score": 10, "comments": comments, "in_posts": False,
            "techs": [{"name": t, "key": tech_key(t), "kind": "other", "explicit": True} for t in techs]
                     + [{"name": t, "key": tech_key(t), "kind": "other", "explicit": False} for t in inferred],
            "blockers": [{"id": 900 + n, "kind": k, "detail": d, "quote": d, "explicit": e}
                         for n, (k, d, e) in enumerate(blockers)], **kw}


# ---------- identity ----------
def test_project_key_prefers_repository_then_website_then_name_then_post():
    assert P.project_key(obs(1, project_url="https://github.com/Ada/Tidepool/tree/main")) == "gh:ada/tidepool"
    assert P.project_key(obs(1, project_url="https://www.tidepool.dev/docs/start?x=1")) == "url:tidepool.dev/docs/start"
    assert P.project_key(obs(1, project_url="https://www.youtube.com/watch?v=1")) == "name:hn:ada:tidepool"
    assert P.project_key(obs(1, author=None)) == "item:hn:1"
    assert P.project_key(obs(1, ai_title=True)) == "item:hn:1"          # an AI-written title never identifies a project
    assert P.github_repo("https://github.com/orgs/acme") is None


def test_profile_url_only_for_plain_handles():
    assert P.profile_url("hn", "ada") == "https://news.ycombinator.com/user?id=ada"
    assert P.profile_url("hn", "a b<script>") is None and P.profile_url("stackoverflow", "x") is None


def test_derive_project_keeps_history_and_newest_evidence():
    items = [obs(1, 40, stage="alpha_beta", collected=ago(39)), obs(2, 3, stage="launched", focus="offline sync",
                                                                     focus_quote="now working on offline sync", collected=ago(2))]
    p = P.derive_project("name:hn:ada:tidepool", items)
    assert p["project_name"] == "Tidepool" and not p["name_is_ai"]
    assert p["build_stage"] == "launched" and p["current_focus"] == "offline sync"   # newest evidence wins
    assert p["first_seen_at"][:10] == ago(39)[:10] and p["last_observed_at"][:10] == ago(2)[:10]   # collection dates
    assert p["first_published_at"][:10] == ago(40)[:10]                                            # post dates kept apart
    assert p["builder_profile_url"] == "https://news.ycombinator.com/user?id=ada"


def test_stage_is_unknown_without_evidence_and_legacy_values_map():
    assert P.derive_project("k", [obs(1)])["build_stage"] == "unknown"
    assert P.stage_of("alpha_beta") == "beta" and P.stage_of("maintained") == "launched" and P.stage_of("nonsense") == "unknown"


# ---------- freshness and trends ----------
def test_old_announcement_is_not_current_activity():
    assert P.freshness(ago(200), ago(200), NOW) == "quiet"
    assert P.freshness(ago(5), ago(5), NOW) == "new"
    assert P.freshness(ago(60), ago(10), NOW) == "recent"
    assert P.freshness(None, None, NOW) == "unknown"


def test_activity_trend_needs_comparable_history():
    assert P.activity_trend([obs(1, 2)], NOW)["status"] == "insufficient"                         # one isolated post
    assert P.activity_trend([obs(i, 2) for i in range(4)], NOW)["status"] == "insufficient"         # zero baseline
    rising = [obs(i, 2) for i in range(5)] + [obs(10, 40)]
    assert P.activity_trend(rising, NOW)["status"] == "rising"
    declining = [obs(1, 2)] + [obs(i, 40) for i in range(10, 15)]
    assert P.activity_trend(declining, NOW)["status"] == "declining"
    stable = [obs(1, 2), obs(2, 3), obs(10, 40), obs(11, 41)]
    assert P.activity_trend(stable, NOW)["status"] == "stable"


# ---------- assembling, metrics, filters ----------
def _projects():
    items = [
        obs(1, 2, techs=["Rust", "Postgres"], blockers=[("deployment", "Deploys to Fly fail with OOM", True)]),
        obs(2, 5, techs=["Rust"], blockers=[("deployment", "Deploys to Fly fail with OOM", True)]),     # same project, same blocker
        obs(3, 4, title="Lumen", author="bob", project_url="https://lumen.app", techs=["Next.js"], inferred=["Redis"],
            blockers=[("ai_reliability", "Agents loop forever", False)], stage="launched"),
        obs(4, 120, title="Oldie", author="cy", project_url="https://oldie.io", techs=["Django"]),
    ]
    return P.assemble([], items, NOW)


def test_assemble_groups_observations_into_distinct_projects():
    ps = {p["project_name"]: p for p in _projects()}
    assert set(ps) == {"Tidepool", "Lumen", "Oldie"}
    assert len(ps["Tidepool"]["items"]) == 2 and len(ps["Tidepool"]["blockers"]) == 1     # duplicate blocker counted once
    assert [t["name"] for t in ps["Lumen"]["techs"]] == ["Next.js", "Redis"]               # explicit before inferred
    assert ps["Oldie"]["freshness"] == "quiet"


def test_metrics_count_distinct_entities_from_real_rows():
    ps = P.filter_projects(_projects(), {"days": 30}, NOW)
    stack = P.stack(ps, NOW.date(), 30)
    m = P.metrics(ps, {"days": 30}, NOW, stack)
    assert m["projects"] == 2                         # Oldie's only post is 120 days old
    assert m["builders"] == 2                         # ada (2 posts) + bob; cy's post is too old to count as active
    assert m["blockers"] == 1                         # one explicit distinct blocker; the AI-inferred one isn't counted
    assert P.metrics([], {"days": 30}, NOW, P.stack([], NOW.date(), 30)) == {
        "projects": 0, "builders": 0, "active_days": 30, "trending": None, "blockers": 0}


def test_filters_work_together_and_search_matches_word_starts():
    ps = _projects()
    f = lambda **kw: [p["project_name"] for p in P.filter_projects(ps, {"days": 0, **kw}, NOW)]
    assert f(q="postg") == ["Tidepool"] and f(q="bob") == ["Lumen"] and f(q="rust postg") == ["Tidepool"]
    assert f(tech="rust", blockers="yes") == ["Tidepool"]
    assert f(stage="launched", source="hn") == ["Lumen"]
    assert f(fresh="quiet") == ["Oldie"] and f(blockers="no") == ["Lumen", "Oldie"]
    first = ps[0]["first_seen_at"][:10]
    assert f(seen_from=first, seen_to=first, category="Developer tools") == [p["project_name"] for p in ps if p["first_seen_at"][:10] == first]
    assert f(q="nothingmatches") == []


def test_sorting_and_pagination():
    ps = _projects()
    assert [p["project_name"] for p in P.sort_projects(ps, "name")] == ["Lumen", "Oldie", "Tidepool"]
    assert P.sort_projects(ps, "discussed")[0]["project_name"] == "Tidepool"      # 3+3 comments
    rows, page, pages = P.paginate(list(range(60)), 3, 25)
    assert rows == list(range(50, 60)) and (page, pages) == (3, 3)
    assert P.paginate([], 9)[1:] == (1, 1)


# ---------- Trending Stack ----------
def _stack_items(today: date):
    weeks = P.period_windows(today, 7)
    cur, prev = weeks[0][0], weeks[1][0]
    at = lambda d: datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc).isoformat()
    items = []
    for k in range(3):     # Rust: 1 project before, 3 now -> growing
        items.append(obs(100 + k, techs=["Rust"], author=f"r{k}", title=f"R{k}", posted_at=at(cur)))
    items.append(obs(110, techs=["Rust"], author="r9", title="R9", posted_at=at(prev)))
    for k in range(2):     # Zig: 2 projects now, none before, never seen -> new to DevvIT
        items.append(obs(200 + k, techs=["Zig"], author=f"z{k}", title=f"Z{k}", posted_at=at(cur)))
    items.append(obs(300, techs=["Go"], inferred=["Kotlin"], author="g", title="G", posted_at=at(cur)))   # 1 project: not listed
    return items


def test_stack_compares_equal_periods_by_distinct_projects():
    today = NOW.date()
    ps = P.assemble([], _stack_items(today), NOW)
    s = P.stack(ps, today, 7)
    rows = {r["name"]: r for r in s["rows"]}
    assert s["covered"]
    assert rows["Rust"]["status"] == "growing" and (rows["Rust"]["cur"], rows["Rust"]["prev"]) == (3, 1)
    assert rows["Rust"]["pct"] == 200
    assert rows["Zig"]["status"] == "new" and rows["Zig"]["pct"] is None          # no infinite % on a zero baseline
    assert "Go" not in rows and "Kotlin" not in rows                              # too few projects / AI-inferred only


def test_stack_waits_for_history_and_filters_by_group():
    today = NOW.date()
    ps = P.assemble([], [i for i in _stack_items(today) if i["discussion_id"] != "hn:110"], NOW)
    s = P.stack(ps, today, 7)
    assert not s["covered"] and all(r["status"] == "history" for r in s["rows"])
    assert [r["name"] for r in P.stack(ps, today, 7, "languages")["rows"]] == ["Rust", "Zig"]
    assert P.stack(ps, today, 7, "databases")["rows"] == []


# ---------- Builder Challenges ----------
def test_challenges_keep_explicit_and_inferred_apart():
    ch = P.challenges(_projects(), 30, NOW)
    assert [g["category"] for g in ch["groups"]] == ["deployment"] and len(ch["groups"][0]["rows"]) == 1
    assert [r["detail"] for r in ch["inferred"]] == ["Agents loop forever"]
    assert ch["unmatched"] == 1


def test_legacy_blocker_kinds_map_to_spec_categories():
    assert P.blocker_category("testing_debugging") == "debugging" and P.blocker_category("integration") == "api_integration"
    assert P.blocker_category("authentication") == "authentication" and P.blocker_category(None) == "other"


def test_pain_point_links_need_evidence_not_keywords():
    same = obs(1, pain_point="slow docker builds")
    linked = obs(2, blockers=[("performance", "docker builds are slow", True)])
    linked["blockers"][0].update(pain_point="slow docker builds", link_method="ai_match", link_status="suggested",
                                 link_basis="Both describe slow container builds")
    keyword_only = obs(3, blockers=[("performance", "slow docker builds everywhere", True)])     # shares words, no link
    rejected = obs(4, blockers=[("performance", "docker builds", True)])
    rejected["blockers"][0].update(pain_point="slow docker builds", link_method="ai_match", link_status="rejected")
    rows = P.builds_for_pain_point("slow docker builds", [same, linked, keyword_only, rejected])
    assert [(r["item"]["discussion_id"], r["suggested"]) for r in rows] == [("hn:1", False), ("hn:2", True)]


def test_missing_fields_do_not_break_assembly():
    bare = {"discussion_id": "github:9", "source": "github", "relevant": True}
    p = P.assemble([], [bare], NOW)[0]
    assert p["project_name"] == "Untitled" and p["freshness"] == "unknown" and p["trend"]["status"] == "insufficient"


# ---------- sync (persistence) ----------
def _db(items, **extra):
    rows = []
    for i in items:
        r = {k: v for k, v in i.items() if k not in ("techs", "blockers")}
        rows.append(r)
    return FakeDB({"build_items": rows, "build_projects": [], "build_watchlist": [], "build_technologies": [],
                   "build_blockers": [], "build_refreshes": [], "digests": [], "posts": [], **extra},
                  defaults={"build_projects": {"id": lambda: str(uuid.uuid4())}})


def test_sync_links_observations_and_is_idempotent(monkeypatch):
    from lib import build_sync as S, workspace
    workspace._checked.clear()
    monkeypatch.setattr(S, "fetch_hn_authors", lambda ids: {"hn:3": "bob"})
    items = [obs(1, 5), obs(2, 2), obs(3, 1, title="Lumen", author=None, project_url="https://lumen.app")]
    sb = _db(items)
    st = S.sync_projects(sb)
    projects = sb.tables["build_projects"]
    assert st["projects_created"] == 2 and len(projects) == 2
    by_key = {p["project_key"]: p["id"] for p in projects}
    links = {i["discussion_id"]: i["project_id"] for i in sb.tables["build_items"]}
    assert links["hn:1"] == links["hn:2"] == by_key["name:hn:ada:tidepool"] and links["hn:3"] == by_key["url:lumen.app"]
    assert next(i for i in sb.tables["build_items"] if i["discussion_id"] == "hn:3")["author"] == "bob"
    S.sync_projects(sb)                                     # second run: no duplicates, nothing re-linked
    assert len(sb.tables["build_projects"]) == 2
    sb.tables["build_items"].append({k: v for k, v in obs(4, 0.5).items() if k not in ("techs", "blockers")})
    st = S.sync_projects(sb)
    assert st["projects_created"] == 0 and st["observations_linked"] == 1          # a new post joins its project


def test_sync_reports_missing_migration():
    from lib import build_sync as S, workspace
    workspace._checked.clear()
    sb = FakeDB({"build_items": []}, missing={"build_projects"})
    assert S.sync_projects(sb)["projects"] == "migration 005 not run"


def test_author_lookup_failure_never_blocks_linking(monkeypatch):
    from lib import build_sync as S, workspace
    workspace._checked.clear()
    monkeypatch.setattr(S, "fetch_hn_authors", lambda ids: (_ for _ in ()).throw(RuntimeError("algolia down")))
    sb = _db([obs(1, 2, author=None, project_url="https://lumen.app")])
    st = S.sync_projects(sb)
    assert "algolia down" in st["author_lookup_error"] and st["projects_created"] == 1


# ---------- routes ----------
@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    import api.index as w
    from lib import build_sync as S, workspace
    workspace._checked.clear()
    monkeypatch.setattr(S, "fetch_hn_authors", lambda ids: {})
    items = [obs(1, 2, techs=["Rust"], blockers=[("deployment", "Deploys to Fly fail with OOM", True)]),
             obs(2, 40, techs=["Rust"]),
             obs(3, 4, title="Lumen", author="bob", project_url="https://lumen.app", techs=["Next.js"])]
    sb = _db(items)
    for i in items:
        for t in i["techs"]:
            sb.tables["build_technologies"].append({**t, "discussion_id": i["discussion_id"]})
        for b in i["blockers"]:
            sb.tables["build_blockers"].append({**b, "discussion_id": i["discussion_id"]})
    S.sync_projects(sb)
    monkeypatch.setattr(w, "db", lambda: sb)
    return w, TestClient(w.app), sb


def _pid(sb, key):
    return next(p["id"] for p in sb.tables["build_projects"] if p["project_key"] == key)


def test_building_tab_lists_persisted_projects(client):
    w, c, sb = client
    r = c.get("/building?days=90")
    assert r.status_code == 200 and 'href="/building" class="on"' in r.text
    assert "Track publicly shared developer projects" in r.text and "can't know what anyone is privately" in r.text
    for text in ("Tidepool", "Lumen", "Projects discovered", "Trending Stack", "Builder Challenges", "Deploys to Fly fail with OOM"):
        assert text in r.text
    assert f'/building/project?id={_pid(sb, "name:hn:ada:tidepool")}' in r.text
    r = c.get("/building?days=90&tech=nextjs")
    assert "Lumen" in r.text and ">Tidepool<" not in r.text


def test_tech_tags_link_to_the_tech_filter(client):
    w, c, sb = client
    assert 'href="/building?tech=rust"' in c.get("/building").text


def test_project_page_shows_the_right_record_with_full_history(client):
    w, c, sb = client
    pid = _pid(sb, "name:hn:ada:tidepool")
    r = c.get(f"/building/project?id={pid}")
    assert r.status_code == 200 and "Tidepool" in r.text and "Lumen" not in r.text
    assert r.text.count('class="tl-i"') == 2                       # both observations, the 40-day-old one included
    assert "Explicitly reported" in r.text and "Not yet compared with pain points" in r.text
    assert c.get("/building/project?id=nope").status_code == 404


def test_watchlist_is_private_and_persists(client):
    w, c, sb = client
    pid = _pid(sb, "url:lumen.app")
    assert c.post("/building/watch", data={"project_id": pid, "on": 1}, follow_redirects=False).status_code == 401
    r = c.post("/building/watch", data={"project_id": pid, "on": 1, "note": "secret plan", "back": f"/building/project?id={pid}"},
               auth=("sumit", "pw"), follow_redirects=False)
    assert r.status_code == 303 and sb.tables["build_watchlist"][0]["note"] == "secret plan"
    assert "secret plan" not in c.get(f"/building/project?id={pid}").text              # notes never shown publicly
    assert "secret plan" in c.get(f"/building/project?id={pid}", auth=("sumit", "pw")).text
    assert c.get("/building?watch=1").status_code == 401                               # saved view needs the password
    saved = c.get("/building?watch=1&days=0", auth=("sumit", "pw")).text
    assert "Lumen" in saved and ">Tidepool<" not in saved
    c.post("/building/watch", data={"project_id": pid, "on": 0}, auth=("sumit", "pw"))
    assert sb.tables["build_watchlist"] == []


def test_watch_rejects_unknown_projects_and_offsite_redirects(client):
    w, c, sb = client
    assert c.post("/building/watch", data={"project_id": "x", "on": 1}, auth=("a", "pw")).status_code == 404
    pid = _pid(sb, "url:lumen.app")
    r = c.post("/building/watch", data={"project_id": pid, "on": 1, "back": "https://evil.example"}, auth=("a", "pw"),
               follow_redirects=False)
    assert r.headers["location"].startswith("/building/project?id=")


def test_flag_for_review_needs_admin(client):
    w, c, sb = client
    pid = _pid(sb, "url:lumen.app")
    assert c.post("/building/flag", data={"project_id": pid, "flagged": 1, "note": "wrong"}).status_code == 401
    c.post("/building/flag", data={"project_id": pid, "flagged": 1, "note": "wrong name"}, auth=("a", "pw"))
    assert "Flagged for review" in c.get(f"/building/project?id={pid}").text


def test_page_works_before_migration_005(monkeypatch):
    from fastapi.testclient import TestClient
    import api.index as w
    from lib import workspace
    workspace._checked.clear()
    sb = _db([obs(1, 2, techs=["Rust"])])
    sb.missing = {"build_projects", "build_watchlist"}
    sb.tables["build_items"][0].pop("author")
    monkeypatch.setattr(w, "db", lambda: sb)
    c = TestClient(w.app)
    r = c.get("/building")
    assert r.status_code == 200 and "Tidepool" in r.text and "005_building_projects.sql" in r.text
    assert "/building/project?key=" in r.text
    assert c.get("/building/project?key=" + P.project_key(sb.tables["build_items"][0])).status_code == 200


def test_empty_state_never_shows_sample_data(monkeypatch):
    from fastapi.testclient import TestClient
    import api.index as w
    from lib import workspace
    workspace._checked.clear()
    monkeypatch.setattr(w, "db", lambda: _db([]))
    r = TestClient(w.app).get("/building")
    assert "No build activity stored yet" in r.text and "Projects discovered" not in r.text
