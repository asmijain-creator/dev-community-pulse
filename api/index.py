"""FastAPI app — single Vercel function handles every route.

The /api/run-digest endpoint is hit by Vercel Cron every Friday 03:00 UTC
(08:30 IST). It can also be invoked manually from the dashboard via
the /run-now button (admin-password protected).
"""
import asyncio
import base64
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone

# Make project root importable so `from lib.* import ...` works on Vercel.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import markdown as md
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from lib import views as V
from lib.collectors import collect
from lib.db import db
from lib.gemini_brief import write_brief
from lib.gemini_tag import tag_batch
from lib.metrics import aggregate, compute_trends, week_start_for

try:
    import resend
except ImportError:
    resend = None

app = FastAPI(title="Dev Community Pulse")

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


# ---------- public ----------

@app.get("/api/health")
def health():
    ok, missing = _env_check()
    return {"ok": ok, "missing": missing, "resend": resend is not None}


@app.get("/", response_class=HTMLResponse)
def home():
    ok, missing = _env_check()
    if not ok:
        return HTMLResponse(V.not_configured(missing))
    sb = db()
    latest = sb.table("digests").select("*").order("week_start", desc=True).limit(1).execute()
    metrics_rows: list[dict] = []
    ws = None
    brief_md = "_No brief yet. Click **Run now** above to generate the first one._"
    if latest.data:
        ws = latest.data[0]["week_start"]
        brief_md = latest.data[0]["content_md"] or brief_md
        m = sb.table("weekly_metrics").select("*").eq("week_start", ws) \
            .order("mention_count", desc=True).execute()
        metrics_rows = m.data or []
    history = sb.table("digests").select("week_start") \
        .order("week_start", desc=True).limit(12).execute()
    return V.dashboard(md.markdown(brief_md), metrics_rows, history.data or [], ws)


@app.get("/history/{week}", response_class=HTMLResponse)
def history_item(week: str):
    sb = db()
    r = sb.table("digests").select("*").eq("week_start", week).limit(1).execute()
    if not r.data:
        raise HTTPException(404, "no brief for that week")
    m = sb.table("weekly_metrics").select("*").eq("week_start", week) \
        .order("mention_count", desc=True).execute()
    hist = sb.table("digests").select("week_start") \
        .order("week_start", desc=True).limit(12).execute()
    return V.dashboard(md.markdown(r.data[0]["content_md"] or ""),
                       m.data or [], hist.data or [], week)


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
    _check_admin(request)
    return _do_run(days_back=7)


# ---------- cron ----------

@app.get("/api/run-digest")
def api_run_digest(request: Request):
    _check_cron_auth(request)
    # First-run trick: no prior weekly_metrics → pull 14 days so we can
    # split into "last week" + "this week" and show real trends on day 1.
    prev = db().table("weekly_metrics").select("week_start").limit(1).execute()
    days = 7 if prev.data else 14
    return _do_run(days_back=days)


# ---------- pipeline ----------

def _do_run(days_back: int = 7) -> dict:
    sb = db()
    today = datetime.now(timezone.utc).date()
    this_week = week_start_for(today)
    last_week = this_week - timedelta(days=7)

    topics_rows = sb.table("topics").select("*").eq("active", True).execute().data or []
    if not topics_rows:
        return {"ok": False, "error": "no active topics — seed via supabase/schema.sql or /topics"}

    topics = [
        {"id": t["id"], "category": t["category"], "keywords": t["keywords"]}
        for t in topics_rows
    ]

    # 1. Collect from live sources (async parallel across keywords × sources)
    posts = asyncio.run(collect(topics, days_back=days_back))

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
    untagged = sb.table("posts") \
        .select("id,title,body,created_at,topic_id,score,comments,url") \
        .is_("pain_point", "null") \
        .gte("created_at", cutoff) \
        .limit(300) \
        .execute().data or []

    categories = [t["category"] for t in topics_rows] + ["Other"]
    prior = sb.table("posts").select("pain_point") \
        .not_.is_("pain_point", "null").limit(500).execute().data or []
    prior_labels = sorted({p["pain_point"] for p in prior if p.get("pain_point")})

    # 4. Tag in batches
    tagged = 0
    for i in range(0, len(untagged), TAG_BATCH_SIZE):
        batch = untagged[i:i + TAG_BATCH_SIZE]
        try:
            tags = tag_batch(batch, categories, prior_labels)
        except Exception as e:
            print(f"[run] tag_batch error: {e}")
            continue
        tag_by_id = {t["post_id"]: t for t in tags if t.get("post_id")}
        for p in batch:
            t = tag_by_id.get(p["id"])
            if not t:
                continue
            created = datetime.fromisoformat(
                p["created_at"].replace("Z", "+00:00")
            ).date()
            ws = week_start_for(created).isoformat()
            if t.get("relevant", True):
                update = {
                    "pain_point": (t.get("pain_point") or "").strip().lower()[:100] or None,
                    "category": (t.get("category") or "Other")[:60],
                    "sentiment": t.get("sentiment"),
                    "is_unresolved": bool(t.get("is_unresolved")),
                    "week_start": ws,
                }
            else:
                update = {"pain_point": None, "week_start": None, "category": None}
            sb.table("posts").update(update).eq("id", p["id"]).execute()
            tagged += 1

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
        email_status = _send_email(brief, this_week.isoformat())
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


def _send_email(brief_md: str, week: str) -> str:
    key = os.getenv("RESEND_API_KEY")
    to = os.getenv("DIGEST_EMAIL_TO")
    if not (key and to):
        return "no RESEND_API_KEY or DIGEST_EMAIL_TO"
    if resend is None:
        return "resend package missing"
    resend.api_key = key
    sender = os.getenv("RESEND_FROM", "onboarding@resend.dev")
    html = md.markdown(brief_md)
    resend.Emails.send({
        "from": sender,
        "to": [to],
        "subject": f"Dev Community Pulse — week of {week}",
        "html": html,
    })
    return "sent"
