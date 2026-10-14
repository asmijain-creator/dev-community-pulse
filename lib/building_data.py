"""Data access for the Building Now projects table.

The table page only calls load_projects(). Today it returns the illustrative sample in lib/building_fixture.py;
a Supabase-backed loader can replace it later without touching the page, as long as it returns the same shape
(see BuildingProject in building_fixture). Every record goes through _clean(), so a missing or unexpected value
renders as "unknown" / "insufficient data" instead of breaking the page.
"""
from lib import building_fixture as F

STAGES = ("idea", "prototype", "mvp", "beta", "launched", "unknown")
TRENDS = ("rising", "stable", "declining", "insufficient")
EVIDENCE = ("explicit", "inferred")


def _url(u) -> str | None:
    return u if isinstance(u, str) and u.startswith(("https://", "http://")) else None


def _clean(p: dict) -> dict:
    out = dict(p)
    out["buildStage"] = p.get("buildStage") if p.get("buildStage") in STAGES else "unknown"
    out["activityTrend"] = p.get("activityTrend") if p.get("activityTrend") in TRENDS else "insufficient"
    out["techStack"] = [t for t in p.get("techStack") or [] if isinstance(t, str) and t.strip()]
    for k in ("builderProfileUrl", "sourceUrl", "projectUrl", "repositoryUrl"):
        out[k] = _url(p.get(k))
    blockers = p.get("blockers")
    if blockers is None:
        out["blockers"] = None                       # no blocker information: shown as "—", never as 0
    else:
        out["blockers"] = [{**b, "evidenceType": b.get("evidenceType") if b.get("evidenceType") in EVIDENCE else "inferred"}
                           for b in blockers if b.get("title")]
    out["timeline"] = sorted(({**e, "sourceUrl": _url(e.get("sourceUrl"))} for e in p.get("timeline") or []),
                             key=lambda e: e.get("collectedAt") or "", reverse=True)
    out["isWatched"] = bool(p.get("isWatched"))
    return out


def load_projects() -> dict:
    """{"source", "isSample", "asOf", "projects"}: the only thing the table page reads."""
    return {"source": "sample", "isSample": True, "asOf": F.AS_OF, "projects": [_clean(p) for p in F.PROJECTS]}
