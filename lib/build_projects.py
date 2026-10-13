"""Building Now projects: identity, history, freshness, trends and metrics. Pure logic, no database or network.

A *project* groups the public observations (build_items rows) that point at the same thing: the same public
repository, the same project website, or the same name posted by the same public handle. Everything shown
about a project is derived from those stored observations, and every count is of distinct entities:
distinct projects, distinct public handles, distinct blockers, never raw post counts.
"""
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from lib import build_config as C
from lib.building import _clip, _norm, complete_weeks, tech_key, week_start
from lib.evidence import tokens

_GH_RESERVED = {"orgs", "features", "topics", "collections", "marketplace", "sponsors", "settings", "about",
                "pricing", "explore", "trending", "login", "join", "apps", "search", "notifications", "issues", "pulls"}


# ---------- dates ----------
def parse_ts(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


# ---------- identity ----------
def github_repo(url: str | None) -> str | None:
    """'https://github.com/Owner/Repo/issues/3' -> 'owner/repo'. None for profiles and GitHub's own pages."""
    try:
        u = urlsplit(url or "")
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or u.hostname not in ("github.com", "www.github.com"):
        return None
    parts = [p for p in u.path.split("/") if p]
    if len(parts) < 2 or parts[0].lower() in _GH_RESERVED:
        return None
    repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
    return f"{parts[0].lower()}/{repo.lower()}" if repo else None


def url_key(url: str | None) -> str | None:
    """A project website as 'host/path' (at most two path segments). None for hosts that don't identify a project."""
    try:
        u = urlsplit(url or "")
    except ValueError:
        return None
    host = (u.hostname or "").lower().removeprefix("www.")
    if u.scheme not in ("http", "https") or not host or "." not in host:
        return None
    if host in C.GENERIC_HOSTS or any(host.endswith("." + g) for g in C.GENERIC_HOSTS) or host == "github.com":
        return None
    parts = [p for p in u.path.split("/") if p and p not in ("index.html", "index.php")][:2]
    return "/".join([host, *[p.lower() for p in parts]])


def project_key(item: dict) -> str:
    """Stable identity for the project an observation is about (see migration 005)."""
    for url in (item.get("project_url"), item.get("discussion_url") if item.get("source") == "github" else None):
        repo = github_repo(url)
        if repo:
            return f"gh:{repo}"
    k = url_key(item.get("project_url"))
    if k:
        return f"url:{k}"
    if item.get("author") and item.get("project_title") and not item.get("title_is_ai"):
        name = re.sub(r"[^a-z0-9]+", "-", _norm(item["project_title"])).strip("-")[:60]
        if name:
            return f"name:{item.get('source')}:{item['author'].lower()}:{name}"
    return f"item:{item['discussion_id']}"


def profile_url(source: str | None, handle: str | None) -> str | None:
    if not handle or not re.fullmatch(r"[A-Za-z0-9_.\-]{1,60}", handle):
        return None
    return {"hn": f"https://news.ycombinator.com/user?id={handle}",
            "github": f"https://github.com/{handle}"}.get(source or "")


# ---------- taxonomies ----------
def stage_of(raw: str | None) -> str:
    return C.LEGACY_STAGE.get(raw or "", "unknown")


def blocker_category(kind: str | None) -> str:
    k = kind or "other"
    return k if k in C.BLOCKER_CATEGORIES else C.LEGACY_BLOCKER.get(k, "other")


def tech_group(key: str, kind: str | None) -> str:
    return C.KNOWN_TECH.get(key) or C.KIND_GROUP.get(kind or "other", "other")


# ---------- one project from its observations ----------
def _when(it: dict) -> datetime:
    return parse_ts(it.get("posted_at")) or parse_ts(it.get("classified_at")) or datetime.min.replace(tzinfo=timezone.utc)


def derive_project(key: str, items: list[dict]) -> dict:
    """Project fields from its observations (newest evidence wins for stage and focus). Deterministic."""
    obs = sorted(items, key=_when)                       # oldest first
    discussions = [i for i in obs if i.get("origin") != "repo_release"] or obs
    named = [i["project_title"] for i in discussions if i.get("project_title") and not i.get("title_is_ai")]
    if named:
        name, name_is_ai = Counter(named).most_common(1)[0][0], False
    else:
        latest_title = next((i.get("project_title") for i in reversed(discussions) if i.get("project_title")), None)
        repo = key[3:] if key.startswith("gh:") else None
        name = latest_title or (repo.split("/")[1] if repo else None) or discussions[-1].get("title_raw") or "Untitled"
        name_is_ai = bool(latest_title)
    staged = [i for i in obs if i.get("stage") and stage_of(i["stage"]) != "unknown"]
    focused = [i for i in obs if i.get("focus")]
    announcer = next((i for i in discussions if i.get("author")), None)
    repo = key[3:] if key.startswith("gh:") else next((github_repo(i.get("project_url")) for i in obs if github_repo(i.get("project_url"))), None)
    proj_url = next((i["project_url"] for i in reversed(obs) if i.get("project_url") and not github_repo(i["project_url"])), None)
    cats = Counter(i["category"] for i in discussions if i.get("category"))
    seen = [parse_ts(i.get("classified_at")) for i in obs if parse_ts(i.get("classified_at"))]
    pub = [parse_ts(i.get("posted_at")) for i in obs if parse_ts(i.get("posted_at"))]
    now = datetime.now(timezone.utc)
    return {
        "project_key": key, "project_name": _clip(name, 160), "name_is_ai": name_is_ai,
        "description": next((i["summary"] for i in reversed(discussions) if i.get("summary")), None),
        "category": cats.most_common(1)[0][0] if cats else None,
        "project_url": proj_url, "repository_url": f"https://github.com/{repo}" if repo else None,
        "builder_platform": (announcer or {}).get("source"), "builder_username": (announcer or {}).get("author"),
        "builder_profile_url": profile_url((announcer or {}).get("source"), (announcer or {}).get("author")),
        "build_stage": stage_of(staged[-1]["stage"]) if staged else "unknown",
        "stage_quote": staged[-1].get("stage_quote") if staged else None,
        "current_focus": focused[-1]["focus"] if focused else None,
        "focus_quote": focused[-1].get("focus_quote") if focused else None,
        "focus_observed_at": focused[-1].get("posted_at") if focused else None,
        "first_seen_at": _iso(min(seen)) if seen else _iso(now), "last_observed_at": _iso(max(seen)) if seen else _iso(now),
        "first_published_at": _iso(min(pub)) if pub else None, "last_published_at": _iso(max(pub)) if pub else None,
    }


def tech_stack(items: list[dict]) -> list[dict]:
    """Technologies across a project's observations: explicit (named in a post) before AI-inferred."""
    out: dict[str, dict] = {}
    for it in sorted(items, key=_when):
        for t in it.get("techs", []):
            r = out.setdefault(t["key"], {"key": t["key"], "names": Counter(), "kind": t.get("kind") or "other",
                                          "explicit": False, "first": it.get("posted_at"), "last": it.get("posted_at"),
                                          "evidence": None})
            r["names"][t["name"]] += 1
            r["last"] = it.get("posted_at")
            if t.get("explicit") and not r["explicit"]:
                r["explicit"], r["evidence"] = True, it
            r["evidence"] = r["evidence"] or it
    rows = []
    for r in out.values():
        r["name"] = r.pop("names").most_common(1)[0][0]
        r["group"] = tech_group(r["key"], r["kind"])
        rows.append(r)
    return sorted(rows, key=lambda r: (not r["explicit"], r["name"].lower()))


def distinct_blockers(items: list[dict]) -> list[dict]:
    """One entry per distinct blocker (same category and same wording count once), newest evidence kept."""
    seen: dict[tuple, dict] = {}
    for it in sorted(items, key=_when):
        for b in it.get("blockers", []):
            cat = blocker_category(b.get("kind"))
            k = (cat, bool(b.get("explicit")), " ".join(sorted(tokens(b.get("detail")))) or _norm(b.get("detail")))
            seen[k] = {**b, "category": cat, "item": it}
    return sorted(seen.values(), key=lambda b: (not b["explicit"], -_when(b["item"]).timestamp()))


# ---------- freshness and trend ----------
def freshness(first_pub: str | None, last_pub: str | None, now: datetime) -> str:
    """new | recent | quiet | unknown, from ORIGINAL post dates (collection dates never make a project 'active')."""
    first, last = parse_ts(first_pub), parse_ts(last_pub)
    if not last:
        return "unknown"
    if (now - last).days > C.RECENT_DAYS:
        return "quiet"
    if first and (now - first).days <= C.NEW_DAYS:
        return "new"
    return "recent"


FRESHNESS = {"new": "Newly discovered", "recent": "Recently observed", "quiet": "No recent evidence",
             "unknown": "Unknown activity"}


def activity_trend(items: list[dict], now: datetime) -> dict:
    """Compare observations in the latest TREND_WINDOW_DAYS with the window before. One isolated post is
    never a trend: below TREND_MIN_OBS, or with no observations in the earlier window, it's insufficient."""
    w = timedelta(days=C.TREND_WINDOW_DAYS)
    dates = [parse_ts(i.get("posted_at")) for i in items]
    cur = sum(1 for d in dates if d and now - w < d <= now)
    prev = sum(1 for d in dates if d and now - 2 * w < d <= now - w)
    if cur + prev < C.TREND_MIN_OBS or prev == 0:
        status = "insufficient"
    elif cur >= prev * C.TREND_RATIO and cur - prev >= C.TREND_MIN_DELTA:
        status = "rising"
    elif cur * C.TREND_RATIO <= prev and prev - cur >= C.TREND_MIN_DELTA:
        status = "declining"
    else:
        status = "stable"
    return {"status": status, "cur": cur, "prev": prev, "delta": cur - prev}


TRENDS = {"rising": ("▲", "Rising"), "stable": ("■", "Stable"), "declining": ("▼", "Declining"),
          "insufficient": ("·", "Insufficient data")}


# ---------- projects for the page ----------
def assemble(projects: list[dict], items: list[dict], now: datetime, watched: set[str] | None = None) -> list[dict]:
    """Join stored projects with their observations. Observations not yet linked to a stored project are
    grouped by project_key, so nothing collected is hidden before the next update links it."""
    by_id = {p["id"]: {**p, "items": []} for p in projects if p.get("id")}
    by_key = {p["project_key"]: p for p in by_id.values()}
    virtual: dict[str, list[dict]] = {}
    for it in items:
        p = by_id.get(it.get("project_id")) or by_key.get(project_key(it))
        if p:
            p["items"].append(it)
        else:
            virtual.setdefault(project_key(it), []).append(it)
    out = list(by_id.values())
    for key, its in virtual.items():
        out.append({**derive_project(key, its), "id": None, "items": its, "review_status": "ok"})
    rows = []
    for p in out:
        if not p["items"]:
            continue
        its = sorted(p["items"], key=_when, reverse=True)
        fresh = derive_project(p["project_key"], its)        # recomputed so the page never shows stale derived fields
        merged = {**p, **{k: v for k, v in fresh.items() if k not in ("first_seen_at", "last_observed_at")}}
        # collection dates: the stored project keeps the earliest/latest even for observations outside the load window
        merged["first_seen_at"] = min(filter(None, [p.get("first_seen_at"), fresh["first_seen_at"]]))
        merged["last_observed_at"] = max(filter(None, [p.get("last_observed_at"), fresh["last_observed_at"]]))
        merged.update(items=its, techs=tech_stack(its), blockers=distinct_blockers(its),
                      trend=activity_trend(its, now),
                      freshness=freshness(merged["first_published_at"], merged["last_published_at"], now),
                      discussed=sum(int(i.get("comments") or 0) for i in its),
                      source=its[0].get("source"), source_url=next((i["discussion_url"] for i in its if i.get("discussion_url")), None),
                      watched=bool(p.get("id")) and p.get("id") in (watched or set()))
        rows.append(merged)
    return rows


def in_period(p: dict, days: int, now: datetime) -> bool:
    if not days:
        return True
    since = now - timedelta(days=days)
    return any((d := parse_ts(i.get("posted_at"))) and d >= since for i in p["items"])


def search_text(p: dict) -> set[str]:
    return tokens(" ".join([p.get("project_name") or "", p.get("description") or "", p.get("category") or "",
                            p.get("builder_username") or "", p.get("current_focus") or "",
                            " ".join(t["name"] for t in p["techs"]),
                            " ".join(i.get("title_raw") or "" for i in p["items"][:5])]))


def filter_projects(projects: list[dict], f: dict, now: datetime) -> list[dict]:
    q = tokens(f.get("q"))
    out = []
    for p in projects:
        if not in_period(p, f.get("days", C.DEFAULT_PERIOD), now):
            continue
        if f.get("category") and p.get("category") != f["category"]:
            continue
        if f.get("tech") and f["tech"] not in {t["key"] for t in p["techs"]}:
            continue
        if f.get("source") and f["source"] not in {i.get("source") for i in p["items"]}:
            continue
        if f.get("stage") and p.get("build_stage") != f["stage"]:
            continue
        if f.get("fresh") and p["freshness"] != f["fresh"]:
            continue
        if f.get("blockers") == "yes" and not any(b["explicit"] for b in p["blockers"]):
            continue
        if f.get("blockers") == "no" and any(b["explicit"] for b in p["blockers"]):
            continue
        first = (p.get("first_seen_at") or "")[:10]
        if f.get("seen_from") and first < f["seen_from"]:
            continue
        if f.get("seen_to") and first > f["seen_to"]:
            continue
        if f.get("watch") and not p.get("watched"):
            continue
        if q:                                 # every search word must match the start of a word ("postg" finds Postgres)
            hay = search_text(p)
            if not all(any(h.startswith(t) for h in hay) for t in q):
                continue
        out.append(p)
    return out


SORTS = {"recent": "Recently observed", "discussed": "Most discussed", "growth": "Fastest-growing activity",
         "first_seen": "Newest first seen", "name": "Name"}


def sort_projects(rows: list[dict], how: str) -> list[dict]:
    if how == "discussed":
        return sorted(rows, key=lambda p: (-p["discussed"], p["project_name"].lower()))
    if how == "growth":   # only projects with a valid comparison are ranked; the rest follow by recency
        return sorted(rows, key=lambda p: (p["trend"]["status"] == "insufficient", -p["trend"]["delta"],
                                           -(parse_ts(p.get("last_published_at")) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
    if how == "first_seen":
        return sorted(rows, key=lambda p: p.get("first_seen_at") or "", reverse=True)
    if how == "name":
        return sorted(rows, key=lambda p: p["project_name"].lower())
    return sorted(rows, key=lambda p: (p.get("last_observed_at") or "", p.get("last_published_at") or ""), reverse=True)


def paginate(rows: list[dict], page: int, size: int = C.PAGE_SIZE) -> tuple[list[dict], int, int]:
    pages = max(1, -(-len(rows) // size))
    page = min(max(1, page), pages)
    return rows[(page - 1) * size: page * size], page, pages


# ---------- Trending Stack ----------
def period_windows(today: date, days: int) -> tuple[list[date], list[date]]:
    """(current weeks, previous weeks) of equal length, complete Friday-to-Thursday weeks only."""
    n = C.PERIOD_WEEKS.get(days or 30, 4)
    weeks = complete_weeks(today, 2 * n)
    return weeks[n:], weeks[:n]


def stack(projects: list[dict], today: date, days: int, group: str = "") -> dict:
    """Technologies by distinct projects mentioning them (explicitly) in the current vs previous period.

    Only Show HN observations count (sampled the same way every week), so periods are comparable.
    A percentage is only shown when the previous period had projects; otherwise the row says so."""
    cur_w, prev_w = period_windows(today, days)
    cur_set, prev_set = set(cur_w), set(prev_w)
    first_week = min((week_start(d.date()) for p in projects for i in p["items"]
                      if i.get("origin") == C.STACK_ORIGIN and (d := parse_ts(i.get("posted_at")))), default=None)
    covered = first_week is not None and first_week <= prev_w[0]
    rows: dict[str, dict] = {}
    for p in projects:
        for i in p["items"]:
            d = parse_ts(i.get("posted_at"))
            if i.get("origin") != C.STACK_ORIGIN or not d:
                continue
            w = week_start(d.date())
            for t in i.get("techs", []):
                if not t.get("explicit"):
                    continue
                r = rows.setdefault(t["key"], {"key": t["key"], "names": Counter(), "kind": t.get("kind"),
                                               "cur": set(), "prev": set(), "before": set(), "obs": 0, "examples": []})
                r["names"][t["name"]] += 1
                pid = p.get("id") or p["project_key"]
                if w in cur_set:
                    r["cur"].add(pid)
                    r["obs"] += 1
                    if len(r["examples"]) < 4 and p not in r["examples"]:
                        r["examples"].append(p)
                elif w in prev_set:
                    r["prev"].add(pid)
                elif w < prev_w[0]:
                    r["before"].add(pid)
    out = []
    for r in rows.values():
        cur, prev = len(r["cur"]), len(r["prev"])
        g = tech_group(r["key"], r["kind"])
        if group and g != group:
            continue
        if cur < C.STACK_MIN_PROJECTS and prev < C.STACK_MIN_PROJECTS:
            continue
        if not covered:
            status = "history"
        elif prev == 0:
            status = "new" if not r["before"] else "newly_observed"
        elif cur >= prev + 2 and cur >= prev * 1.5:
            status = "growing"
        elif prev >= 2 and cur * 2 <= prev:
            status = "declining"
        elif cur >= C.STACK_POPULAR and prev >= C.STACK_POPULAR:
            status = "popular"
        else:
            status = "steady"
        pct = round((cur - prev) * 100 / prev) if prev and covered else None
        out.append({"key": r["key"], "name": r["names"].most_common(1)[0][0], "group": g, "cur": cur, "prev": prev,
                    "obs": r["obs"], "pct": pct, "status": status, "examples": r["examples"]})
    order = {"new": 0, "growing": 1, "newly_observed": 2, "popular": 3, "steady": 4, "declining": 5, "history": 6}
    out.sort(key=lambda r: (order[r["status"]], -r["cur"], r["name"].lower()))
    return {"rows": out, "covered": covered, "cur_weeks": cur_w, "prev_weeks": prev_w, "first_week": first_week}


STACK_STATUS = {"new": ("✦", "New to DevvIT"), "newly_observed": ("✦", "Newly observed"),
                "growing": ("▲", "Growing in mentions"), "popular": ("■", "Consistently popular"),
                "steady": ("■", "Steady"), "declining": ("▼", "Declining in mentions"),
                "history": ("·", "Needs earlier data")}


# ---------- overview metrics ----------
def metrics(projects: list[dict], f: dict, now: datetime, trending: dict) -> dict:
    """The four summary cards, from the filtered projects. Each value counts distinct entities."""
    days = f.get("days", C.DEFAULT_PERIOD)
    since = now - timedelta(days=days) if days else None
    active_days = min(days, C.ACTIVE_BUILDER_DAYS) if days else C.ACTIVE_BUILDER_DAYS
    active_since = now - timedelta(days=active_days)
    builders, blockers = set(), set()
    for p in projects:
        for i in p["items"]:
            d = parse_ts(i.get("posted_at"))
            if i.get("author") and d and d >= active_since and i.get("origin") != "repo_release":
                builders.add((i.get("source"), i["author"].lower()))
        for b in p["blockers"]:
            d = parse_ts(b["item"].get("posted_at"))
            if b["explicit"] and (not since or (d and d >= since)):
                blockers.add((p.get("id") or p["project_key"], b["category"], " ".join(sorted(tokens(b.get("detail"))))))
    trend_n = sum(1 for r in trending["rows"] if r["status"] in {"new", "newly_observed", "growing"})
    return {"projects": len(projects), "builders": len(builders), "active_days": active_days,
            "trending": trend_n if trending["covered"] else None, "blockers": len(blockers)}


# ---------- Builder Challenges ----------
def challenges(projects: list[dict], days: int, now: datetime) -> dict:
    """Distinct blockers in the period grouped by category. Explicit reports and AI inferences are kept
    in separate lists and never counted together."""
    since = now - timedelta(days=days) if days else None
    groups: dict[str, dict] = {}
    inferred = []
    for p in projects:
        for b in p["blockers"]:
            d = parse_ts(b["item"].get("posted_at"))
            if since and (not d or d < since):
                continue
            row = {**b, "project": p}
            if not b["explicit"]:
                inferred.append(row)
                continue
            g = groups.setdefault(b["category"], {"category": b["category"],
                                                  "label": C.BLOCKER_CATEGORIES.get(b["category"], "Other"), "rows": []})
            g["rows"].append(row)
    ordered = sorted(groups.values(), key=lambda g: -len(g["rows"]))
    unmatched = sum(1 for g in ordered for r in g["rows"] if not r.get("pain_point") or r.get("link_status") == "rejected")
    return {"groups": ordered, "inferred": inferred, "unmatched": unmatched}


# ---------- pain point pages ----------
def builds_for_pain_point(label: str, items: list[dict]) -> list[dict]:
    """Build discussions connected to one pain point by evidence only: the discussion itself is tagged with
    the pain point, or one of its quoted blockers is linked to it (same thread, or a Gemini match with a
    stated reason). Shared keywords alone never connect them."""
    out = []
    for it in items:
        if it.get("pain_point") == label:
            out.append({"item": it, "basis": "Same thread is tagged with this pain point", "suggested": False})
            continue
        b = next((b for b in it.get("blockers", []) if b.get("pain_point") == label and b.get("link_status") != "rejected"), None)
        if b:
            out.append({"item": it, "suggested": b.get("link_method") == "ai_match" and b.get("link_status") != "confirmed",
                        "basis": f'Reported blocker “{b["detail"]}”' + (f': {b["link_basis"]}' if b.get("link_basis") else "")})
    return out
