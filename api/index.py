"""FastAPI app — single Vercel function handles every route.

The /api/run-digest endpoint is hit by Vercel Cron every Friday 03:00 UTC
(08:30 IST). It can also be invoked manually from the dashboard via
the /run-now button (open, no sign-in).
"""
import asyncio
import os
import secrets
import time
from urllib.parse import parse_qs, quote
import sys
from datetime import datetime, timedelta, timezone

# Make project root importable so `from lib.* import ...` works on Vercel.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import markdown as md
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.exception_handlers import http_exception_handler
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from lib import devi
from lib import share_snapshot as SS, sharing as SH, views_share as VS
from lib import build_pipeline as BP, building as BLD, views_build as VB
from lib import opportunity_ai, radar, scoring
from lib import views_intel as VI
from lib import workspace as W
from lib.evidence import opinion_mix, unique_threads
from lib import views as V
from lib.collectors import collect
from lib.db import db
from lib.email_view import build_email
from lib.gemini_brief import write_brief
from lib.gemini_tag import tag_all
from lib.metrics import aggregate, compute_trends, week_start_for

try:
    import resend
except ImportError:
    resend = None

app = FastAPI(title="DevvIT")

REQUIRED_ENV = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY"]
TAG_BATCH_SIZE = 15


def _env_check() -> tuple[bool, list[str]]:
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    return (len(missing) == 0, missing)


def _check_cron_auth(req: Request) -> None:
    """Vercel Cron sends `authorization: Bearer <CRON_SECRET>` when the env
    var is set. If no secret is configured we allow (dev-only)."""
    secret = os.getenv("CRON_SECRET")
    if not secret:
        return
    header = req.headers.get("authorization", "")
    expected = f"Bearer {secret}"
    if not secrets.compare_digest(header, expected):
        raise HTTPException(401, "unauthorized")


@app.exception_handler(StarletteHTTPException)
async def branded_errors(request: Request, exc: StarletteHTTPException):
    """Browser pages get a DevvIT error page; API routes and non-HTML clients keep the JSON error.
    Headers on the exception are passed through unchanged."""
    if request.url.path.startswith("/api/") or "text/html" not in request.headers.get("accept", ""):
        return await http_exception_handler(request, exc)
    return HTMLResponse(V.error_page(exc.status_code, str(exc.detail)), status_code=exc.status_code,
                        headers=getattr(exc, "headers", None))


# ---------- public ----------

@app.get("/api/health")
def health():
    ok, missing = _env_check()
    return {"ok": ok, "missing": missing, "resend": resend is not None}


