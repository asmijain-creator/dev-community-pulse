"""Emerging pain-point radar.

Compares each theme's mentions in the latest week with its own baseline: the average of up to four
earlier weeks that have a brief. The rules are deliberately simple and explained on every finding;
they are heuristics, not statistical significance tests.
"""
from lib.evidence import evidence_level, group_labels, slug, sources_of, unique_threads

BASELINE_WEEKS = 4
MIN_THREADS = 2          # independent threads needed before anything is flagged
RISE_FACTOR = 2.0        # flagged as rising when this week >= 2x its baseline...
RISE_MIN_DELTA = 2       # ...and at least 2 more mentions than the baseline


def _next_step(kind: str, ev: str, unresolved: int, n: int) -> str:
    if ev == "Thin":
        return "Keep watching: check next week's brief before acting on it."
    if unresolved and unresolved >= n / 2:
        return "Read the open threads and line up 2-3 developer interviews: most of them have no working fix."
    if kind == "rising":
        return "Compare this week's threads with earlier ones to see what changed (a release, an outage, a new tool)."
    return "Read the threads, write a one-line problem statement and decide whether to add it to the watchlist."


def find_signals(weeks: list[str], metrics: list[dict], latest_posts: list[dict], states: dict | None = None) -> dict:
    """
    weeks:        weeks that have a brief, oldest first (latest last)
    metrics:      weekly_metrics rows for those weeks
    latest_posts: tagged posts of the latest week (with pain_point)
    states:       {finding_key: radar_state row} for relevant / dismissed / monitored
    """
    states = states or {}
    if not weeks:
        return {"findings": [], "latest": None, "baseline_weeks": [], "history_ok": False}
    latest, base_weeks = weeks[-1], weeks[:-1][-BASELINE_WEEKS:]

    # Theme grouping: most-mentioned labels first so they become the canonical names.
    totals: dict[str, int] = {}
    for m in metrics:
        totals[m["pain_point"]] = totals.get(m["pain_point"], 0) + (m.get("mention_count") or 0)
    canon = group_labels(sorted(totals, key=lambda k: -totals[k]))

    series: dict[str, dict[str, int]] = {}
    unresolved: dict[str, int] = {}
    for m in metrics:
        c = canon.get(m["pain_point"], m["pain_point"])
        series.setdefault(c, {})
        series[c][m["week_start"]] = series[c].get(m["week_start"], 0) + (m.get("mention_count") or 0)
        if m["week_start"] == latest:
            unresolved[c] = unresolved.get(c, 0) + (m.get("unresolved_count") or 0)
    posts_by: dict[str, list[dict]] = {}
    for p in latest_posts:
        if p.get("pain_point"):
            posts_by.setdefault(canon.get(p["pain_point"], p["pain_point"]), []).append(p)

    findings = []
    for label, per_week in series.items():
        cur = per_week.get(latest, 0)
        threads = unique_threads(posts_by.get(label, []))
        n = len(threads)
        if cur == 0 or n < MIN_THREADS:
            continue
        first_seen = min(w for w, v in per_week.items() if v)
        base = (sum(per_week.get(w, 0) for w in base_weeks) / len(base_weeks)) if base_weeks else None

        if base is None:
            kind, reason = "baseline_pending", (
                f"{n} independent threads this week. There is no earlier brief yet, so it can't be compared "
                f"with a baseline.")
        elif first_seen == latest:
            kind, reason = "new", (
                f"First seen this week: {n} independent threads, and no mentions in the previous "
                f"{len(base_weeks)} week{'s' if len(base_weeks) != 1 else ''} with a brief.")
        elif base > 0 and cur >= RISE_FACTOR * base and cur - base >= RISE_MIN_DELTA:
            kind, reason = "rising", (
                f"{cur} mentions this week vs an average of {base:.1f} over the previous {len(base_weeks)} "
                f"week{'s' if len(base_weeks) != 1 else ''} ({cur / base:.1f}x).")
        elif base == 0:
            kind, reason = "returning", (
                f"Back after being quiet: {cur} mentions this week and none in the previous {len(base_weeks)} "
                f"week{'s' if len(base_weeks) != 1 else ''}; first seen {first_seen}.")
        else:
            continue

        srcs = sources_of(threads)
        ev = evidence_level(n, len(srcs))
        key = slug(label)
        state = states.get(key) or {}
        findings.append({
            "key": key, "label": label, "kind": kind, "reason": reason,
            "first_seen": first_seen, "current": cur, "baseline": base, "unique_threads": n,
            "duplicates_merged": sum(t.get("duplicates", 0) for t in threads),
            "sources": srcs, "evidence": ev, "unresolved": unresolved.get(label, 0),
            "direction": "new" if kind in ("new", "baseline_pending") else "up",
            "series": [per_week.get(w, 0) for w in weeks],
            "threads": threads[:5], "next_step": _next_step(kind, ev["level"], unresolved.get(label, 0), n),
            "status": state.get("status", "new"),
            "members": sorted(k for k, v in canon.items() if v == label),
        })
    order = {"new": 0, "rising": 1, "returning": 2, "baseline_pending": 3}
    findings.sort(key=lambda f: (order[f["kind"]], -f["unique_threads"], -f["current"]))
    return {"findings": findings, "latest": latest, "baseline_weeks": base_weeks, "history_ok": bool(base_weeks)}
