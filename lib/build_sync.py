"""Building Now persistence for projects (migration 005): link observations to projects, public handles,
GitHub releases, the project watchlist and review flags.

Observations (build_items) are only ever inserted or given links (project_id, author); their content is
never rewritten. Project rows are derived from their observations and refreshed after each update.
Every function here tolerates migration 005 not being run yet: it reports that and does nothing.
"""
import time
from datetime import datetime, timezone

import httpx

from lib import build_projects as P
from lib.collectors import HN_URL, HTTP_TIMEOUT
from lib.workspace import ready

OWNER = "admin"            # DevvIT's single owner (ADMIN_PASSWORD), as in shared_reports
AUTHOR_BATCH = 40          # HN ids per Algolia lookup
MAX_AUTHOR_LOOKUPS = 600   # per update
_ITEM_COLS = ("discussion_id,source,origin,discussion_url,project_url,project_title,title_is_ai,title_raw,author,"
              "project_id,posted_at,classified_at,enriched_at,summary,category,stage,stage_quote,focus,focus_quote,comments")
V2_ITEM_FIELDS = ("author", "author_url", "event_type", "event_quote", "focus", "focus_quote", "enriched_at", "project_id")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enabled(sb) -> bool:
    return ready(sb, "build_projects")


def _page_all(make_query, size: int = 1000) -> list[dict]:
    rows, start = [], 0
    while True:
        chunk = make_query().range(start, start + size - 1).execute().data or []
        rows += chunk
        if len(chunk) < size:
            return rows
        start += size


# ---------- public handles ----------
def fetch_hn_authors(ids: list[str]) -> dict[str, str]:
    """{'hn:123': 'pg', ...} for HN stories, via the public Algolia API (no AI). Missing ids are skipped."""
    out: dict[str, str] = {}
    with httpx.Client(headers={"User-Agent": "dev-community-pulse/1.0"}, timeout=HTTP_TIMEOUT) as client:
        for i in range(0, len(ids), AUTHOR_BATCH):
            chunk = [x[3:] for x in ids[i:i + AUTHOR_BATCH] if x.startswith("hn:") and x[3:].isdigit()]
            if not chunk:
                continue
            r = client.get(HN_URL, params={"tags": "(" + ",".join(f"story_{x}" for x in chunk) + ")",
                                           "hitsPerPage": len(chunk)})
            r.raise_for_status()
            for h in r.json().get("hits", []):
                if h.get("objectID") and h.get("author"):
                    out[f"hn:{h['objectID']}"] = h["author"]
    return out


def backfill_authors(sb, items: list[dict], stats: dict) -> None:
    todo = [i["discussion_id"] for i in items if i["source"] == "hn" and not i.get("author")][:MAX_AUTHOR_LOOKUPS]
    if not todo:
        return
    try:
        found = fetch_hn_authors(todo)
    except Exception as e:                       # a source failure never blocks the rest of the update
        stats["author_lookup_error"] = repr(e)[:200]
        return
    by_author: dict[str, list[str]] = {}
    for did, a in found.items():
        by_author.setdefault(a, []).append(did)
    for a, ids in by_author.items():
        sb.table("build_items").update({"author": a, "author_url": P.profile_url("hn", a)}) \
            .in_("discussion_id", ids).is_("author", "null").execute()
    for i in items:
        if i["discussion_id"] in found:
            i["author"] = found[i["discussion_id"]]
    stats["authors_found"] = len(found)


