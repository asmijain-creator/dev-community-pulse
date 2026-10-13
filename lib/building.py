"""Building Now: what developers are publicly building. Pure logic, no database or network.

- `validate` turns one Gemini classification into stored rows, checking every "explicit" claim against the
  post text: names, stages, quotes and technologies that don't appear in the post are dropped or labelled
  as AI inferences.
- `summarise`, `trends`, `blocker_groups` and the pain point matchers compute every number on the page
  from stored rows. Counts are of discussions, never of users or installs.
"""
import re
from datetime import date, datetime, timedelta, timezone

from lib.evidence import tokens

CATEGORIES = ["AI agents & LLM apps", "Developer tools", "Web apps", "Mobile apps", "Data & analytics",
              "Infrastructure & DevOps", "Security", "Open-source libraries", "Games & creative",
              "Hardware & IoT", "Productivity", "Other"]
ACTIVITY = {"side_project": "Side project", "product": "Product", "prototype": "Prototype",
            "open_source": "Open source", "experiment": "Experiment", "tool": "Tool", "other": "Other"}
STAGES = {"idea": "Idea", "prototype": "Prototype", "alpha_beta": "Alpha / beta", "launched": "Launched",
          "maintained": "Maintained"}
BLOCKERS = {"integration": "Integration difficulties", "deployment": "Deployment failures",
            "api_limits": "API limitations", "tool_reliability": "Tool reliability",
            "performance": "Performance problems", "testing_debugging": "Testing and debugging",
            "ai_agent_reliability": "AI agent reliability", "code_review": "Code review problems",
            "other": "Other blockers"}
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
        "exclusion_reason": None if relevant else reason, "confidence": conf, "model": model,
        "classified_at": datetime.now(timezone.utc).isoformat(),
        # every row carries every column, so a bulk insert never sends NULL to a NOT NULL column
        "activity_type": None, "project_title": None, "title_is_ai": False, "summary": None, "category": None,
        "stage": None, "stage_quote": None, "excerpt": None,
    }
    if not relevant:
        return item, [], []

    name = _clip(c.get("project_name"), 120)
    named = bool(name) and _norm(name) in _norm(text)
    title = name if named else _clip(c.get("descriptive_title"), 120) or _clip(post.get("title"), 120)
    stage = c.get("stage") if c.get("stage") in STAGES else None
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
        blockers.append({"discussion_id": post["id"], "kind": b.get("type") if b.get("type") in BLOCKERS else "other",
                         "detail": detail, "quote": quote if ok else None, "explicit": ok})
    return item, techs[:12], blockers[:6]


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


# ---------- filtering ----------
def apply_filters(items: list[dict], f: dict, today: date) -> list[dict]:
    """Filter relevant items by period, category, technology, source, blocker kind and search words."""
    days = f.get("days")
    since = today - timedelta(days=days) if days else None
    q = tokens(f.get("q"))
    out = []
    for it in items:
        d = _day(it.get("posted_at"))
        if since and (not d or d < since):
            continue
        if f.get("category") and it.get("category") != f["category"]:
            continue
        if f.get("source") and it.get("source") != f["source"]:
            continue
        if f.get("tech") and f["tech"] not in {t["key"] for t in it.get("techs", [])}:
            continue
        if f.get("blocker") and f["blocker"] not in {b["kind"] for b in it.get("blockers", [])}:
            continue
        if q:
            hay = tokens(" ".join([it.get("project_title") or "", it.get("title_raw") or "", it.get("summary") or "",
                                   it.get("category") or "", " ".join(t["name"] for t in it.get("techs", [])),
                                   " ".join(b["detail"] for b in it.get("blockers", []))]))
            if not q & hay:
                continue
        out.append(it)
    return out


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


def blocker_groups(items: list[dict]) -> list[dict]:
    """Blockers grouped by kind. Only blockers quoted verbatim from a post are counted."""
    groups: dict[str, dict] = {}
    for it in items:
        for b in it.get("blockers", []):
            if not b["explicit"]:
                continue
            g = groups.setdefault(b["kind"], {"kind": b["kind"], "label": BLOCKERS.get(b["kind"], b["kind"]),
                                              "n": 0, "examples": []})
            g["n"] += 1
            g["examples"].append({**b, "item": it})
    return sorted(groups.values(), key=lambda g: -g["n"])


