"""FastAPI app — single Vercel function handles every route.

The /api/run-digest endpoint is hit by Vercel Cron every Friday 03:00 UTC
(08:30 IST). It can also be invoked manually from the dashboard via
the /run-now button (admin-password protected).
"""
import asyncio
import base64
import os
import secrets
from urllib.parse import quote
import sys
from datetime import datetime, timedelta, timezone

# Make project root importable so `from lib.* import ...` works on Vercel.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import markdown as md
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exception_handlers import http_exception_handler
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from lib import devi
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


def _check_admin(req: Request) -> None:
    pw = os.getenv("ADMIN_PASSWORD")
    if not pw:
        raise HTTPException(500, "ADMIN_PASSWORD env var is not set on the server")
    header = req.headers.get("authorization", "")
    if not header.startswith("Basic "):
        raise HTTPException(
            401, "auth required",
            headers={"WWW-Authenticate": 'Basic realm="admin"'},
        )
    try:
        decoded = base64.b64decode(header[6:]).decode()
        _, got = decoded.split(":", 1)
    except Exception:
        raise HTTPException(401, "bad auth header",
                            headers={"WWW-Authenticate": 'Basic realm="admin"'})
    if not secrets.compare_digest(got, pw):
        raise HTTPException(401, "bad credentials",
                            headers={"WWW-Authenticate": 'Basic realm="admin"'})


@app.exception_handler(StarletteHTTPException)
async def branded_errors(request: Request, exc: StarletteHTTPException):
    """Browser pages get a DevvIT error page; API routes and non-HTML clients keep the JSON error.
    Headers (e.g. WWW-Authenticate for the admin login prompt) are passed through unchanged."""
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
        env("Admin password", "ADMIN_PASSWORD", "Protects Topics and Run now", "Missing: ADMIN_PASSWORD"),
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
    return V.dashboard(_bundle(sb), _history(sb), flash=_run_message(request.query_params))


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
    return V.pain_point_page(name, week or weeks[-1]["week_start"], weeks, threads, hist)


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
    _check_admin(request)
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


def _opportunity_rows(sb, weights: dict):
    hist, weeks, metrics, posts = _recent(sb)
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
        threads, opinion_mix(threads), W.ready(sb, "opportunities"), _flash_from(request.query_params), hist)


@app.post("/opportunity/save")
def opportunity_save(request: Request, name: str = Form(...), status: str = Form("New"), notes: str = Form("")):
    _check_admin(request)
    sb = db()
    if not W.ready(sb, "opportunities"):
        return RedirectResponse(f"/opportunity?name={quote(name)}&msg=migrate", status_code=303)
    if status not in W.STATUSES:
        raise HTTPException(400, "unknown status")
    W.save_opportunity(sb, name[:200], status, notes[:5000])
    return RedirectResponse(f"/opportunity?name={quote(name)}&msg=saved", status_code=303)


@app.post("/opportunity/analyze")
def opportunity_analyze(request: Request, name: str = Form(...)):
    _check_admin(request)
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

@app.get("/topics", response_class=HTMLResponse)
def topics_get(request: Request):
    _check_admin(request)
    sb = db()
    rows = sb.table("topics").select("*").order("id").execute()
    return V.topics_page(rows.data or [])


@app.post("/topics/add")
def topics_add(request: Request, category: str = Form(...), keywords: str = Form(...)):
    _check_admin(request)
    kws = [k.strip() for k in keywords.split(",") if k.strip()]
    if not category.strip() or not kws:
        raise HTTPException(400, "category + at least one keyword required")
    db().table("topics").insert(
        {"category": category.strip(), "keywords": kws, "active": True}
    ).execute()
    return RedirectResponse("/topics", status_code=303)


@app.post("/topics/toggle/{tid}")
def topics_toggle(request: Request, tid: int):
    _check_admin(request)
    sb = db()
    r = sb.table("topics").select("active").eq("id", tid).limit(1).execute()
    cur = r.data[0]["active"] if r.data else True
    sb.table("topics").update({"active": not cur}).eq("id", tid).execute()
    return RedirectResponse("/topics", status_code=303)


@app.post("/run-now")
def run_now(request: Request):
    """Dashboard button: run the pipeline, then go back to the brief with a summary."""
    _check_admin(request)
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
    try:
        W.finish_run(sb, run_id, "success" if result.get("ok") else "failed",
                     {**stats, **{k: v for k, v in result.items() if k != "ok"}}, result.get("error"))
    except Exception as e:
        print(f"[run] couldn't log run end: {e!r}")
    return result


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