@app.get("/health", response_class=HTMLResponse)
def health_html():
    def env(label, key, detail_ok, detail_missing, required=True):
        ok = bool(os.getenv(key))
        return {"label": label, "ok": True if ok else (False if required else None),
                "detail": detail_ok if ok else detail_missing}

    settings = [
        env("Supabase URL", "SUPABASE_URL", "Set", "Missing: SUPABASE_URL"),
        env("Supabase key", "SUPABASE_SERVICE_ROLE_KEY", "Set", "Missing: SUPABASE_SERVICE_ROLE_KEY"),
        env("AI model key", "GEMINI_API_KEY", "Set", "Missing: GEMINI_API_KEY"),
        env("Cron secret", "CRON_SECRET", "Friday run is protected", "Not set: anyone can trigger the weekly run", False),
    ]

    data = []
    if all(os.getenv(k) for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")):
        try:
            sb = db()
            last = sb.table("digests").select("week_start,created_at")                 .order("week_start", desc=True).limit(1).execute().data
            topics = sb.table("topics").select("active").execute().data or []
            data.append({"label": "Database connection", "ok": True, "detail": "Connected to Supabase"})
            data.append({"label": "Latest brief", "ok": True if last else None,
                         "detail": f"Week of {last[0]['week_start']}" if last else "No brief yet: click Run now"})
            active = sum(1 for t in topics if t.get("active"))
            data.append({"label": "Topics", "ok": active > 0,
                         "detail": f"{active} of {len(topics)} active"})
        except Exception as e:
            data.append({"label": "Database connection", "ok": False,
                         "detail": f"Could not query Supabase ({type(e).__name__})"})
    else:
        data.append({"label": "Database connection", "ok": False, "detail": "Supabase settings missing"})

    email_ready = bool(os.getenv("RESEND_API_KEY") and os.getenv("DIGEST_EMAIL_TO"))
    delivery = [
        {"label": "Weekly schedule", "ok": True, "detail": "Every Friday 03:00 UTC (8:30 AM IST)"},
        {"label": "Email delivery", "ok": True if email_ready else None,
         "detail": "Brief is emailed after each run" if email_ready
         else "Not set: needs RESEND_API_KEY and DIGEST_EMAIL_TO"},
        env("GitHub token", "GITHUB_TOKEN", "Higher GitHub search limits", "Optional: raises GitHub search limits", False),
        env("Stack Exchange key", "SO_KEY", "Higher Stack Overflow quota", "Optional: raises Stack Overflow quota", False),
    ]
    return V.health_page([("Settings", settings), ("Data", data), ("Delivery", delivery)])


def _load_week(sb, week: str | None = None):
    """(week_start, brief_html, metrics) for one week, or the latest when week is None."""
    q = sb.table("digests").select("*")
    q = q.eq("week_start", week) if week else q.order("week_start", desc=True)
    rows = q.limit(1).execute().data
    if not rows:
        return None
    ws = rows[0]["week_start"]
    metrics = sb.table("weekly_metrics").select("*").eq("week_start", ws) \
        .order("mention_count", desc=True).execute().data or []
    return ws, md.markdown(rows[0]["content_md"] or ""), metrics


def _history(sb) -> list[dict]:
    return sb.table("digests").select("week_start").order("week_start", desc=True).limit(12).execute().data or []


def _bundle(sb, week: str | None = None) -> dict | None:
    """Everything the Friday brief page needs for one week (the latest when week is None)."""
    found = _load_week(sb, week)
    if not found:
        return None
    ws, brief_html, metrics = found
    hist = _history(sb)
    weeks = sorted(h["week_start"] for h in hist if h["week_start"] <= ws)[-6:] or [ws]
    prev_week = weeks[-2] if len(weeks) > 1 else None
    rows = sb.table("weekly_metrics").select("week_start,pain_point,mention_count") \
        .in_("week_start", weeks).execute().data or []
    series: dict[str, dict] = {}
    for r in rows:
        series.setdefault(r["pain_point"], {})[r["week_start"]] = r["mention_count"]
    prev = {p: s.get(prev_week, 0) for p, s in series.items() if s.get(prev_week)} if prev_week else None
    posts = sb.table("posts") \
        .select("source,title,body,url,score,comments,created_at,is_unresolved,category,pain_point") \
        .eq("week_start", ws).not_.is_("pain_point", "null").limit(500).execute().data or []
    topics = sb.table("topics").select("category,keywords,active").order("id").execute().data or []
    meta = sb.table("digests").select("created_at").eq("week_start", ws).limit(1).execute().data or []
    return {"week": ws, "prev_week": prev_week, "weeks": weeks, "series": series, "prev": prev,
            "metrics": metrics, "brief_html": brief_html, "sections": V.parse_brief(brief_html),
            "posts": posts, "topics": topics, "created_at": meta[0]["created_at"] if meta else None}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    sb = db()
    return V.dashboard(_bundle(sb), _history(sb), flash=_run_message(request.query_params), intel=_home_intel(sb))


def _home_intel(sb) -> dict:
    """Radar findings and scored opportunities for the homepage panels. Never breaks the brief if it fails."""
    try:
        recent = _recent(sb)
        _, weeks, metrics, posts = recent
        found = radar.find_signals(weeks, metrics, posts, W.radar_states(sb))["findings"]
        _, _, opps, _ = _opportunity_rows(sb, scoring.DEFAULT_WEIGHTS, recent)
        return {"radar": found, "opps": opps}
    except Exception as e:
        print(f"[home] radar/opportunities unavailable: {e!r}")
        return {}


@app.get("/history/{week}", response_class=HTMLResponse)
def history_item(week: str):
    sb = db()
    b = _bundle(sb, week)
    if not b:
        raise HTTPException(404, "no brief for that week")
    return V.dashboard(b, _history(sb))


@app.get("/unresolved", response_class=HTMLResponse)
def unresolved(week: str = ""):
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    sb = db()
    return V.unresolved_page(_bundle(sb, week or None), _history(sb))


@app.get("/pain-points", response_class=HTMLResponse)
def pain_points_latest():
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    sb = db()
    found = _load_week(sb)
    if not found:
        return V.pain_points_page(None, [], [], _history(sb))
    ws, brief_html, metrics = found
    return V.pain_points_page(ws, metrics, V.parse_brief(brief_html), _history(sb))


@app.get("/pain-point", response_class=HTMLResponse)
def pain_point_detail(name: str = "", week: str = ""):
    if not name:
        return RedirectResponse("/pain-points", status_code=303)
    sb = db()
    weeks = sb.table("weekly_metrics").select("*").eq("pain_point", name) \
        .order("week_start", desc=True).limit(12).execute().data or []
    if not weeks:
        return RedirectResponse("/pain-points", status_code=303)
    # x-axis = every week that has a brief, so quiet weeks show as 0 instead of disappearing
    by_week = {w["week_start"]: w for w in weeks}
    category = weeks[0].get("category")
    hist = _history(sb)
    axis = sorted({h["week_start"] for h in hist} | set(by_week))[-12:]
    weeks = [by_week.get(w, {"week_start": w, "mention_count": 0, "unresolved_count": 0,
                             "engagement": 0, "category": category}) for w in axis]
    threads = sb.table("posts").select("source,title,url,score,comments,created_at,is_unresolved") \
        .eq("pain_point", name).order("created_at", desc=True).limit(40).execute().data or []
    return V.pain_point_page(name, week or weeks[-1]["week_start"], weeks, threads, hist,
                             extra=VB.build_panel(_builds_for(sb, name), name))


@app.get("/brief/{week}/pain-points", response_class=HTMLResponse)
def pain_points_week(week: str):
    sb = db()
    found = _load_week(sb, week)
    if not found:
        raise HTTPException(404, "no brief for that week")
    ws, brief_html, metrics = found
    return V.pain_points_page(ws, metrics, V.parse_brief(brief_html), _history(sb))


@app.get("/brief/{week}/{section}", response_class=HTMLResponse)
def brief_section(week: str, section: str):
    sb = db()
    found = _load_week(sb, week)
    if not found:
        raise HTTPException(404, "no brief for that week")
    ws, brief_html, _ = found
    sections = V.parse_brief(brief_html)
    if section not in {s["key"] for s in sections}:
        return RedirectResponse(f"/history/{ws}", status_code=303)
    return V.section_page(ws, sections, section, _history(sb))


@app.get("/watchlist", response_class=HTMLResponse)
def watchlist():
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    return V.watchlist_page(_history(db()))


@app.get("/recent", response_class=HTMLResponse)
def recent():
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    return V.recent_page(_history(db()))


@app.get("/api/watchlist", response_class=HTMLResponse)
def watchlist_cards(n: list[str] = Query(default=[]), compact: int = 0, mode: str = "cards"):
    """Latest numbers for the watched pain points (names come from the browser's watchlist)."""
    names = list(dict.fromkeys(x.strip()[:200] for x in n if x.strip()))[:50]
    sb = db()
    weeks = sorted(h["week_start"] for h in _history(sb))[-6:]
    rows = []
    if names and weeks:
        rows = sb.table("weekly_metrics") \
            .select("week_start,pain_point,category,mention_count,unresolved_count,engagement") \
            .in_("pain_point", names).in_("week_start", weeks).execute().data or []
    mode = "compact" if compact else mode if mode in ("cards", "rows", "feature") else "cards"
    return V.watch_cards(names, weeks, rows, mode=mode)


class DeviQuestion(BaseModel):
    question: str
    history: list[dict] = []


@app.post("/api/devi")
def devi_ask(q: DeviQuestion):
    """Devi, the DevvIT assistant: answers questions from the data in Supabase."""
    ok, _ = _env_check()
    if not ok:
        raise HTTPException(503, "Devi isn't set up yet: the database or AI key is missing.")
    if not q.question.strip():
        raise HTTPException(400, "Type a question first.")
    try:
        answer, meta = devi.ask(db(), q.question, q.history)
    except Exception as e:
        print(f"[devi] failed: {e!r}")
        raise HTTPException(502, "Devi couldn't reach the AI model just now. Please try again in a moment.")
    return {"answer": answer, "html": devi.to_html(answer), "meta": meta}


def _recent(sb, n_weeks: int = 6):
    """(history, weeks oldest-first, weekly_metrics rows, latest week's tagged posts)."""
    hist = _history(sb)
    weeks = sorted(h["week_start"] for h in hist)[-n_weeks:]
    if not weeks:
        return hist, [], [], []
    metrics = sb.table("weekly_metrics").select("week_start,pain_point,category,mention_count,unresolved_count,engagement") \
        .in_("week_start", weeks).execute().data or []
    posts = sb.table("posts") \
        .select("id,source,title,url,score,comments,created_at,is_unresolved,sentiment,category,pain_point,week_start") \
        .eq("week_start", weeks[-1]).not_.is_("pain_point", "null").limit(500).execute().data or []
    return hist, weeks, metrics, posts


def _flash_from(q) -> str | None:
    return {"saved": "Saved.", "monitored": "Added to monitored topics. Fine-tune the keyword on the Keywords page.",
            "relevant": "Marked as relevant.", "dismissed": "Dismissed. It won't be shown again unless it changes.",
            "new": "Restored.", "analysed": "Analysis generated from this pain point's threads.",
            "migrate": "Saving needs the database update: run migration 002 in Supabase first.",
            "ai-failed": "The analysis failed: Gemini couldn't be reached. Please try again in a moment.",
            "no-threads": "There are no stored threads for this pain point to analyse."}.get(q.get("msg") or "")


@app.get("/radar", response_class=HTMLResponse)
def radar_view(request: Request, dismissed: int = 0):
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    sb = db()
    hist, weeks, metrics, posts = _recent(sb)
    res = radar.find_signals(weeks, metrics, posts, W.radar_states(sb))
    cats = {m["pain_point"]: m.get("category") or "" for m in metrics}
    return VI.radar_page(res, cats, hist, W.ready(sb, "radar_state"), _flash_from(request.query_params), bool(dismissed))


@app.post("/radar/action")
def radar_action(request: Request, key: str = Form(...), label: str = Form(...), action: str = Form(...),
                 first_seen: str = Form(""), category: str = Form("")):
    sb = db()
    if not W.ready(sb, "radar_state"):
        return RedirectResponse("/radar?msg=migrate", status_code=303)
    if action not in ("relevant", "dismissed", "monitored", "new"):
        raise HTTPException(400, "unknown action")
    W.set_radar_state(sb, key[:120], label[:200], action, first_seen[:10] or None)
    if action == "monitored":
        # Add the theme as a keyword to its category's topic (or a new topic), keeping existing settings.
        cat = category.strip() or "Radar"
        topics = sb.table("topics").select("id,category,keywords").execute().data or []
        t = next((t for t in topics if (t["category"] or "").lower() == cat.lower()), None)
        if t:
            if label not in (t["keywords"] or []):
                sb.table("topics").update({"keywords": (t["keywords"] or []) + [label]}).eq("id", t["id"]).execute()
        else:
            sb.table("topics").insert({"category": cat, "keywords": [label], "active": True}).execute()
    return RedirectResponse(f"/radar?msg={action}", status_code=303)


def _opportunity_rows(sb, weights: dict, recent: tuple | None = None):
    hist, weeks, metrics, posts = recent or _recent(sb)
    if not weeks:
        return hist, weeks, [], False
    latest, base_weeks = weeks[-1], weeks[:-1][-4:]
    per: dict[str, dict] = {}
    for m in metrics:
        per.setdefault(m["pain_point"], {})[m["week_start"]] = m
    by_label: dict[str, list] = {}
    for p in posts:
        by_label.setdefault(p["pain_point"], []).append(p)
    current = {k: v[latest] for k, v in per.items() if latest in v}
    max_cur = max((m["mention_count"] for m in current.values()), default=0)
    statuses = W.opportunity_rows(sb)
    rows = []
    for name, m in current.items():
        base = (sum((per[name].get(w) or {}).get("mention_count", 0) for w in base_weeks) / len(base_weeks)) if base_weeks else None
        f = scoring.factors(m["mention_count"], max_cur, base, by_label.get(name, []))
        rows.append({"name": name, "category": m.get("category") or "Other", "factors": f,
                     "score": scoring.score(f, weights), "status": (statuses.get(name) or {}).get("status")})
    rows.sort(key=lambda r: -(r["score"] or 0))
    return hist, weeks, rows, bool(base_weeks)


@app.get("/opportunities", response_class=HTMLResponse)
def opportunities(request: Request):
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    sb = db()
    weights = scoring.parse_weights(dict(request.query_params))
    hist, weeks, rows, has_base = _opportunity_rows(sb, weights)
    return VI.opportunities_page(rows, weights, weeks[-1] if weeks else None, hist, W.ready(sb, "opportunities"), has_base)


def _point_threads(sb, name: str, weeks: list[str], with_body: bool = False) -> list[dict]:
    cols = "id,source,title,url,score,comments,created_at,is_unresolved,sentiment,week_start" + (",body" if with_body else "")
    q = sb.table("posts").select(cols).eq("pain_point", name)
    if weeks:
        q = q.in_("week_start", weeks)
    return unique_threads(q.order("created_at", desc=True).limit(80).execute().data or [])


@app.get("/opportunity", response_class=HTMLResponse)
def opportunity(request: Request, name: str = ""):
    if not name:
        return RedirectResponse("/opportunities", status_code=303)
    sb = db()
    weights = scoring.parse_weights(dict(request.query_params))
    hist, weeks, rows, _ = _opportunity_rows(sb, weights)
    row = next((r for r in rows if r["name"] == name), None)
    if not row or not weeks:
        raise HTTPException(404, "That pain point isn't in the latest brief.")
    _, _, metrics, _ = _recent(sb)
    series = [next((m["mention_count"] for m in metrics if m["pain_point"] == name and m["week_start"] == w), 0) for w in weeks]
    threads = _point_threads(sb, name, weeks)
    latest = weeks[-1]
    return VI.opportunity_page(
        name, row["category"], latest, weeks, series, row["factors"], row["score"], weights,
        W.opportunity_rows(sb).get(name), W.opportunity_log(sb, name), W.get_insight(sb, name, latest),
        threads, opinion_mix(threads), W.ready(sb, "opportunities"), _flash_from(request.query_params), hist,
        extra=VB.build_panel(_builds_for(sb, name), name))


@app.post("/opportunity/save")
def opportunity_save(request: Request, name: str = Form(...), status: str = Form("New"), notes: str = Form("")):
    sb = db()
    if not W.ready(sb, "opportunities"):
        return RedirectResponse(f"/opportunity?name={quote(name)}&msg=migrate", status_code=303)
    if status not in W.STATUSES:
        raise HTTPException(400, "unknown status")
    W.save_opportunity(sb, name[:200], status, notes[:5000])
    return RedirectResponse(f"/opportunity?name={quote(name)}&msg=saved", status_code=303)


@app.post("/opportunity/analyze")
def opportunity_analyze(request: Request, name: str = Form(...)):
    sb = db()
    if not W.ready(sb, "opportunity_insights"):
        return RedirectResponse(f"/opportunity?name={quote(name)}&msg=migrate", status_code=303)
    weeks = sorted(h["week_start"] for h in _history(sb))[-6:]
    threads = _point_threads(sb, name, weeks, with_body=True)
    if not threads:
        return RedirectResponse(f"/opportunity?name={quote(name)}&msg=no-threads", status_code=303)
    try:
        content = opportunity_ai.analyze(name, threads)
    except Exception as e:
        print(f"[opportunity] analysis failed: {e!r}")
        return RedirectResponse(f"/opportunity?name={quote(name)}&msg=ai-failed", status_code=303)
    W.save_insight(sb, name, weeks[-1], content)
    return RedirectResponse(f"/opportunity?name={quote(name)}&msg=analysed", status_code=303)


@app.get("/evidence", response_class=HTMLResponse)
def evidence(request: Request):
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    sb = db()
    hist, weeks, metrics, posts = _recent(sb)
    latest = weeks[-1] if weeks else None
    runs = W.recent_runs(sb)
    last_sources = ((runs[0].get("stats") or {}).get("sources") or {}) if runs else {}
    labels = {"hn": ("hackernews", "Hacker News"), "so": ("stackoverflow", "Stack Overflow"), "gh": ("github", "GitHub")}
    coverage = []
    for code, (src, label) in labels.items():
        n = sum(1 for p in posts if (p.get("source") or "").lower() in (src, code))
        st = last_sources.get(code) or {}
        coverage.append({"label": label, "posts": n, "failed": st.get("failed", 0), "queries": st.get("queries", 0)})
    by_label: dict[str, list] = {}
    for p in posts:
        by_label.setdefault(p["pain_point"], []).append(p)
    uniq = {k: unique_threads(v) for k, v in by_label.items()}
    dupes = sorted(((k, sum(t["duplicates"] for t in v)) for k, v in uniq.items()), key=lambda x: -x[1])
    meta = sb.table("digests").select("created_at").eq("week_start", latest).limit(1).execute().data if latest else []
    fresh = None
    if meta and meta[0].get("created_at"):
        made = datetime.fromisoformat(meta[0]["created_at"].replace("Z", "+00:00"))
        fresh = (datetime.now(timezone.utc) - (made if made.tzinfo else made.replace(tzinfo=timezone.utc))).days
    data = {"latest": latest, "freshness_days": fresh, "runs": runs, "coverage": coverage,
            "dupes": [d for d in dupes if d[1]][:15], "thin": sorted(k for k, v in uniq.items() if len(v) == 1),
            "mixed": [(k, m) for k, v in uniq.items() if (m := opinion_mix(v))["mixed"]],
            "other": sum(1 for p in posts if (p.get("category") or "Other") == "Other"), "total": len(posts)}
    return VI.evidence_page(data, hist)


# ---------- admin ----------

# ---------- Sharing ----------
_NO_STORE = {"Cache-Control": "no-store, private", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow"}
MAX_REPORT_ITEMS = 20


def _base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto.split(',')[0].strip()}://{host.split(',')[0].strip()}"


def _link(request: Request, row: dict) -> str:
    return f"{_base_url(request)}/r/{SH.token_for(row['token_nonce'])}"


def _weights(w: str) -> dict:
    """Opportunity weights from the explorer's query string (e.g. '?w_growth=2'), clamped like the page does."""
    q = {k: v[0] for k, v in parse_qs((w or "").lstrip("?")).items() if v}
    return scoring.parse_weights(q)


def _single_snapshot(sb, kind: str, name: str, w: str = "", title: str = "", intro: str = "") -> tuple[dict, list[dict]]:
    """Snapshot for one pain point, one opportunity or the latest weekly report. 404 when the data isn't there."""
    ctx = SS.load_context(sb)
    if kind == "pain_point":
        sec = SS.pain_point(sb, name, ctx)
        if not sec:
            raise HTTPException(404, "That pain point isn't in DevvIT's data.")
        sections = [sec]
    elif kind == "opportunity":
        sec = SS.opportunity(sb, name, ctx, _weights(w))
        if not sec:
            raise HTTPException(404, "That opportunity isn't in the latest brief.")
        sections = [sec]
    elif kind == "weekly":
        sec = SS.brief(sb, ctx)
        if not sec:
            raise HTTPException(404, "There is no weekly brief yet.")
        sections = [sec, SS.trends(sb, ctx)]
        name = sec["week"]
        title = title or f"Developer intelligence report · week of {sec['week']}"
    else:
        raise HTTPException(400, "Unknown report type.")
    title = SH.clean_text(title or sections[0]["title"], SH.MAX_TITLE)
    return SS.assemble(kind, title, SH.clean_text(intro, SH.MAX_INTRO), sections, ctx), [{"type": kind, "name": name}]


def _combined_snapshot(sb, items: list[str], title: str, intro: str, with_trends: bool) -> tuple[dict, list[dict], list[str]]:
    """Snapshot for several pain points and opportunities, in the order given. Unknown items are reported, not invented."""
    ctx = SS.load_context(sb)
    sections, refs, missing, seen = [], [], [], set()
    for it in items[:MAX_REPORT_ITEMS]:
        kind, _, name = it.partition(":")
        if (kind, name) in seen or kind not in ("pp", "op") or not name:
            continue
        seen.add((kind, name))
        sec = SS.pain_point(sb, name, ctx) if kind == "pp" else SS.opportunity(sb, name, ctx)
        if sec:
            sections.append(sec)
            refs.append({"type": "pain_point" if kind == "pp" else "opportunity", "name": name})
        else:
            missing.append(SS.nice(name))
    if with_trends:
        sections.append(SS.trends(sb, ctx))
    title = SH.clean_text(title, SH.MAX_TITLE) or "Developer intelligence report"
    return SS.assemble("combined", title, SH.clean_text(intro, SH.MAX_INTRO), sections, ctx), refs, missing


@app.get("/api/share/summary")
def share_summary(kind: str, name: str = "", w: str = ""):
    """Copy summary: built from the same data as a shared report. Public, like the dashboards it summarises."""
    try:
        snap, _ = _single_snapshot(db(), kind, name, w)
    except HTTPException as e:
        return JSONResponse({"detail": e.detail}, status_code=e.status_code)
    return {"text": SH.summary_text(snap)}


@app.get("/share/print", response_class=HTMLResponse)
def share_print(kind: str, name: str = "", w: str = ""):
    """Print-friendly page of live data (Export). Nothing is saved."""
    snap, _ = _single_snapshot(db(), kind, name, w)
    return HTMLResponse(VS.report_page(snap, banner=VS.print_banner("Print preview of current data, not a saved report."),
                                       show_copy_link=False), headers=_NO_STORE)


@app.post("/reports/print", response_class=HTMLResponse)
def reports_print(item: list[str] = Form(default=[]), title: str = Form(""), intro: str = Form(""), trends: str = Form("")):
    snap, _, _ = _combined_snapshot(db(), item, title, intro, trends == "1")
    return HTMLResponse(VS.report_page(snap, banner=VS.print_banner("Print preview, not a saved report."), show_copy_link=False),
                        headers=_NO_STORE)


@app.get("/reports/new", response_class=HTMLResponse)
def reports_new(request: Request, pp: list[str] = Query(default=[]), op: list[str] = Query(default=[])):
    sb = db()
    items = [f"pp:{n}" for n in pp] + [f"op:{n}" for n in op]
    ctx_snap, _, missing = _combined_snapshot(sb, items, "", "", False)
    sections = ctx_snap["sections"]
    trends = SS.trends(sb, SS.load_context(sb))
    week = ctx_snap.get("latest_week")
    return VS.builder_page(sections, missing, f"Developer intelligence report{f' · week of {week}' if week else ''}",
                           SS.executive_summary(sections), trends, _history(sb), W.ready(sb, "shared_reports"))


@app.post("/share/create")
def share_create(request: Request, kind: str = Form(...), name: str = Form(""), w: str = Form(""),
                 title: str = Form(""), intro: str = Form(""), item: list[str] = Form(default=[]), trends: str = Form(""),
                 visibility: str = Form("unlisted"), expires: str = Form("30")):
    """Create a shared report (owner only). The snapshot is built on the server from stored data; only the title
    and introduction come from the form, as plain text."""
    sb = db()
    if not W.ready(sb, "shared_reports"):
        raise HTTPException(503, "Sharing needs the database update: run supabase/migrations/004_shared_reports.sql in Supabase first.")
    if visibility not in SH.VISIBILITY:
        raise HTTPException(400, "Unknown visibility.")
    try:
        exp = SH.expiry(expires, datetime.now(timezone.utc))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if kind == "combined":
        snap, refs, _ = _combined_snapshot(sb, item, title, intro, trends == "1")
        if not refs:
            raise HTTPException(400, "Select at least one pain point or opportunity that is in DevvIT's data.")
    else:
        snap, refs = _single_snapshot(sb, kind, name, w, title, intro)
    row, _ = SH.create(sb, kind, snap["title"], refs, snap, visibility, exp)
    return RedirectResponse(f"/reports/{row['id']}?msg=created", status_code=303)


@app.get("/reports", response_class=HTMLResponse)
def reports_list(request: Request):
    sb = db()
    ok = W.ready(sb, "shared_reports")
    rows = SH.all_reports(sb) if ok else []
    now = datetime.now(timezone.utc)
    return VS.reports_page(rows, {r["id"]: _link(request, r) for r in rows}, {r["id"]: SH.status(r, now) for r in rows},
                           _history(sb), ok, _share_flash(request.query_params))


def _share_flash(q) -> str | None:
    return {"created": "Report created. Copy the link below to share it.", "revoked": "Access revoked. The link no longer works.",
            "updated": "Settings saved."}.get(q.get("msg") or "")


@app.get("/reports/{rid}", response_class=HTMLResponse)
def report_manage(request: Request, rid: int):
    sb = db()
    row = SH.by_id(sb, rid) if W.ready(sb, "shared_reports") else None
    if not row:
        raise HTTPException(404, "That report doesn't exist.")
    link = _link(request, row)
    state = SH.status(row, datetime.now(timezone.utc))
    return VS.created_page(row, link, SH.summary_text(row["snapshot"], link), state, _history(sb), _share_flash(request.query_params))


@app.post("/reports/{rid}/revoke")
def report_revoke(request: Request, rid: int):
    sb = db()
    if not SH.by_id(sb, rid):
        raise HTTPException(404, "That report doesn't exist.")
    sb.table("shared_reports").update({"revoked_at": datetime.now(timezone.utc).isoformat()}).eq("id", rid) \
        .is_("revoked_at", "null").execute()
    return RedirectResponse(f"/reports/{rid}?msg=revoked", status_code=303)


@app.post("/reports/{rid}/update")
def report_update(request: Request, rid: int, visibility: str = Form("unlisted"), expires: str = Form("keep"),
                  expires_on: str = Form("")):
    sb = db()
    row = SH.by_id(sb, rid)
    if not row:
        raise HTTPException(404, "That report doesn't exist.")
    if row.get("revoked_at"):
        raise HTTPException(409, "A revoked report can't be changed.")
    if visibility not in SH.VISIBILITY:
        raise HTTPException(400, "Unknown visibility.")
    changes = {"visibility": visibility}
    choice = expires_on.strip() or expires
    if choice != "keep":
        try:
            exp = SH.expiry(choice, datetime.now(timezone.utc))
        except ValueError as e:
            raise HTTPException(400, str(e))
        changes["expires_at"] = exp.isoformat() if exp else None
    sb.table("shared_reports").update(changes).eq("id", rid).execute()
    return RedirectResponse(f"/reports/{rid}?msg=updated", status_code=303)


@app.get("/r/{token}", response_class=HTMLResponse)
def shared_report(request: Request, token: str):
    """The read-only report recipients open. Revocation, expiry and privacy are checked here, on every request."""
    try:
        sb = db()
        row = SH.by_token(sb, token) if W.ready(sb, "shared_reports") else None
    except Exception as e:
        print(f"[share] lookup failed: {type(e).__name__}")       # never log the token
        code, html = VS.link_error("unavailable")
        return HTMLResponse(html, status_code=code, headers=_NO_STORE)
    if not row:
        code, html = VS.link_error("invalid")
        return HTMLResponse(html, status_code=code, headers=_NO_STORE)
    now = datetime.now(timezone.utc)
    state = SH.status(row, now)
    if state != "active":
        code, html = VS.link_error(state)
        return HTMLResponse(html, status_code=code, headers=_NO_STORE)
    try:
        SH.touch(sb, row, now)
    except Exception:
        pass
    return HTMLResponse(VS.report_page(row["snapshot"]), headers=_NO_STORE)


# ---------- Building Now ----------
def _builds_for(sb, name: str) -> list[dict] | None:
    """Build discussions connected to one pain point, or None when Building Now isn't set up (panel hidden)."""
    if not W.ready(sb, "build_items"):
        return None
    try:
        return BLD.builds_for_pain_point(name, BP.load(sb)["items"])
    except Exception as e:
        print(f"[building] related builds failed: {e!r}")
        return None


def _build_filters(q) -> dict:
    try:
        days = int(q.get("days", 30))
    except ValueError:
        days = 30
    f = {"days": days if days in (7, 30, 90, 0) else 30}
    for k, allowed in (("category", set(BLD.CATEGORIES)), ("source", {"hn", "stackoverflow", "github", "devto", "producthunt"}),
                       ("blocker", set(BLD.BLOCKERS)), ("theme", {"emerging", "recurring"})):
        f[k] = q.get(k) if q.get(k) in allowed else ""
    f["tech"] = BLD.tech_key(q.get("tech") or "")
    f["q"] = " ".join((q.get("q") or "").split())[:100]
    return f


def _related_pain_points(sb, f: dict, items: list[dict], tech_label: str, labels: list[str], weeks: list[str]) -> dict | None:
    """Pain points connected to the selected technology or category, only where stored records support it."""
    if f["tech"] and weeks:
        threads = sb.table("posts").select("title,body,pain_point").in_("week_start", weeks) \
            .not_.is_("pain_point", "null").limit(1000).execute().data or []
        rows = BLD.pain_points_for_tech(tech_label, threads)
        for r in rows:
            r["basis"] = f"mention {tech_label} by name"
        return {"name": tech_label, "rows": rows,
                "how": f"Pain points from the last {len(weeks)} weekly briefs whose threads mention {tech_label} by name (text match, not AI)."}
    if f["category"]:
        found: dict[str, list] = {}
        for it in items:
            if it.get("category") != f["category"]:
                continue
            for b in it["blockers"]:
                m = BLD.match_pain_point(b, labels) if b["explicit"] else None
                if m:
                    found.setdefault(m[0], []).append(it)
        rows = [{"pain_point": k, "threads": v, "basis": "in this category report a blocker sharing 2+ words with it (suggested)"}
                for k, v in sorted(found.items(), key=lambda x: -len(x[1]))][:6]
        return {"name": f["category"], "rows": rows,
                "how": "Suggested connections: build discussions in this category whose quoted blocker shares at least two words with a pain point."}
    return None


@app.get("/building", response_class=HTMLResponse)
def building(request: Request):
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    sb = db()
    f = _build_filters(request.query_params)
    hist = _history(sb)
    if not W.ready(sb, "build_items"):
        return VB.building_page(None, f, hist, state="migrate")
    try:
        d = BP.load(sb)
        now = datetime.now(timezone.utc)
        today = now.date()
        items = d["items"]
        tt, tc = BLD.trends(items, today, "tech"), BLD.trends(items, today, "category")
        tp = BLD.trends(items, today, "topic")
        shown = BLD.apply_filters(items, f, today)
        if f["theme"]:
            keys = BLD.theme_keys(tt, f["theme"]) | BLD.theme_keys(tc, f["theme"])
            shown = [it for it in shown if it.get("category") in keys
                     or any(t["explicit"] and t["key"] in keys for t in it["techs"])]
        tech_options = BLD.top_counts(BLD.apply_filters(items, {"days": f["days"]}, today), "tech", 40)
        tech_label = next((t["name"] for it in items for t in it["techs"] if t["key"] == f["tech"]), f["tech"])
        _, weeks, metrics, _ = _recent(sb)
        labels = sorted({m["pain_point"] for m in metrics})
        d.update(f=f, shown=shown, recent=sorted(shown, key=lambda it: it.get("posted_at") or "", reverse=True)[:24],
                 cats=BLD.top_counts(shown, "category"), techs=BLD.top_counts(shown, "tech", 12),
                 trend_tech=tt, trend_cat=tc, trend_topic=tp, topics=BLD.top_counts(shown, "topic", 12),
                 langs=BLD.top_counts(shown, "language", 10), blockers=BLD.blocker_groups(shown), labels=labels,
                 tech_options=tech_options, related=_related_pain_points(sb, f, items, tech_label, labels, weeks),
                 fresh=BLD.freshness(items, d["refreshes"], now), flash=_build_message(request.query_params))
    except Exception as e:
        print(f"[building] failed: {e!r}")
        return VB.building_page(None, f, hist, state="error")
    return VB.building_page(d, f, hist)


def _build_message(q) -> str | None:
    s = q.get("updated")
    if s == "busy":
        return "An update is already running. Refresh this page in a minute."
    if s == "failed":
        return "The update failed. Details are under Data freshness and coverage."
    if s and s.isdigit():
        return f"Updated: {s} new build discussion{'s' if s != '1' else ''} found."
    return None


@app.post("/building/refresh")
def building_refresh():
    """Collect and classify new build discussions only (no brief, no email). Open like Run now.
    Repeat clicks cost almost nothing: discussions already classified are never sent to Gemini again."""
    sb = db()
    if not W.ready(sb, "build_items"):
        return RedirectResponse("/building", status_code=303)
    if W.run_in_progress(sb):
        return RedirectResponse("/building?updated=busy", status_code=303)
    stats = BP.refresh(sb, "manual", budget_s=240)
    if not stats.get("ok"):
        return RedirectResponse("/building?updated=failed", status_code=303)
    return RedirectResponse(f"/building?updated={int(stats.get('relevant', 0))}", status_code=303)


@app.get("/topics", response_class=HTMLResponse)
def topics_get(request: Request):
    sb = db()
    rows = sb.table("topics").select("*").order("id").execute()
    return V.topics_page(rows.data or [])


@app.post("/topics/add")
def topics_add(request: Request, category: str = Form(...), keywords: str = Form(...)):
    kws = [k.strip() for k in keywords.split(",") if k.strip()]
    if not category.strip() or not kws:
        raise HTTPException(400, "category + at least one keyword required")
    db().table("topics").insert(
        {"category": category.strip(), "keywords": kws, "active": True}
    ).execute()
    return RedirectResponse("/topics", status_code=303)


@app.post("/topics/toggle/{tid}")
def topics_toggle(request: Request, tid: int):
    sb = db()
    r = sb.table("topics").select("active").eq("id", tid).limit(1).execute()
    cur = r.data[0]["active"] if r.data else True
    sb.table("topics").update({"active": not cur}).eq("id", tid).execute()
    return RedirectResponse("/topics", status_code=303)


@app.post("/run-now")
def run_now(request: Request):
    """Dashboard button: run the pipeline, then go back to the brief with a summary. No sign-in needed."""
    try:
        result = _do_run(days_back=7)
    except Exception as e:
        print(f"[run-now] failed: {e!r}")
        return RedirectResponse("/?run=error", status_code=303)
    if result.get("skipped"):
        return RedirectResponse("/?run=busy", status_code=303)
    if not result.get("ok"):
        return RedirectResponse("/?run=error", status_code=303)
    if not result.get("pain_points"):
        return RedirectResponse("/?run=empty", status_code=303)
    email = result.get("email", "")
    email_flag = "sent" if email == "sent" else "skipped" if email.startswith("no ") else "failed"
    return RedirectResponse(
        f"/?run=done&posts={int(result.get('collected', 0))}&pp={int(result['pain_points'])}&email={email_flag}",
        status_code=303)


def _run_message(q) -> str | None:
    """Turn the run-now redirect parameters into a one-line message. Only known values are used."""
    run = q.get("run")
    if run == "busy":
        return "A run is already in progress. The new brief will appear when it finishes; refresh in a minute."
    if run == "error":
        return "The run failed. Check the Vercel function logs, then try again."
    if run == "empty":
        return "Run finished, but no relevant posts were found this week. Try adding keywords on the Topics page."
    if run != "done":
        return None
    try:
        posts, pp = int(q.get("posts", 0)), int(q.get("pp", 0))
    except ValueError:
        return "Brief updated."
    email = {"sent": "and emailed", "skipped": "(email not set up)", "failed": "but the email failed to send"}
    return f"Brief updated from {posts} posts: {pp} pain points {email.get(q.get('email'), '')}".rstrip() + "."


# ---------- cron ----------

@app.get("/api/run-digest")
def api_run_digest(request: Request):
    _check_cron_auth(request)
    # First-run trick: no prior weekly_metrics → pull 14 days so we can
    # split into "last week" + "this week" and show real trends on day 1.
    prev = db().table("weekly_metrics").select("week_start").limit(1).execute()
    days = 7 if prev.data else 14
    return _do_run(days_back=days, trigger="cron")


# ---------- pipeline ----------

def _do_run(days_back: int = 7, trigger: str = "manual") -> dict:
    """Run the pipeline once, logged in `runs` (when migration 002 is applied).
    A run that started less than 10 minutes ago and hasn't finished blocks a second one."""
    t0 = time.monotonic()
    sb = db()
    if W.run_in_progress(sb):
        return {"ok": False, "skipped": True, "error": "another run is already in progress"}
    run_id, stats = None, {}
    try:
        run_id = W.start_run(sb, trigger)
    except Exception as e:
        print(f"[run] couldn't log run start: {e!r}")
    try:
        result = _pipeline(days_back, stats)
    except Exception as e:
        try:
            W.finish_run(sb, run_id, "failed", stats, repr(e))
        except Exception:
            pass
        raise
    result["building"] = _refresh_building(sb, trigger, t0)
    try:
        W.finish_run(sb, run_id, "success" if result.get("ok") else "failed",
                     {**stats, **{k: v for k, v in result.items() if k != "ok"}}, result.get("error"))
    except Exception as e:
        print(f"[run] couldn't log run end: {e!r}")
    return result


def _refresh_building(sb, trigger: str, t0: float) -> dict:
    """Building Now update after the brief. Uses only the time left in the 300 s function limit and never
    fails the run: anything not classified now is picked up next time."""
    budget = 270 - (time.monotonic() - t0)
    if budget < 60:
        return {"ok": False, "skipped": "not enough time left in this run"}
    try:
        if not W.ready(sb, "build_items"):
            return {"ok": False, "skipped": "migration 003 not applied"}
        s = BP.refresh(sb, trigger, budget_s=budget)
        return {k: s.get(k) for k in ("ok", "candidates", "classified", "relevant", "pending", "error")}
    except Exception as e:
        print(f"[building] refresh after run failed: {e!r}")
        return {"ok": False, "error": repr(e)[:200]}


def _pipeline(days_back: int, stats: dict) -> dict:
    sb = db()
    today = datetime.now(timezone.utc).date()
    this_week = week_start_for(today)
    last_week = this_week - timedelta(days=7)

    topics_rows = sb.table("topics").select("*").eq("active", True).execute().data or []
    if not topics_rows:
        return {"ok": False, "error": "no active topics — seed via supabase/schema.sql or /topics"}

    topics = [
        {"id": t["id"], "category": t["category"], "keywords": t["keywords"],
         "exclude_terms": t.get("exclude_terms") or []}
        for t in topics_rows
    ]

    # 1. Collect from live sources (async parallel across keywords × sources)
    posts = asyncio.run(collect(topics, days_back=days_back, stats=stats))

    # 2. Upsert raw posts (dedupe by PK)
    if posts:
        rows = [{
            "id": p["id"],
            "source": p["source"],
            "title": (p.get("title") or "")[:500],
            "body": (p.get("body") or "")[:5000],
            "url": p["url"],
            "score": int(p.get("score") or 0),
            "comments": int(p.get("comments") or 0),
            "created_at": p["created_at"],
            "topic_id": p["topic_id"],
        } for p in posts]
        # supabase-py accepts a list for upsert
        sb.table("posts").upsert(rows).execute()

    # 3. Find untagged posts within the window
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    MAX_TAG = 90
    untagged = sb.table("posts") \
        .select("id,title,body,created_at,topic_id,score,comments,url") \
        .is_("pain_point", "null") \
        .gte("created_at", cutoff) \
        .order("score", desc=True) \
        .limit(MAX_TAG) \
        .execute().data or []

    categories = [t["category"] for t in topics_rows] + ["Other"]
    prior = sb.table("posts").select("pain_point") \
        .not_.is_("pain_point", "null").limit(300).execute().data or []
    prior_labels = sorted({p["pain_point"] for p in prior if p.get("pain_point")})

    # 4. Tag — all batches in parallel (asyncio.gather w/ semaphore)
    tagged = 0
    if untagged:
        tags = asyncio.run(tag_all(untagged, categories, prior_labels,
                                   batch_size=12, concurrency=5))
        tag_by_id = {t["post_id"]: t for t in tags if t.get("post_id")}
        # Build upsert rows (need full row data since upsert replaces)
        full_untagged = {p["id"]: p for p in untagged}
        update_rows = []
        for pid, p in full_untagged.items():
            t = tag_by_id.get(pid)
            if not t:
                continue
            created = datetime.fromisoformat(
                p["created_at"].replace("Z", "+00:00")
            ).date()
            ws = week_start_for(created).isoformat()
            row = {
                "id": pid,
                "source": pid.split(":", 1)[0],
                "title": p.get("title") or "",
                "body": p.get("body") or "",
                "url": p.get("url"),
                "score": p.get("score") or 0,
                "comments": p.get("comments") or 0,
                "created_at": p["created_at"],
                "topic_id": p.get("topic_id"),
            }
            if t.get("relevant", True):
                row.update({
                    "pain_point": (t.get("pain_point") or "").strip().lower()[:100] or None,
                    "category": (t.get("category") or "Other")[:60],
                    "sentiment": t.get("sentiment"),
                    "is_unresolved": bool(t.get("is_unresolved")),
                    "week_start": ws,
                })
            else:
                row.update({
                    "pain_point": None, "category": None,
                    "sentiment": t.get("sentiment"),
                    "is_unresolved": False, "week_start": None,
                })
            update_rows.append(row)
            tagged += 1
        # Single batched upsert
        if update_rows:
            sb.table("posts").upsert(update_rows).execute()

    # 5. Aggregate THIS week + LAST week from DB
    this_rows = sb.table("posts") \
        .select("pain_point,category,is_unresolved,score,comments,title,url") \
        .eq("week_start", this_week.isoformat()).execute().data or []
    last_rows = sb.table("posts").select("pain_point") \
        .eq("week_start", last_week.isoformat()).execute().data or []

    prev_counts: dict[str, int] = {}
    for r in last_rows:
        pp = r.get("pain_point")
        if pp:
            prev_counts[pp] = prev_counts.get(pp, 0) + 1

    agg = aggregate(this_rows)
    metrics = compute_trends(agg, prev_counts)

    # 6. Overwrite this week's weekly_metrics table
    sb.table("weekly_metrics").delete().eq("week_start", this_week.isoformat()).execute()
    if metrics:
        metric_rows = [{
            "week_start": this_week.isoformat(),
            "pain_point": m["pain_point"],
            "category": m["category"],
            "mention_count": m["count"],
            "engagement": m["engagement"],
            "unresolved_count": m["unresolved_count"],
        } for m in metrics]
        sb.table("weekly_metrics").upsert(metric_rows).execute()

    if not metrics:
        return {
            "ok": True,
            "note": "no relevant tagged posts for this week — try again with more keywords or wider window",
            "collected": len(posts),
            "tagged": tagged,
        }

    # 7. Build evidence examples + write brief with Gemini
    examples = {}
    for m in metrics[:8]:
        examples[m["pain_point"]] = [
            {"title": p.get("title") or "", "url": p.get("url")}
            for p in m["posts"][:3]
        ]
    brief = write_brief(metrics[:12], examples)

    # 8. Persist brief
    sb.table("digests").upsert({
        "week_start": this_week.isoformat(),
        "content_md": brief,
    }).execute()

    # 9. Email (non-fatal if it fails)
    email_status = "skipped"
    try:
        email_status = _send_email(brief, this_week.isoformat(), metrics)
    except Exception as e:
        print(f"[run] email error: {e}")
        email_status = f"failed: {e}"

    return {
        "ok": True,
        "week": this_week.isoformat(),
        "days_back": days_back,
        "collected": len(posts),
        "tagged": tagged,
        "pain_points": len(metrics),
        "email": email_status,
    }


def _send_email(brief_md: str, week: str, metrics: list[dict]) -> str:
    key = os.getenv("RESEND_API_KEY")
    to = os.getenv("DIGEST_EMAIL_TO")
    if not (key and to):
        return "no RESEND_API_KEY or DIGEST_EMAIL_TO"
    if resend is None:
        return "resend package missing"
    resend.api_key = key
    sender = os.getenv("RESEND_FROM", "DevvIT <onboarding@resend.dev>")
    subject, html, text = build_email(brief_md, metrics, week)
    resend.Emails.send({
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    })
    return "sent"
