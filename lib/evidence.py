"""Evidence helpers: independent threads, near-duplicates, evidence sufficiency, opinion mix, label grouping.

Pure functions (no database, no AI) so they are cheap to run on every page and easy to test.
"""
import re

_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "your", "you", "are", "how", "what", "why", "when",
    "can", "not", "but", "has", "have", "into", "about", "after", "before", "does", "doesn", "don", "using",
    "use", "any", "all", "our", "out", "its", "was", "were", "will", "should", "would", "could", "there",
    "ask", "show", "tell", "feature", "request", "issue", "bug",
}
NEAR_DUPLICATE = 0.8      # title token overlap at which two threads count as the same discussion
SAME_THEME = 0.6          # label token overlap at which two pain point labels are the same theme


def tokens(text: str | None) -> frozenset[str]:
    return frozenset(t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2 and t not in _STOP)


def jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def engagement(p: dict) -> int:
    return int(p.get("score") or 0) + int(p.get("comments") or 0)


def unique_threads(posts: list[dict]) -> list[dict]:
    """Collapse reposts and near-duplicate threads so they don't count as independent confirmation.

    Two posts are the same discussion if they share a URL or their titles overlap >= NEAR_DUPLICATE.
    The most-engaged copy is kept; `duplicates` on it says how many copies were merged into it."""
    kept: list[tuple[dict, frozenset]] = []
    for p in sorted(posts, key=engagement, reverse=True):
        tk, url = tokens(p.get("title")), (p.get("url") or "").rstrip("/")
        twin = next((k for k, ktk in kept
                     if (url and url == (k.get("url") or "").rstrip("/")) or jaccard(tk, ktk) >= NEAR_DUPLICATE), None)
        if twin is not None:
            twin["duplicates"] = twin.get("duplicates", 0) + 1
            continue
        kept.append(({**p, "duplicates": 0}, tk))
    return [k for k, _ in kept]


def sources_of(posts: list[dict]) -> list[str]:
    return sorted({(p.get("source") or "unknown").lower() for p in posts})


def evidence_level(n_threads: int, n_sources: int) -> dict:
    """How much independent evidence there is. A sufficiency label, not a statistical confidence."""
    if n_threads >= 5 and n_sources >= 2:
        return {"level": "Strong", "why": f"{n_threads} independent threads across {n_sources} sources"}
    if n_threads >= 3:
        return {"level": "Moderate", "why": f"{n_threads} independent threads"
                + ("" if n_sources > 1 else ", all from one source")}
    return {"level": "Thin", "why": f"only {n_threads} independent thread{'s' if n_threads != 1 else ''}: treat as a lead, not a finding"}


def opinion_mix(posts: list[dict]) -> dict:
    """Sentiment split. 'Mixed' when developers clearly disagree (both positive and negative threads)."""
    counts = {"negative": 0, "neutral": 0, "positive": 0, "unknown": 0}
    for p in posts:
        counts[p.get("sentiment") if p.get("sentiment") in counts else "unknown"] += 1
    return {**counts, "mixed": counts["positive"] > 0 and counts["negative"] > 0}


def group_labels(labels: list[str]) -> dict[str, str]:
    """Map each pain point label to a canonical label so near-identical themes are counted once.

    Labels are grouped when their word overlap is >= SAME_THEME (e.g. 'ai generated code review fatigue'
    and 'fatigue from reviewing ai generated code'). The first label in the input order (callers pass
    them most-mentioned first) becomes the canonical name."""
    canon: dict[str, str] = {}
    reps: list[tuple[str, frozenset]] = []
    for label in labels:
        tk = tokens(label)
        match = next((r for r, rtk in reps if jaccard(tk, rtk) >= SAME_THEME), None)
        if match is None:
            reps.append((label, tk))
            match = label
        canon[label] = match
    return canon


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:120]
