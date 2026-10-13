"""Build the frozen content of a shared report from what DevvIT has stored.

Rules: only stored data and DevvIT's own calculations are used. Missing values are left out or marked
unavailable, never estimated. AI text (from a saved opportunity analysis) is kept separate and labelled.
Private notes, opportunity status, internal ids and admin details are never included.
"""
from datetime import datetime, timezone

from lib import radar, scoring
from lib.evidence import evidence_level, opinion_mix, sources_of, unique_threads
from lib.sharing import safe_url

SNAPSHOT_VERSION = 1
_SRC = {"hn": "Hacker News", "hackernews": "Hacker News", "so": "Stack Overflow", "stackoverflow": "Stack Overflow",
        "gh": "GitHub", "github": "GitHub"}
_ACR = {"ai", "llm", "llms", "ci", "cd", "pr", "prs", "api", "apis", "ui", "ide", "sdk", "cli", "sql", "aws", "gpu", "mcp"}


def nice(label: str) -> str:
    words = [w.upper() if w in _ACR else w for w in (label or "").split()]
    s = " ".join(words)
    return s[:1].upper() + s[1:]


def _plural(n: int, w: str) -> str:
    return f"{n} {w}{'' if n == 1 else 's'}"


def load_context(sb) -> dict:
    """Data shared by every section: recent briefs, weekly counts and the latest week's tagged threads."""
    hist = sb.table("digests").select("week_start,created_at").order("week_start", desc=True).limit(12).execute().data or []
    weeks = sorted(h["week_start"] for h in hist)[-6:]
    metrics = (sb.table("weekly_metrics").select("week_start,pain_point,category,mention_count,unresolved_count,engagement")
               .in_("week_start", weeks).execute().data or []) if weeks else []
    posts = (sb.table("posts").select("id,source,title,url,score,comments,created_at,is_unresolved,sentiment,category,pain_point,week_start")
             .eq("week_start", weeks[-1]).not_.is_("pain_point", "null").limit(500).execute().data or []) if weeks else []
    return {"hist": hist, "weeks": weeks, "metrics": metrics, "posts": posts,
            "data_updated_at": hist[0].get("created_at") if hist else None}


def _thread(t: dict) -> dict | None:
    url = safe_url(t.get("url"))
    if not url:
        return None
    return {"title": " ".join((t.get("title") or "Untitled thread").split())[:200], "url": url,
            "source": _SRC.get((t.get("source") or "").lower(), t.get("source") or "Source"),
            "date": (t.get("created_at") or "")[:10], "score": int(t.get("score") or 0),
            "comments": int(t.get("comments") or 0), "unresolved": bool(t.get("is_unresolved"))}


def _claims(items) -> list[dict]:
    out = []
    for c in items or []:
        ev = [{"title": e.get("title") or "", "url": e["url"]} for e in c.get("evidence") or [] if safe_url(e.get("url"))]
        if c.get("text") and ev:
            out.append({"text": c["text"], "evidence": ev})
    return out


def _insight(sb, name: str, week: str | None) -> dict | None:
    """The saved Gemini analysis for this pain point and week, if one was generated (migration 002)."""
    if not week:
        return None
    try:
        rows = sb.table("opportunity_insights").select("content,created_at").eq("pain_point", name) \
            .eq("week_start", week).limit(1).execute().data
    except Exception:
        return None
    return {**rows[0]["content"], "_created_at": rows[0]["created_at"]} if rows else None


