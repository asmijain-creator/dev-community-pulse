"""FastAPI app served by Vercel. Pages follow Sumit's Friday journey:
This week (scan -> what's moving -> evidence -> act) · Pain points (dig in) · Archive (compare)
· Topics (maintain) · Runs & health (operate)."""
import secrets
import sys
import zlib
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI, Form, HTTPException, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse  # noqa: E402
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402

from pulse.brief import list_items, split_sections  # noqa: E402
from pulse.collector import normalize_keywords  # noqa: E402
from pulse.config import get_settings  # noqa: E402
from pulse.db import Store  # noqa: E402
from pulse.emailer import safe_markdown  # noqa: E402
from pulse.pipeline import ConfigError, run_digest  # noqa: E402
from pulse.writer import TREND_ICON  # noqa: E402

app = FastAPI(title="Developer Community Pulse", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(ROOT / "pulse" / "templates"))
basic = HTTPBasic()

# Notion's tag palette. Trend colours read as "needs attention" (red) to "calming down" (green).
TAG_COLORS = ["gray", "brown", "orange", "yellow", "green", "blue", "purple", "pink", "red"]
TREND_COLOR = {"rising": "red", "new": "blue", "newly tracked": "purple", "steady": "gray",
               "falling": "green", "gone quiet": "brown"}
SOURCE_LABEL = {"hackernews": ("Hacker News", "orange"), "stackoverflow": ("Stack Overflow", "yellow"),
                "github": ("GitHub", "gray")}


def tag_color(text: str) -> str:
    """Stable colour per category name, like Notion select options."""
    return TAG_COLORS[1 + zlib.crc32(str(text).encode()) % (len(TAG_COLORS) - 1)]


ACRONYMS = {w: w.upper() for w in ("ai", "pr", "ci", "cd", "ci/cd", "api", "ide", "llm", "sast", "qa", "ui", "ux", "sla")}
ACRONYMS.update({w + "s": w.upper() + "s" for w in ("pr", "api", "llm", "sla", "ide")})


def label(text: str) -> str:
    """'review latency on large prs' -> 'Review latency on large PRs' (stored labels are lowercase)."""
    words = [ACRONYMS.get(w.lower(), w) for w in str(text).split(" ")]
    out = " ".join(words)
    return out[:1].upper() + out[1:]


templates.env.filters["label"] = label
templates.env.filters["md"] = safe_markdown
templates.env.filters["tag_color"] = tag_color
templates.env.globals.update(trend_icon=TREND_ICON, trend_color=TREND_COLOR, source_label=SOURCE_LABEL,
                             quote=quote)


