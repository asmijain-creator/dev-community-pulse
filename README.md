# DevvIT

**AI-powered developer community intelligence.** DevvIT turns public developer discussions into
actionable product intelligence: what developers are struggling with, which pain points are emerging,
how they trend week over week, and where the product opportunities are.

_Formerly Developer Community Pulse. The Vercel project, database tables and environment variables keep
their original names (`dev-community-pulse`), so existing deployments and data are unaffected._


Automated weekly brief for a PM at a code-review-tool startup. Every Friday
morning, scrapes developer discussions from Hacker News, Stack Overflow and
GitHub, classifies them with Gemini Flash into pain points, compares week-over-week,
and emails a product-opportunity brief.

Replaces 90 minutes of manual forum reading with a 5-minute read.

## What it does

- **Collects** last 7 days of posts from HN (Algolia API), Stack Overflow
  (StackExchange API) and GitHub (Issues search), for each keyword in Supabase.
- **Dedupes** by `source:external_id` primary key.
- **Classifies** each post with Gemini 2.5 Flash into category, normalized
  pain point, sentiment, and unresolved/resolved — JSON schema enforced.
- **Reuses prior pain-point labels** so trends don't fragment week to week.
- **Aggregates** mentions per pain point in Python/SQL (not AI — numbers are
  deterministic).
- **Compares** with last week → Rising / Falling / New.
- **Writes the brief** with Gemini: top 5 pain points, trends, unsolved
  opportunities, sales objections, 3 actions for Monday. Every claim links to
  a real post.
- **Delivers** via Resend email + dashboard.

## Architecture

```
Vercel Cron (Fri 03:00 UTC = 08:30 IST)
    └→ /api/run-digest  (FastAPI, Python on Vercel)
        ├─ Supabase: read topics
        ├─ Collect: HN + StackOverflow + GitHub  (async httpx, parallel)
        ├─ Supabase: upsert raw posts
        ├─ Gemini 2.5 Flash: tag each post (JSON schema)
        ├─ Supabase: update tagged posts
        ├─ SQL: aggregate this week + fetch last week
        ├─ Compute trends (Rising / Falling / New)
        ├─ Supabase: upsert weekly_metrics
        ├─ Gemini 2.5 Flash: write brief
        ├─ Supabase: save brief to digests
        └─ Resend: email brief to PM
```

## Setup

### 1. Supabase

Create a free project at supabase.com. Open the SQL editor and paste
[`supabase/schema.sql`](supabase/schema.sql). This creates the four tables
and seeds three default topics (Code Review / CI/CD / Developer Workflow).

Copy `Project URL` and the **service_role** key from
Settings → API — these are server-only; never expose them to the browser.

### 2. Gemini

Get a free API key from aistudio.google.com/apikey. The free tier is enough
for one Friday run per week.

### 3. Resend

Sign up at resend.com. For self-only testing, use the default
`onboarding@resend.dev` sender — it only sends to the Resend account owner's
email. For other recipients, verify a domain in the Resend dashboard.

### 4. Deploy to Vercel

```bash
# Push this repo to GitHub, then on vercel.com:
#   1. New Project → import the repo
#   2. Framework preset: "Other"
#   3. Add env vars (see .env.example)
#   4. Deploy
```

Then on the Vercel project:

- **Settings → Deployment Protection**: set Vercel Authentication to
  **Disabled** so examiners can view the public URL.
- **Settings → Environment Variables**: add every variable from
  `.env.example`. Env changes require a redeploy to take effect.
- **Settings → Cron Jobs**: the Friday 03:00 UTC schedule is auto-registered
  from `vercel.json`.

### 5. Verify

- Open `https://<your-app>.vercel.app/api/health` → expect `{"ok": true}`.
- Open `/` and click **Run now** (prompts for admin password). The first run
  pulls 14 days of data so the brief has real trend data (last week vs this week).
- Open `/topics` (same admin password) to add or pause keywords without a redeploy.

## Env vars

| Var | Required | Notes |
|---|---|---|
| `GEMINI_API_KEY` | yes | aistudio.google.com |
| `SUPABASE_URL` | yes | from Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | **server-only** |
| `ADMIN_PASSWORD` | yes | protects `/topics` and `/run-now` |
| `CRON_SECRET` | yes | Vercel sends `Authorization: Bearer <secret>` to cron paths |
| `RESEND_API_KEY` | for email | otherwise brief is only on the dashboard |
| `DIGEST_EMAIL_TO` | for email | the PM's address |
| `RESEND_FROM` | optional | default `onboarding@resend.dev` |
| `GITHUB_TOKEN` | optional | personal access token, no scopes needed, raises rate limit from 10/min to 30/min |
| `SO_KEY` | optional | raises Stack Exchange quota from 300/day to 10k/day |

## Components map

```
┌───────────────────────┐          ┌──────────────────────────┐
│  Vercel Cron Trigger   │  Fri      │  Live sources (public)   │
│  (0 3 * * 5 UTC)       │  08:30    │  • HN Algolia API        │
└──────────┬────────────┘   IST     │  • StackExchange API     │
           │                         │  • GitHub Search API      │
           ▼                         └──────────────┬───────────┘
┌───────────────────────┐                           │ async fetch
│  /api/run-digest       │◄──────────────────────────┘
│  (FastAPI on Vercel)   │
└──┬────────────────┬────┘
   │ read/write     │ classify + write
   ▼                ▼
┌────────────┐  ┌────────────────────┐
│  Supabase   │  │  Gemini 2.5 Flash  │
│  topics     │  │  • tag posts (JSON)│
│  posts      │  │  • write brief     │
│  weekly_... │  └────────────────────┘
│  digests    │
└─────┬──────┘
      │ latest brief + trend table
      ▼
┌───────────────────────┐          ┌──────────────────────────┐
│  Dashboard (/, /topics)│         │  Resend email → PM        │
│  dark Linear-style UI  │         │  Friday morning           │
└───────────────────────┘          └──────────────────────────┘
```

## Known limits

- **Vercel Hobby maxDuration = 60s.** A full run with ~20 keywords usually
  finishes in 30-50s. If you hit a timeout: reduce `MAX_PER_KW` in
  `lib/collectors.py`, drop keywords, or move to Pro (300s).
- **Reddit is not scraped** — their API blocks server-side requests from
  Vercel egress IPs without OAuth. HN + SO + GitHub cover the same ground.
- **GitHub Search unauthenticated = 10 req/min.** Set `GITHUB_TOKEN`.
- **Resend default sender** (`onboarding@resend.dev`) only delivers to the
  Resend account owner's email. Verify a domain for other recipients.

## Files

```
api/index.py             — FastAPI app, every route
lib/collectors.py        — HN / Stack Overflow / GitHub (async httpx)
lib/db.py                — Supabase client singleton
lib/gemini_tag.py        — Gemini classifier, JSON schema enforced
lib/gemini_brief.py      — Gemini brief writer
lib/metrics.py           — Trend math (Python, not AI)
lib/views.py             — HTML views (clean dark Linear-style, no templating)
supabase/schema.sql      — Four tables + seed topics
vercel.json              — Rewrites + cron + maxDuration
requirements.txt         — Python deps
```
