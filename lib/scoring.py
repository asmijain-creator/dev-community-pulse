"""Transparent opportunity score.

Every factor is a number from 0 to 1 that is shown next to the score, and the weights can be changed
by the user. The score ranks where to look first; community discussion volume is not evidence of
willingness to pay or market size.
"""
from statistics import median

from lib.evidence import engagement, opinion_mix, sources_of, unique_threads

FACTORS = {
    "frequency":  "Mentions this week, relative to the most-mentioned pain point",
    "growth":     "Increase over its baseline (average of up to 4 earlier weeks), capped at 3x",
    "severity":   "Share of negative threads, plus how much engagement the threads get",
    "unresolved": "Share of threads with no working fix",
    "diversity":  "Independent threads (5 or more = full) and number of sources (3 = full)",
}
DEFAULT_WEIGHTS = {k: 1.0 for k in FACTORS}


def parse_weights(params: dict) -> dict[str, float]:
    """Weights from query parameters like w_growth=2. Each is clamped to 0-3."""
    out = dict(DEFAULT_WEIGHTS)
    for k in FACTORS:
        try:
            out[k] = max(0.0, min(3.0, float(params.get(f"w_{k}", out[k]))))
        except (TypeError, ValueError):
            pass
    return out


def factors(cur: int, max_cur: int, base: float | None, posts: list[dict]) -> dict:
    threads = unique_threads(posts)
    n = len(threads)
    mix = opinion_mix(threads)
    neg_share = mix["negative"] / n if n else 0.0
    eng = median(engagement(t) for t in threads) if threads else 0
    return {
        "frequency": cur / max_cur if max_cur else 0.0,
        "growth": None if base is None else min(max((cur - base) / max(base, 1.0), 0.0), 3.0) / 3.0,
        "severity": 0.5 * neg_share + 0.5 * min(eng / 50.0, 1.0),
        "unresolved": (sum(1 for t in threads if t.get("is_unresolved")) / n) if n else 0.0,
        "diversity": 0.5 * min(n / 5.0, 1.0) + 0.5 * min(len(sources_of(threads)) / 3.0, 1.0),
        "_threads": n, "_sources": sources_of(threads), "_mixed": mix["mixed"],
    }


def score(f: dict, weights: dict[str, float]) -> float | None:
    """Weighted average of the available factors, 0-100. Growth is skipped when there's no baseline."""
    used = [(weights[k], f[k]) for k in FACTORS if f.get(k) is not None and weights.get(k, 0) > 0]
    total = sum(w for w, _ in used)
    return round(100 * sum(w * v for w, v in used) / total, 1) if total else None