def pain_point(sb, name: str, ctx: dict) -> dict | None:
    weeks = ctx["weeks"]
    rows = sb.table("weekly_metrics").select("week_start,category,mention_count,unresolved_count,engagement") \
        .eq("pain_point", name).order("week_start", desc=True).limit(52).execute().data or []
    if not rows:
        return None
    by_week = {r["week_start"]: r for r in rows}
    cur = rows[0]
    week = cur["week_start"]
    axis = [w for w in weeks if w <= week] or [week]
    series = [{"week": w, "mentions": (by_week.get(w) or {}).get("mention_count", 0)} for w in axis]
    prev_week = next((w for w in reversed(axis[:-1])), None)
    prev = (by_week.get(prev_week) or {}).get("mention_count", 0) if prev_week else None
    n, u = cur["mention_count"], cur.get("unresolved_count") or 0
    raw = sb.table("posts").select("source,title,url,score,comments,created_at,is_unresolved,sentiment") \
        .eq("pain_point", name).order("created_at", desc=True).limit(200).execute().data or []
    uniq = unique_threads(raw)
    srcs = sorted({_SRC.get((t.get("source") or "").lower(), t.get("source") or "") for t in uniq} - {""})
    ev = evidence_level(len(uniq), len(srcs))
    mix = opinion_mix(uniq)
    dates = sorted((t.get("created_at") or "")[:10] for t in raw if t.get("created_at"))
    threads = [x for x in (_thread(t) for t in sorted(uniq, key=lambda t: -(int(t.get("score") or 0) + int(t.get("comments") or 0)))) if x][:8]

    if prev is None:
        trend, trend_text = None, "First week tracked: no earlier brief to compare with."
    else:
        trend = "up" if n > prev else "down" if n < prev else "flat"
        word = "no change" if trend == "flat" else trend
        trend_text = f"{_plural(n, 'mention')} in the week of {week}, vs {prev} in the previous brief ({word})."
    why = []
    if n:
        why.append(f"{u} of {_plural(n, 'thread')} that week had no working fix")
    if mix["negative"]:
        why.append(f"{mix['negative']} of {len(uniq)} stored threads were negative in tone")
    ins = _insight(sb, name, week)
    return {
        "type": "pain_point", "name": name, "title": nice(name), "category": cur.get("category") or "Other", "week": week,
        "explanation": f"Developers raised this in {_plural(n, 'thread')} in the week of {week} "
                       f"(category: {cur.get('category') or 'Other'}).",
        "why": "; ".join(why) + "." if why else None,
        "ai_problem": (ins or {}).get("problem_statement") or None,
        "ai_segment": _claims((ins or {}).get("segment")),
        "ai_generated_at": ((ins or {}).get("_created_at") or "")[:10] or None,
        "mentions": n, "previous": prev, "trend": trend, "trend_text": trend_text, "series": series,
        "unresolved": u, "engagement": cur.get("engagement") or 0,
        "negative": mix["negative"], "mixed_opinions": mix["mixed"],
        "independent_threads": len(uniq), "duplicates_merged": sum(t.get("duplicates", 0) for t in uniq),
        "sources": srcs, "evidence_level": ev["level"],
        "evidence_text": f"{_plural(len(uniq), 'independent thread')} stored across all weeks, from {_plural(len(srcs), 'source')} "
                         f"({ev['level'].lower()} evidence: {ev['why']}).",
        "first_observed": dates[0] if dates else None, "last_observed": dates[-1] if dates else None,
        "first_week": min(by_week), "threads": threads,
    }


def opportunity(sb, name: str, ctx: dict, weights: dict | None = None) -> dict | None:
    weeks = ctx["weeks"]
    if not weeks:
        return None
    latest, base_weeks = weeks[-1], weeks[:-1][-4:]
    current = {m["pain_point"]: m for m in ctx["metrics"] if m["week_start"] == latest}
    if name not in current:
        return None
    weights = weights or dict(scoring.DEFAULT_WEIGHTS)
    per = {m["week_start"]: m["mention_count"] for m in ctx["metrics"] if m["pain_point"] == name}
    base = (sum(per.get(w, 0) for w in base_weeks) / len(base_weeks)) if base_weeks else None
    posts = [p for p in ctx["posts"] if p.get("pain_point") == name]
    max_cur = max(m["mention_count"] for m in current.values())
    f = scoring.factors(current[name]["mention_count"], max_cur, base, posts)
    sc = scoring.score(f, weights)
    pp = pain_point(sb, name, ctx) or {}
    uniq = unique_threads(posts)
    ev = evidence_level(len(uniq), len(sources_of(uniq)))
    ins = _insight(sb, name, latest)

    risks = ["Discussion volume ranks where to look first. It is not evidence of willingness to pay or market size."]
    if ev["level"] != "Strong":
        risks.append(f"Evidence is {ev['level'].lower()}: {ev['why']}.")
    if len(sources_of(uniq)) == 1:
        risks.append("All threads this week come from one source, which may not represent developers elsewhere.")
    if base is None:
        risks.append("Growth can't be judged yet: there is no earlier brief to compare with, so it isn't in the score.")
    if opinion_mix(uniq)["mixed"]:
        risks.append("Developers disagree: some threads are positive and some negative.")
    risks.append("Only public posts on Hacker News, Stack Overflow and GitHub are covered; private teams and other communities are not.")
    return {
        "type": "opportunity", "name": name, "title": nice(name), "category": current[name].get("category") or "Other",
        "week": latest, "score": sc, "weights": weights,
        "factors": [{"key": k, "label": k.capitalize(), "value": f[k], "weight": weights[k], "about": d}
                    for k, d in scoring.FACTORS.items()],
        "explanation": pp.get("explanation") or "",
        "ai_problem": (ins or {}).get("problem_statement") or None,
        "ai_segment": _claims((ins or {}).get("segment")),
        "ai_unmet_needs": _claims((ins or {}).get("unmet_needs")),
        "ai_existing": _claims((ins or {}).get("existing_solutions")),
        "ai_experiments": [x for x in (ins or {}).get("experiments") or [] if isinstance(x, str)][:6],
        "ai_questions": [x for x in (ins or {}).get("interview_questions") or [] if isinstance(x, str)][:6],
        "ai_generated_at": ((ins or {}).get("_created_at") or "")[:10] or None,
        "supporting": [{"title": nice(name), "name": name, "mentions": current[name]["mention_count"],
                        "unresolved": current[name].get("unresolved_count") or 0}],
        "risks": risks,
        "independent_threads": len(uniq), "evidence_level": ev["level"],
        "evidence_text": f"{_plural(len(uniq), 'independent thread')} this week across "
                         f"{_plural(len(sources_of(uniq)), 'source')} ({ev['level'].lower()} evidence).",
        "threads": [x for x in (_thread(t) for t in sorted(uniq, key=lambda t: -(int(t.get("score") or 0) + int(t.get("comments") or 0)))) if x][:8],
    }


