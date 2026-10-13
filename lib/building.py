"""Building Now: what developers are publicly building. Pure logic, no database or network.

- `validate` turns one Gemini classification into stored rows, checking every "explicit" claim against the
  post text: names, stages, quotes and technologies that don't appear in the post are dropped or labelled
  as AI inferences.
- `top_counts` and `freshness` are small helpers; projects, trends and pain point links live in
  lib.build_projects. Counts are of distinct projects and discussions, never of users or installs.
"""
import re
from datetime import date, datetime, timedelta, timezone

from lib import build_config as C


CATEGORIES = ["AI agents & LLM apps", "Developer tools", "Web apps", "Mobile apps", "Data & analytics",
              "Infrastructure & DevOps", "Security", "Open-source libraries", "Games & creative",
              "Hardware & IoT", "Productivity", "Other"]
ACTIVITY = {"side_project": "Side project", "product": "Product", "prototype": "Prototype",
            "open_source": "Open source", "experiment": "Experiment", "tool": "Tool", "other": "Other"}
# Stages Gemini may return now; older stored values (alpha_beta, maintained) are still accepted and mapped
# for display by lib.build_projects.stage_of.
STAGES = {"idea": "Idea", "prototype": "Prototype", "mvp": "MVP", "beta": "Beta", "launched": "Launched"}
LEGACY_STAGES = {"alpha_beta": "Alpha / beta", "maintained": "Maintained"}
BLOCKERS = dict(C.BLOCKER_CATEGORIES)
LEGACY_BLOCKERS = {"integration", "api_limits", "tool_reliability", "testing_debugging", "ai_agent_reliability"}
EVENTS = [e for e in C.EVENTS if e != "unclear"]
TECH_KINDS = {"framework", "language", "api", "ai_model", "dev_tool", "infrastructure", "database", "other"}
MIN_CONFIDENCE = 0.5

# Threads already in DevvIT (collected for pain points) that look like someone sharing what they build.
# Only these are sent to Gemini, so ordinary questions and bug reports cost no AI calls.
_BUILD_HINT = re.compile(
    r"\b(show hn|launch hn|side project|weekend project|hobby project|my project|prototype|"
    r"(i|we)(\s+just|\s+finally)?\s+(built|made|created|wrote|launched|released|shipped|open[- ]sourced)|"
    r"(i'?m|i am|we'?re|we are)\s+(building|making|working on|developing))\b", re.I)


def looks_like_build(title: str | None, body: str | None) -> bool:
    return bool(_BUILD_HINT.search(f"{title or ''}\n{(body or '')[:1500]}"))


# ---------- text checks ----------
def _norm(s: str | None) -> str:
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(s.lower().split())


def verbatim(quote: str | None, text: str, min_len: int = 12) -> bool:
    """True when `quote` appears in the post text (case and whitespace ignored)."""
    q = _norm(quote).strip(" .\"'…")
    return len(q) >= min_len and q in _norm(text)


def tech_key(name: str) -> str:
    """'Next.js', 'NextJS' and 'next js' -> 'nextjs'. Keeps + and # (C++, C#)."""
    return re.sub(r"[^a-z0-9+#]", "", (name or "").lower())[:60]


def mentioned(name: str, text: str) -> bool:
    """The technology's name (or its spacing/punctuation variant) appears in the text."""
    n = _norm(name)
    if not n:
        return False
    t = _norm(text)
    if re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", t):
        return True
    k = tech_key(name)
    return len(k) >= 3 and k in tech_key(text)


