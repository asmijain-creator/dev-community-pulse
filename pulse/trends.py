"""Turns the SQL week-over-week counts into labelled trends. Pure functions, no AI."""

MIN_MENTIONS_FOR_TREND = 3   # 1 -> 3 is "+200%" but not a trend
CHANGE_THRESHOLD_PCT = 25


def change_pct(current: int, previous: int) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def label_trend(current: int, previous: int, newly_tracked: bool = False) -> str:
    if newly_tracked and previous == 0:
        return "newly tracked"
    if current == 0 and previous > 0:
        return "gone quiet"
    if previous == 0:
        return "new"
    if max(current, previous) < MIN_MENTIONS_FOR_TREND:
        return "steady"
    pct = change_pct(current, previous)
    if pct >= CHANGE_THRESHOLD_PCT:
        return "rising"
    if pct <= -CHANGE_THRESHOLD_PCT:
        return "falling"
    return "steady"


def build_metrics(rows: list[dict], new_categories: set[str]) -> list[dict]:
    """rows come from the pain_point_trends() SQL function."""
    metrics = []
    for row in rows:
        cur, prev = int(row["mentions"]), int(row["prev_mentions"])
        metrics.append({
            "category": row["category"],
            "pain_point": row["pain_point"],
            "mentions": cur,
            "prev_mentions": prev,
            "change_pct": change_pct(cur, prev),
            "trend": label_trend(cur, prev, row["category"] in new_categories),
            "engagement": int(row["engagement"]),
            "unresolved": int(row["unresolved"]),
        })
    # Most-discussed first; engagement breaks ties so one viral post can't outrank many mentions.
    metrics.sort(key=lambda m: (m["mentions"], m["engagement"]), reverse=True)
    return metrics
