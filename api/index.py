"""FastAPI app served by Vercel: dashboard, topics editor, history, and the cron endpoint."""
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI, Form, HTTPException, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse  # noqa: E402
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402

from pulse.collector import normalize_keywords  # noqa: E402
from pulse.config import get_settings  # noqa: E402
from pulse.db import Store  # noqa: E402
from pulse.emailer import safe_markdown  # noqa: E402
from pulse.pipeline import ConfigError, run_digest  # noqa: E402
from pulse.writer import TREND_ICON  # noqa: E402

app = FastAPI(title="Developer Community Pulse", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(ROOT / "pulse" / "templates"))
templates.env.filters["md"] = safe_markdown
templates.env.globals["trend_icon"] = TREND_ICON
basic = HTTPBasic()


def store() -> Store:
    s = get_settings()
    if missing := s.missing():
        raise HTTPException(500, f"Server not configured. Missing: {', '.join(missing)}")
    return Store(s.supabase_url, s.supabase_service_key)


def require_admin(creds: HTTPBasicCredentials = Depends(basic)) -> None:
    password = get_settings().admin_password
    if not password:
        raise HTTPException(403, "Set ADMIN_PASSWORD to enable admin pages")
    if not secrets.compare_digest(creds.password.encode(), password.encode()):
        raise HTTPException(401, "Wrong password", headers={"WWW-Authenticate": "Basic"})


# ---------- pages ----------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, msg: str = ""):
    db = store()
    digest = db.latest_digest()
    metrics = db.digest_metrics(digest["period_end"]) if digest else []
    top = [m["pain_point"] for m in metrics if m["mentions"] > 0][:5]
    history: dict[str, list] = {p: [] for p in top}
    for row in db.metric_history(top):
        history[row["pain_point"]].append(row)
    peak = max((r["mentions"] for rows in history.values() for r in rows), default=1)
    return templates.TemplateResponse(request, "index.html", {
        "digest": digest, "metrics": metrics[:15], "history": history, "peak": peak,
        "runs": db.recent_runs(), "msg": msg,
    })


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    return templates.TemplateResponse(request, "history.html", {"digests": store().list_digests()})


@app.get("/digest/{period_end}", response_class=HTMLResponse)
def digest_page(request: Request, period_end: str):
    db = store()
    digest = db.get_digest(period_end)
    if not digest:
        raise HTTPException(404, "No brief for that date")
    return templates.TemplateResponse(request, "digest.html", {
        "digest": digest, "metrics": db.digest_metrics(period_end),
    })


# ---------- admin: topics + run now ----------

@app.get("/topics", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def topics_page(request: Request, msg: str = ""):
    return templates.TemplateResponse(request, "topics.html", {"topics": store().all_topics(), "msg": msg})


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


@app.post("/run", dependencies=[Depends(require_admin)])
async def run_now():
    try:
        result = await run_digest("manual")
    except ConfigError as exc:
        return RedirectResponse("/?msg=" + quote(str(exc)), 303)
    except Exception as exc:
        return RedirectResponse("/?msg=" + quote(f"Run failed: {exc}"[:300]), 303)
    if result["status"] == "skipped":
        return RedirectResponse("/?msg=" + quote(f"Skipped: {result['reason']}"), 303)
    return RedirectResponse("/?msg=" + quote(f"Brief generated in {result.get('seconds')}s"), 303)


# ---------- cron + health ----------

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
