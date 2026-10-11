# Developer Community Pulse

A weekly AI brief for Sumit, PM of a code review automation startup: what developers are
saying about code review, CI/CD and developer workflow, which pain points are rising or falling
compared with last week, and which problems are still unsolved.

**Stack:** Python 3.12 · FastAPI · Supabase (Postgres) · Gemini Flash · Resend · Vercel (hosting + cron)

## How it works

Every Friday 03:00 UTC (8:30 AM IST) Vercel Cron calls `/api/run-digest`:

1. **Collect.** It reads active topics and keywords from Supabase, then searches Hacker News, Stack Overflow
   and GitHub Issues for the last 14 days, removing duplicates and filtering bot/log threads.
2. **Label.** Gemini Flash tags each *new* post: relevant?, category, pain point, sentiment, unresolved?
   Last month's labels are passed in so the same problem keeps the same name week to week.
3. **Count.** The SQL function `pain_point_trends()` counts this week vs last week. Trends
   (rising / falling / new / steady) are labelled in Python. The AI never counts.
4. **Write.** Gemini writes the narrative (TL;DR, top pain points, unsolved gaps, objections,
   3 actions). Code appends the exact numbers table.
5. **Deliver.** The brief is saved to Supabase, emailed via Resend and shown on the dashboard.

## Dashboard (Notion-style, ordered by Sumit's Friday journey)

| Page | Journey step | What's on it |
|---|---|---|
| 🗞️ **This week** `/` | Scan → see what's moving → act | ⚡ 30-second summary · 📊 board of Rising / New / Cooling down · 🔥 top pain points · 🧭 opportunities · 🛡️ objections · ✅ sprint checklist (tick off, copy) · 🔢 all numbers |
| 🔥 **Pain points** `/pain-points` | Dig into the evidence | Database view with All / Rising / New / Unresolved tabs and search |
| ↳ one pain point `/pain-point?name=…` | Check it's real | Mentions by week and the actual threads (source, resolved?, votes, comments) |
| 🗂️ **Archive** `/archive` | Compare weeks | Every past brief with source and email status |
| 🏷️ **Topics & keywords** `/topics` | Maintain | Edit categories and keywords; needs `ADMIN_PASSWORD` |
| ⚙️ **Runs & health** `/runs` | Operate | Setup checklist, run log with errors, **Generate brief now** |
| `/api/run-digest` | — | Cron endpoint (needs `CRON_SECRET`) |
| `/api/health` | — | JSON: which settings are missing |

Missing environment variables show a friendly "Almost there" setup page instead of an error.

## Setup

### 1. Supabase
1. Create a free project at supabase.com.
2. In **SQL Editor**, run `supabase/schema.sql`, then `supabase/seed.sql`.
   Upgrading a database created by the first version (with a `weekly_metrics` table)? Run
   `supabase/reset.sql` instead. It drops the old tables and recreates everything, so existing data is lost.
3. From **Project Settings → API**, copy the Project URL and the **service_role** key.

### 2. Keys
- **Gemini:** create an API key at aistudio.google.com.
- **Resend:** create an API key at resend.com. With the default sender `onboarding@resend.dev`,
  Resend only delivers to the email you signed up with, so use that as `DIGEST_EMAIL_TO`.
- **GitHub token (recommended):** a fine-grained token with no extra permissions raises
  search limits from 10 to 30 requests per minute.
- **Stack Exchange key (recommended):** register an app on stackapps.com. Without it, all
  Vercel apps share a 300-requests-per-day quota per IP.

### 3. Run locally
```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt pytest uvicorn python-dotenv
copy .env.example .env          # then fill in the values
python scripts/check_sources.py # live source test, no keys needed
python scripts/run_digest.py    # full pipeline once
uvicorn api.index:app --reload  # dashboard on http://127.0.0.1:8000
pytest                          # 27 tests, no network or keys needed
```

### 4. Deploy to Vercel
1. Push this folder to a GitHub repository.
2. On vercel.com, choose **Add New → Project** and import the repo (framework preset: Other).
3. Add every variable from `.env.example` under **Settings → Environment Variables**.
   `CRON_SECRET` can be any long random string; Vercel sends it to the cron route automatically.
4. Deploy, open `/api/health` to check the config, then use **Run now** on the dashboard (log in with any
   username and `ADMIN_PASSWORD`) to create the first brief.

The cron schedule is in `vercel.json` (`0 3 * * 5`). On the Hobby plan, Vercel may run it at any time
within that hour. `maxDuration` is 300 s, which needs Fluid Compute (on by default for new projects); if the
deploy rejects it, set it to 60 and lower `MAX_CLASSIFY_PER_RUN`.

## Edge cases handled

| Case | Handling |
|---|---|
| Source down / rate limited | Retry with backoff; the brief notes which source is missing; other sources still run |
| GitHub bot or agent log threads | Bot authors and threads with >300 comments are skipped |
| Off-topic keyword matches ("false positive" in face recognition) | Gemini marks them `relevant: false`; they're excluded from counts |
| Broken Gemini JSON | Schema-constrained output, Pydantic validation, retry; failed posts retry next run |
| Hallucinated post ids or categories | Unknown ids dropped, unknown categories mapped to "Other" |
| Same problem, different words | Known labels are passed back to Gemini; labels are normalised |
| Gemini inventing numbers | Numbers come from SQL; code appends the table |
| Prompt injection in posts | Posts are wrapped as untrusted data; rendered HTML is sanitised |
| First run has no "last week" | Always collects 14 days |
| Tiny numbers ("1 → 3 = +200%") | Fewer than 3 mentions is never called a trend |
| Newly added topic | Labelled "newly tracked", not "rising" |
| Cron and Run now at the same time | Run lock; the second run is skipped and logged |
| Running twice on the same day | Posts aren't re-labelled; the brief is overwritten, not duplicated |
| Email fails | The brief is still saved and shown on the dashboard; the run log records the error |
| All topics turned off | Run is skipped with a clear message |
| Deleting a topic | Topics are turned off, never deleted, so history survives |