def trends(items: list[dict], today: date, kind: str, weeks: int = 4, min_total: int = 3) -> dict:
    """Week-by-week discussion counts for technologies or categories over complete weeks.

    Status compares the latest complete week with the average of the earlier ones:
      new       - seen 2+ times in the latest week and never in earlier weeks (needs earlier weeks with data)
      growing   - latest >= 1.5x the earlier average and at least 2 more discussions
      declining - earlier average >= 2 and latest <= half of it
      stable    - everything else with enough discussions
    Rules of thumb on discussion counts, not statistical tests and not adoption."""
    wk = complete_weeks(today, weeks)
    idx = {w: i for i, w in enumerate(wk)}
    totals = [0] * len(wk)
    series: dict[str, dict] = {}
    for it in items:
        d = _day(it.get("posted_at"))
        w = week_start(d) if d else None
        if w not in idx:
            continue
        i = idx[w]
        totals[i] += 1
        if kind == "category":
            keys = {(it.get("category") or "Other", it.get("category") or "Other")}
        else:
            keys = {(t["key"], t["name"]) for t in it.get("techs", []) if t["explicit"]}
        for k, label in keys:
            s = series.setdefault(k, {"key": k, "label": label, "counts": [0] * len(wk)})
            s["counts"][i] += 1
    earlier_with_data = sum(1 for t in totals[:-1] if t)
    rows = []
    for s in series.values():
        c = s["counts"]
        last, before = c[-1], c[:-1]
        avg = sum(before) / len(before) if before else 0
        if sum(c) < min_total and not (last >= 2 and not any(before)):
            continue
        if not totals[-1] or earlier_with_data == 0:
            status = "pending"
        elif last >= 2 and not any(before):
            status = "new"
        elif last >= 1.5 * avg and last - avg >= 2:
            status = "growing"
        elif avg >= 2 and last <= avg / 2:
            status = "declining"
        else:
            status = "stable"
        rows.append({**s, "status": status, "last": last, "avg": avg, "total": sum(c)})
    order = {"new": 0, "growing": 1, "declining": 2, "stable": 3, "pending": 4}
    rows.sort(key=lambda r: (order[r["status"]], -r["last"], -r["total"]))
    return {"weeks": [w.isoformat() for w in wk], "totals": totals, "rows": rows,
            "history_ok": bool(totals[-1]) and earlier_with_data > 0}


def theme_keys(trend: dict, which: str) -> set[str]:
    """Keys that are emerging (new or growing in the latest complete week) or recurring (seen in 2+ earlier weeks)."""
    if which == "emerging":
        return {r["key"] for r in trend["rows"] if r["status"] in {"new", "growing"}}
    if which == "recurring":
        return {r["key"] for r in trend["rows"] if sum(1 for x in r["counts"][:-1] if x) >= 2}
    return set()


# ---------- connections to pain points ----------
def _stems(text: str) -> set[str]:
    return {t[:-1] if len(t) > 4 and t.endswith("s") else t for t in tokens(text)}


def overlap(a: str, b: str) -> list[str]:
    return sorted(_stems(a) & _stems(b))


def match_pain_point(blocker: dict, labels: list[str]) -> tuple[str, list[str]] | None:
    """The pain point label sharing the most words (at least 2) with a blocker. A suggestion, shown as such."""
    best = None
    for label in labels:
        shared = overlap(f"{blocker['detail']} {blocker.get('quote') or ''}", label)
        if len(shared) >= 2 and (best is None or len(shared) > len(best[1])):
            best = (label, shared)
    return best


def builds_for_pain_point(label: str, items: list[dict]) -> list[dict]:
    """Build discussions related to one pain point, each with the reason:
    'same thread' (the discussion itself is tagged with this pain point), a blocker sharing 2+ words
    with the label, or an explicitly mentioned technology whose name is in the label."""
    out = []
    lab_norm = _norm(label)
    for it in items:
        if it.get("pain_point") == label:
            out.append({"item": it, "basis": "Same thread is tagged with this pain point", "suggested": False})
            continue
        hit = next(((b, s) for b in it.get("blockers", []) if b["explicit"]
                    for s in [overlap(f"{b['detail']} {b.get('quote') or ''}", label)] if len(s) >= 2), None)
        if hit:
            out.append({"item": it, "suggested": True,
                        "basis": f"Reported blocker shares the words: {', '.join(hit[1])}"})
            continue
        tech = next((t for t in it.get("techs", []) if t["explicit"] and len(t["key"]) >= 3
                     and mentioned(t["name"], lab_norm)), None)
        if tech:
            out.append({"item": it, "suggested": True, "basis": f"Mentions {tech['name']}, which is named in this pain point"})
    return out


def pain_points_for_tech(name: str, threads: list[dict], n: int = 6) -> list[dict]:
    """Pain points whose threads mention a technology by name, with the number of threads that do."""
    counts: dict[str, list[dict]] = {}
    for t in threads:
        if t.get("pain_point") and mentioned(name, f"{t.get('title') or ''} {t.get('body') or ''}"):
            counts.setdefault(t["pain_point"], []).append(t)
    return sorted(({"pain_point": k, "threads": v} for k, v in counts.items()), key=lambda r: -len(r["threads"]))[:n]


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
