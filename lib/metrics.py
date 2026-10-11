"""Trend math. Numbers come from here, not from the LLM."""
from collections import defaultdict
from datetime import date, timedelta

MIN_FOR_TREND = 3  # mention count below this = "low signal", no trend label


def week_start_for(d: date) -> date:
    """Weeks run Friday-to-Thursday. Return the Friday that starts the week
    containing d. (Friday weekday = 4.)"""
    delta = (d.weekday() - 4) % 7
    return d - timedelta(days=delta)


def aggregate(posts: list[dict]) -> dict[str, dict]:
    """Group posts by pain_point."""
    agg: dict[str, dict] = defaultdict(lambda: {
        "count": 0,
        "unresolved_count": 0,
        "engagement": 0,
        "category": "",
        "posts": [],
    })
    for p in posts:
        pp = p.get("pain_point")
        if not pp:
            continue
        a = agg[pp]
        a["count"] += 1
        if p.get("is_unresolved"):
            a["unresolved_count"] += 1
        a["engagement"] += int(p.get("score") or 0) + int(p.get("comments") or 0)
        a["category"] = p.get("category") or a["category"]
        a["posts"].append(p)
    return agg


def compute_trends(current: dict[str, dict], prev_counts: dict[str, int]) -> list[dict]:
    """Return list of trend rows sorted by count desc."""
    out = []
    for pp, a in current.items():
        prev = prev_counts.get(pp, 0)
        count = a["count"]
        if prev == 0:
            pct = 100.0 if count >= MIN_FOR_TREND else 0.0
            trend = "🆕 New" if count >= MIN_FOR_TREND else "— low signal"
        else:
            pct = (count - prev) / max(prev, 1) * 100
            if count < MIN_FOR_TREND:
                trend = "— low signal"
            elif pct > 20:
                trend = "📈 Rising"
            elif pct < -20:
                trend = "📉 Falling"
            else:
                trend = "→ Steady"
        out.append({
            "pain_point": pp,
            "category": a["category"],
            "count": count,
            "prev_count": prev,
            "change_pct": pct,
            "trend": trend,
            "unresolved_count": a["unresolved_count"],
            "engagement": a["engagement"],
            "posts": a["posts"],
        })
    out.sort(key=lambda x: (-x["count"], -x["engagement"]))
    return out