class NotConfigured(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing


def store() -> Store:
    s = get_settings()
    if missing := s.missing():
        raise NotConfigured(missing)
    return Store(s.supabase_url, s.supabase_service_key)


@app.exception_handler(NotConfigured)
def not_configured(request: Request, exc: NotConfigured):
    return templates.TemplateResponse(request, "setup.html", {"missing": exc.missing, "nav": ""}, status_code=503)


def require_admin(creds: HTTPBasicCredentials = Depends(basic)) -> None:
    password = get_settings().admin_password
    if not password:
        raise HTTPException(403, "Set ADMIN_PASSWORD to enable admin pages")
    if not secrets.compare_digest(creds.password.encode(), password.encode()):
        raise HTTPException(401, "Wrong password", headers={"WWW-Authenticate": "Basic"})


def page(request: Request, name: str, nav: str, **ctx):
    return templates.TemplateResponse(request, name, {"nav": nav, "msg": request.query_params.get("msg", ""), **ctx})


def brief_context(db: Store, digest: dict) -> dict:
    metrics = db.digest_metrics(digest["period_end"])
    active = [m for m in metrics if m["mentions"] > 0]
    sections = split_sections(digest["content_md"])
    board = {
        "rising": [m for m in active if m["trend"] == "rising"][:4],
        "new": [m for m in active if m["trend"] in ("new", "newly tracked")][:4],
        "falling": [m for m in metrics if m["trend"] in ("falling", "gone quiet")][:4],
    }
    return {
        "digest": digest, "metrics": metrics, "sections": sections, "board": board,
        "actions": list_items(sections.get("actions", "")),
        "sources": (digest.get("stats") or {}).get("source_status", {}),
    }


# ---------- 1. This week: the Friday brief ----------

@app.get("/", response_class=HTMLResponse)
def this_week(request: Request):
    db = store()
    digest = db.latest_digest()
    if not digest:
        return page(request, "empty.html", "week", topics=db.active_topics())
    return page(request, "brief.html", "week", **brief_context(db, digest), latest=True)


# ---------- 2. Pain points: dig into the evidence ----------

@app.get("/pain-points", response_class=HTMLResponse)
def pain_points(request: Request):
    db = store()
    digest = db.latest_digest()
    metrics = db.digest_metrics(digest["period_end"]) if digest else []
    return page(request, "pain_points.html", "points", digest=digest, metrics=metrics)


@app.get("/pain-point", response_class=HTMLResponse)
def pain_point(request: Request, name: str):
    db = store()
    history = db.metric_history([name])
    posts = db.pain_point_posts(name)
    if not history and not posts:
        raise HTTPException(404, "Unknown pain point")
    latest = history[-1] if history else None
    peak = max((h["mentions"] for h in history), default=1) or 1
    return page(request, "pain_point.html", "points", point=name, history=history[-12:], posts=posts,
                latest=latest, peak=peak, category=(latest or posts[0])["category"])


# ---------- 3. Archive: compare with earlier weeks ----------

@app.get("/archive", response_class=HTMLResponse)
def archive(request: Request):
    return page(request, "archive.html", "archive", digests=store().list_digests())


@app.get("/history")
def history_redirect():
    return RedirectResponse("/archive", 301)


@app.get("/digest/{period_end}", response_class=HTMLResponse)
def digest_page(request: Request, period_end: str):
    db = store()
    digest = db.get_digest(period_end)
    if not digest:
        raise HTTPException(404, "No brief for that date")
    return page(request, "brief.html", "archive", **brief_context(db, digest), latest=False)


# ---------- 4. Topics: keep the radar pointed at the right things ----------

@app.get("/topics", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def topics_page(request: Request):
    return page(request, "topics.html", "topics", topics=store().all_topics())


def _keywords(raw: str) -> list[str]:
    return normalize_keywords(raw.replace("\n", ",").split(","))


@app.post("/topics", dependencies=[Depends(require_admin)])
def add_topic(category: str = Form(...), description: str = Form(""), keywords: str = Form(...)):
    category, kws = " ".join(category.split()), _keywords(keywords)
    if not category or not kws:
        return RedirectResponse("/topics?msg=" + quote("Category and at least one keyword are required"), 303)
    db = store()
    if any(t["category"].lower() == category.lower() for t in db.all_topics()):
        return RedirectResponse("/topics?msg=" + quote(f"'{category}' already exists"), 303)
    db.add_topic(category, description.strip(), kws)
    return RedirectResponse("/topics?msg=" + quote(f"Added '{category}'"), 303)


@app.post("/topics/{topic_id}", dependencies=[Depends(require_admin)])
def update_topic(topic_id: int, description: str = Form(""), keywords: str = Form(...),
                 active: str = Form("off")):
    kws = _keywords(keywords)
    if not kws:
        return RedirectResponse("/topics?msg=" + quote("A topic needs at least one keyword"), 303)
    # Topics are deactivated, never deleted, so their trend history survives.
    store().update_topic(topic_id, description=description.strip(), keywords=kws, active=active == "on")
    return RedirectResponse("/topics?msg=" + quote("Saved"), 303)


# ---------- 5. Runs & health: is the machine working? ----------

def health_checks() -> list[dict]:
    s = get_settings()
    return [
        {"name": "Supabase", "ok": bool(s.supabase_url and s.supabase_service_key), "need": True,
         "hint": "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY"},
        {"name": "Gemini Flash", "ok": bool(s.gemini_api_key), "need": True, "hint": f"GEMINI_API_KEY · {s.gemini_model}"},
        {"name": "Friday cron", "ok": bool(s.cron_secret), "need": True, "hint": "CRON_SECRET"},
        {"name": "Admin password", "ok": bool(s.admin_password), "need": True, "hint": "ADMIN_PASSWORD"},
        {"name": "Email delivery", "ok": bool(s.resend_api_key and s.digest_email_to), "need": False,
         "hint": "RESEND_API_KEY and DIGEST_EMAIL_TO"},
        {"name": "GitHub token", "ok": bool(s.github_token), "need": False, "hint": "GITHUB_TOKEN: 3x search rate limit"},
        {"name": "Stack Exchange key", "ok": bool(s.stackexchange_key), "need": False,
         "hint": "STACKEXCHANGE_KEY: 10,000 instead of 300 requests/day"},
    ]


@app.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request):
    return page(request, "runs.html", "runs", runs=store().recent_runs(20), checks=health_checks())


@app.post("/run", dependencies=[Depends(require_admin)])
async def run_now():
    try:
        result = await run_digest("manual")
    except ConfigError as exc:
        return RedirectResponse("/runs?msg=" + quote(str(exc)), 303)
    except Exception as exc:
        return RedirectResponse("/runs?msg=" + quote(f"Run failed: {exc}"[:300]), 303)
    if result["status"] == "skipped":
        return RedirectResponse("/runs?msg=" + quote(f"Skipped: {result['reason']}"), 303)
    return RedirectResponse("/?msg=" + quote(f"Fresh brief generated in {result.get('seconds')}s"), 303)


# ---------- cron + health API ----------

@app.get("/api/run-digest")
async def cron_run(request: Request):
    secret = get_settings().cron_secret
    # Vercel Cron sends "Authorization: Bearer <CRON_SECRET>" automatically when CRON_SECRET is set.
    if not secret or not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {secret}"):
        raise HTTPException(401, "Unauthorized")
    try:
        return await run_digest("cron")
    except ConfigError as exc:
        return JSONResponse({"status": "failed", "error": str(exc)}, 500)
    except Exception as exc:
        return JSONResponse({"status": "failed", "error": f"{exc.__class__.__name__}: {exc}"[:500]}, 500)


@app.get("/api/health")
def health():
    s = get_settings()
    return {
        "ok": not s.missing(),
        "missing": s.missing(),
        "email_configured": bool(s.resend_api_key and s.digest_email_to),
        "cron_secret_set": bool(s.cron_secret),
        "github_token_set": bool(s.github_token),
        "model": s.gemini_model,
    }