def trends(sb, ctx: dict, n: int = 6) -> dict:
    try:
        states = {r["finding_key"]: r for r in sb.table("radar_state").select("*").execute().data or []}
    except Exception:
        states = {}
    res = radar.find_signals(ctx["weeks"], ctx["metrics"], ctx["posts"], states)
    items = [{"label": nice(f["label"]), "kind": f["kind"], "reason": f["reason"], "threads": f["unique_threads"],
              "evidence_level": f["evidence"]["level"]} for f in res["findings"] if f["status"] != "dismissed"][:n]
    return {"type": "trends", "history_ok": res["history_ok"], "items": items}


def brief(sb, ctx: dict) -> dict | None:
    if not ctx["weeks"]:
        return None
    week = ctx["weeks"][-1]
    row = sb.table("digests").select("content_md,created_at").eq("week_start", week).limit(1).execute().data or []
    prev_week = ctx["weeks"][-2] if len(ctx["weeks"]) > 1 else None
    prev = {m["pain_point"]: m["mention_count"] for m in ctx["metrics"] if m["week_start"] == prev_week}
    top = sorted((m for m in ctx["metrics"] if m["week_start"] == week), key=lambda m: -m["mention_count"])[:10]
    srcs: dict[str, int] = {}
    for p in ctx["posts"]:
        s = _SRC.get((p.get("source") or "").lower(), p.get("source") or "Other")
        srcs[s] = srcs.get(s, 0) + 1
    return {"type": "brief", "week": week, "markdown": (row[0].get("content_md") or "") if row else "",
            "threads": len(ctx["posts"]), "sources": srcs,
            "top": [{"title": nice(m["pain_point"]), "category": m.get("category") or "Other", "mentions": m["mention_count"],
                     "previous": prev.get(m["pain_point"]) if prev_week else None,
                     "unresolved": m.get("unresolved_count") or 0} for m in top]}


def assemble(kind: str, title: str, intro: str, sections: list[dict], ctx: dict) -> dict:
    return {"v": SNAPSHOT_VERSION, "kind": kind, "title": title, "intro": intro,
            "generated_at": datetime.now(timezone.utc).isoformat(), "data_updated_at": ctx.get("data_updated_at"),
            "latest_week": ctx["weeks"][-1] if ctx["weeks"] else None,
            "sections": [s for s in sections if s]}


def executive_summary(sections: list[dict]) -> str:
    """A short, data-only starting point for the combined report's introduction (editable before sharing)."""
    pps = [s for s in sections if s and s["type"] == "pain_point"]
    ops = [s for s in sections if s and s["type"] == "opportunity"]
    parts = []
    if pps:
        top = max(pps, key=lambda s: s["mentions"])
        parts.append(f"This report covers {_plural(len(pps), 'developer pain point')}; the most discussed is "
                     f"{top['title']} ({_plural(top['mentions'], 'thread')} in the week of {top['week']}).")
    if ops:
        scored = [s for s in ops if s.get("score") is not None]
        if scored:
            best = max(scored, key=lambda s: s["score"])
            parts.append(f"Of {_plural(len(ops), 'opportunity')}, {best['title']} has the highest DevvIT priority score "
                         f"({best['score']:.0f}/100), which ranks where to look first rather than proving demand.")
    parts.append("All figures come from public Hacker News, Stack Overflow and GitHub threads collected by DevvIT; "
                 "source links are included for each item.")
    return " ".join(parts)