# ---------- projects ----------
def sync_projects(sb, stats: dict | None = None, deadline: float | None = None, full: bool = False) -> dict:
    """Link every relevant observation to a project row and refresh the derived fields of projects that
    gained observations. Once linked, an observation keeps its project (identities stay stable)."""
    stats = stats if stats is not None else {}
    if not enabled(sb):
        stats["projects"] = "migration 005 not run"
        return stats
    items = _page_all(lambda: sb.table("build_items").select(_ITEM_COLS).eq("relevant", True).order("posted_at"))
    backfill_authors(sb, items, stats)
    projects = _page_all(lambda: sb.table("build_projects").select("id,project_key,updated_at"))
    id_by_key = {p["project_key"]: p["id"] for p in projects}
    updated_at = {p["project_key"]: p.get("updated_at") or "" for p in projects}
    groups: dict[str, list[dict]] = {}
    key_of_id = {v: k for k, v in id_by_key.items()}
    for it in items:
        key = key_of_id.get(it.get("project_id")) or P.project_key(it)
        groups.setdefault(key, []).append(it)

    # a project is refreshed when it's new, gained an observation, or one of its observations changed
    # (event/focus enrichment, new release) after the project row was last derived
    touched = {k for k, its in groups.items()
               if full or k not in id_by_key or any(not i.get("project_id") for i in its)
               or any(max(i.get("enriched_at") or "", i.get("classified_at") or "") > updated_at.get(k, "") for i in its)}
    new_keys = {k for k in touched if k not in id_by_key}
    new_rows = [{**P.derive_project(k, groups[k]), "updated_at": _now()} for k in sorted(new_keys)]
    for i in range(0, len(new_rows), 200):
        sb.table("build_projects").upsert(new_rows[i:i + 200], on_conflict="project_key", ignore_duplicates=True).execute()
    if new_rows:
        id_by_key = {p["project_key"]: p["id"] for p in _page_all(lambda: sb.table("build_projects").select("id,project_key"))}

    linked = updated = 0
    for k in sorted(touched):
        if deadline and time.monotonic() > deadline:
            stats["projects_pending"] = True
            break
        pid = id_by_key.get(k)
        if not pid:
            continue
        unlinked = [i["discussion_id"] for i in groups[k] if i.get("project_id") != pid]
        if unlinked:
            sb.table("build_items").update({"project_id": pid}).in_("discussion_id", unlinked).execute()
            linked += len(unlinked)
        if full or k not in new_keys:     # new rows were inserted with fresh derived fields already
            fields = {f: v for f, v in P.derive_project(k, groups[k]).items() if f != "project_key"}
            sb.table("build_projects").update({**fields, "updated_at": _now()}).eq("id", pid).execute()
            updated += 1
    stats.update(projects_created=len(new_rows), observations_linked=linked, projects_updated=updated)
    return stats


# ---------- loading ----------
def load_projects(sb) -> list[dict]:
    return _page_all(lambda: sb.table("build_projects").select("*")) if enabled(sb) else []


def load_project(sb, project_id: str | None = None, key: str | None = None) -> tuple[dict | None, list[dict]]:
    """One project row (or None for observations not linked yet) and ALL its observations, any age."""
    row = None
    if enabled(sb):
        q = sb.table("build_projects").select("*")
        q = q.eq("id", project_id) if project_id else q.eq("project_key", key)
        rows = q.limit(1).execute().data or []
        row = rows[0] if rows else None
    if row:
        items = sb.table("build_items").select("*").eq("project_id", row["id"]).order("posted_at", desc=True).execute().data or []
        if key or not items:
            key = row["project_key"]
    else:
        items = []
    if key and not items:   # not linked yet: find its observations by identity
        cand = _page_all(lambda: sb.table("build_items").select("*").eq("relevant", True))
        items = sorted((i for i in cand if P.project_key(i) == key), key=lambda i: i.get("posted_at") or "", reverse=True)
    return row, items


# ---------- watchlist ----------
def watched_ids(sb) -> set[str]:
    if not ready(sb, "build_watchlist"):
        return set()
    return {r["project_id"] for r in sb.table("build_watchlist").select("project_id").eq("owner", OWNER).execute().data or []}


def watch_entry(sb, project_id: str) -> dict | None:
    if not ready(sb, "build_watchlist"):
        return None
    rows = sb.table("build_watchlist").select("*").eq("owner", OWNER).eq("project_id", project_id).limit(1).execute().data or []
    return rows[0] if rows else None


def set_watch(sb, project_id: str, on: bool, note: str | None = None) -> None:
    if on:
        row = {"owner": OWNER, "project_id": project_id}
        if note is not None:
            row["note"] = note[:2000]
        sb.table("build_watchlist").upsert(row, on_conflict="owner,project_id").execute()
    else:
        sb.table("build_watchlist").delete().eq("owner", OWNER).eq("project_id", project_id).execute()


# ---------- review ----------
def set_review(sb, project_id: str, flagged: bool, note: str = "") -> None:
    sb.table("build_projects").update({"review_status": "flagged" if flagged else "ok", "review_note": note[:1000],
                                       "updated_at": _now()}).eq("id", project_id).execute()


def set_link_status(sb, blocker_id: int, status: str) -> None:
    if status in ("confirmed", "rejected", "suggested"):
        sb.table("build_blockers").update({"link_status": status, "linked_at": _now()}).eq("id", blocker_id).execute()
