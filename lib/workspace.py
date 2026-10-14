"""Persistence for the research workspace (tables from supabase/migrations/002_research_workspace.sql).

Every helper checks that its table exists first, so the app keeps working, read-only, before the
migration has been run. Writes go through the app's POST routes, which are open (DevvIT has no sign-in).
"""
import time
from datetime import datetime, timezone

_checked: dict[str, tuple[bool, float]] = {}
_RECHECK_MISSING = 60  # seconds before re-checking a table that wasn't there


def ready(sb, table: str) -> bool:
    ok, at = _checked.get(table, (False, 0.0))
    if ok or time.time() - at < _RECHECK_MISSING and table in _checked:
        return ok
    try:
        sb.table(table).select("*").limit(1).execute()
        ok = True
    except Exception:
        ok = False
    _checked[table] = (ok, time.time())
    return ok


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- radar ----------
def radar_states(sb) -> dict:
    if not ready(sb, "radar_state"):
        return {}
    return {r["finding_key"]: r for r in sb.table("radar_state").select("*").execute().data or []}


def set_radar_state(sb, key: str, label: str, status: str, first_seen: str | None) -> None:
    sb.table("radar_state").upsert({"finding_key": key, "label": label, "status": status,
                                    "first_seen": first_seen or None, "updated_at": _now()}).execute()


# ---------- opportunities ----------
STATUSES = ["New", "Investigating", "Validating", "Prioritized", "In progress", "Dismissed"]


def opportunity_rows(sb) -> dict:
    if not ready(sb, "opportunities"):
        return {}
    return {r["pain_point"]: r for r in sb.table("opportunities").select("*").execute().data or []}


def save_opportunity(sb, name: str, status: str, notes: str) -> None:
    prev = sb.table("opportunities").select("status,notes").eq("pain_point", name).limit(1).execute().data
    sb.table("opportunities").upsert({"pain_point": name, "status": status, "notes": notes, "updated_at": _now()}).execute()
    changed_status = not prev or prev[0]["status"] != status
    changed_notes = bool(prev) and prev[0]["notes"] != notes
    if changed_status or changed_notes or not prev:
        sb.table("opportunity_log").insert({
            "pain_point": name, "status": status if changed_status else None,
            "note": "Saved to opportunities" if not prev else ("Notes updated" if changed_notes and not changed_status else None),
        }).execute()


def opportunity_log(sb, name: str) -> list[dict]:
    if not ready(sb, "opportunity_log"):
        return []
    return sb.table("opportunity_log").select("*").eq("pain_point", name) \
        .order("created_at", desc=True).limit(30).execute().data or []


def get_insight(sb, name: str, week: str) -> dict | None:
    if not ready(sb, "opportunity_insights"):
        return None
    rows = sb.table("opportunity_insights").select("content,created_at").eq("pain_point", name) \
        .eq("week_start", week).limit(1).execute().data
    return {**rows[0]["content"], "_created_at": rows[0]["created_at"]} if rows else None


def save_insight(sb, name: str, week: str, content: dict) -> None:
    sb.table("opportunity_insights").upsert({"pain_point": name, "week_start": week, "content": content,
                                             "created_at": _now()}).execute()


# ---------- runs (data freshness, coverage, duplicate-run protection) ----------
RUN_LOCK_MINUTES = 10


def run_in_progress(sb) -> bool:
    if not ready(sb, "runs"):
        return False
    rows = sb.table("runs").select("started_at").eq("status", "running") \
        .order("started_at", desc=True).limit(1).execute().data
    if not rows:
        return False
    started = datetime.fromisoformat(rows[0]["started_at"].replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - started).total_seconds() < RUN_LOCK_MINUTES * 60


def start_run(sb, trigger: str) -> int | None:
    if not ready(sb, "runs"):
        return None
    return sb.table("runs").insert({"trigger": trigger}).execute().data[0]["id"]


def finish_run(sb, run_id: int | None, status: str, stats: dict, error: str | None = None) -> None:
    if run_id is None:
        return
    sb.table("runs").update({"status": status, "finished_at": _now(), "stats": stats,
                             "error": (error or "")[:2000] or None}).eq("id", run_id).execute()


def recent_runs(sb, n: int = 8) -> list[dict]:
    if not ready(sb, "runs"):
        return []
    return sb.table("runs").select("*").order("started_at", desc=True).limit(n).execute().data or []