def _clip(s: str | None, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


# ---------- classification -> rows ----------
def validate(c: dict, post: dict, model: str) -> tuple[dict, list[dict], list[dict]]:
    """Check one Gemini classification against the post it describes.

    Returns (item row, technology rows, blocker rows). Nothing the model says is stored as a fact unless
    the post supports it: project names must appear in the post, stage needs a verbatim quote, the excerpt
    must be verbatim, and technologies/blockers not found in the text are marked explicit=False."""
    text = f"{post.get('title') or ''}\n{post.get('body') or ''}"
    conf = c.get("confidence")
    conf = max(0.0, min(1.0, float(conf))) if isinstance(conf, (int, float)) else None
    reason = (c.get("exclusion_reason") or "").strip().lower() or None
    relevant = bool(c.get("is_build_activity")) and reason not in {"advertisement", "job_post"}
    if relevant and (conf is None or conf < MIN_CONFIDENCE):
        relevant, reason = False, "low_confidence"
    if not relevant and not reason:
        reason = "not_build"

    item = {
        "discussion_id": post["id"], "source": post["source"], "origin": post["origin"],
        "discussion_url": post["discussion_url"], "project_url": post.get("project_url"),
        "title_raw": _clip(post.get("title"), 500) or "Untitled", "posted_at": post["created_at"],
        "score": int(post.get("score") or 0), "comments": int(post.get("comments") or 0),
        "in_posts": bool(post.get("in_posts")), "relevant": relevant,
        "author": post.get("author") or None, "author_url": post.get("author_url") or None,
        "exclusion_reason": None if relevant else reason, "confidence": conf, "model": model,
        "classified_at": datetime.now(timezone.utc).isoformat(),
        # every row carries every column, so a bulk insert never sends NULL to a NOT NULL column
        "activity_type": None, "project_title": None, "title_is_ai": False, "summary": None, "category": None,
        "stage": None, "stage_quote": None, "excerpt": None,
        "event_type": None, "event_quote": None, "focus": None, "focus_quote": None, "enriched_at": None,
    }
    if not relevant:
        return item, [], []

    name = _clip(c.get("project_name"), 120)
    named = bool(name) and _norm(name) in _norm(text)
    title = name if named else _clip(c.get("descriptive_title"), 120) or _clip(post.get("title"), 120)
    stage = c.get("stage") if c.get("stage") in STAGES or c.get("stage") in LEGACY_STAGES else None
    stage_quote = _clip(c.get("stage_evidence"), 300)
    if not (stage and verbatim(stage_quote, text, 6)):
        stage, stage_quote = None, None
    excerpt = _clip(c.get("excerpt"), 400)
    item.update({
        "activity_type": c.get("activity_type") if c.get("activity_type") in ACTIVITY else "other",
        "project_title": title, "title_is_ai": not named,
        "summary": _clip(c.get("summary"), 400) or None,
        "category": c.get("category") if c.get("category") in CATEGORIES else "Other",
        "stage": stage, "stage_quote": stage_quote,
        "excerpt": excerpt if verbatim(excerpt, text) else None,
        **validate_event(c, text),
    })

    techs, seen = [], set()
    for t in c.get("technologies") or []:
        nm = _clip((t or {}).get("name"), 60)
        k = tech_key(nm)
        if len(k) < 1 or k in seen:
            continue
        seen.add(k)
        techs.append({"discussion_id": post["id"], "name": nm, "key": k,
                      "kind": t.get("type") if t.get("type") in TECH_KINDS else "other",
                      "explicit": mentioned(nm, text)})
    blockers = []
    for b in c.get("blockers") or []:
        detail = _clip((b or {}).get("detail"), 300)
        if not detail:
            continue
        quote = _clip(b.get("evidence"), 300)
        ok = verbatim(quote, text)
        kind = b.get("type") if b.get("type") in BLOCKERS or b.get("type") in LEGACY_BLOCKERS else "other"
        blockers.append({"discussion_id": post["id"], "kind": kind,
                         "detail": detail, "quote": quote if ok else None, "explicit": ok})
    return item, techs[:12], blockers[:6]


def validate_event(c: dict, text: str) -> dict:
    """What kind of public update a post is and what the builder says they're working on now. Each is kept
    only with words copied from the post that support it; otherwise 'unclear' / no focus."""
    ev, ev_q = c.get("event_type"), _clip(c.get("event_evidence"), 300)
    ok = ev in EVENTS and verbatim(ev_q, text, 6)
    focus, focus_q = _clip(c.get("current_focus"), 160), _clip(c.get("focus_evidence"), 300)
    has_focus = bool(focus) and verbatim(focus_q, text)
    return {"event_type": ev if ok else "unclear", "event_quote": ev_q if ok else None,
            "focus": focus if has_focus else None, "focus_quote": focus_q if has_focus else None,
            "enriched_at": datetime.now(timezone.utc).isoformat()}


# ---------- weeks ----------
def week_start(d: date) -> date:
    """DevvIT weeks run Friday to Thursday, like the weekly briefs."""
    return d - timedelta(days=(d.weekday() - 4) % 7)


def complete_weeks(today: date, n: int = 4) -> list[date]:
    """The last n weeks that have fully ended, oldest first. The current, partial week is never included."""
    last = week_start(today) - timedelta(days=7)
    return [last - timedelta(days=7 * i) for i in range(n - 1, -1, -1)]


def _day(iso: str | None) -> date | None:
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00")).date()
    except ValueError:
        return None


# ---------- counts ----------
def top_counts(items: list[dict], kind: str, n: int = 10) -> list[dict]:
    """Most common categories ('category') or explicitly mentioned technologies ('tech'), by discussions."""
    counts: dict[str, dict] = {}
    for it in items:
        if kind == "category":
            keys = [(it.get("category") or "Other", it.get("category") or "Other")]
        else:
            keys = [(t["key"], t["name"]) for t in it.get("techs", []) if t["explicit"]]
        for k, label in keys:
            c = counts.setdefault(k, {"key": k, "label": label, "n": 0, "names": {}})
            c["n"] += 1
            c["names"][label] = c["names"].get(label, 0) + 1
    for c in counts.values():
        c["label"] = max(c.pop("names").items(), key=lambda x: x[1])[0]   # most common spelling
    return sorted(counts.values(), key=lambda c: (-c["n"], c["label"].lower()))[:n]


# ---------- freshness ----------
def freshness(items: list[dict], refreshes: list[dict], now: datetime) -> dict:
    last = refreshes[0] if refreshes else None
    classified = max((it.get("classified_at") or "" for it in items), default="") or None
    newest = max((it.get("posted_at") or "" for it in items if it.get("relevant")), default="") or None
    when = (last or {}).get("finished_at") or (last or {}).get("started_at") or classified
    age = None
    if when:
        try:
            age = (now - datetime.fromisoformat(when.replace("Z", "+00:00"))).days
        except ValueError:
            age = None
    return {"last_update": when, "age_days": age, "stale": age is not None and age > 8,
            "newest_post": newest, "last": last}
