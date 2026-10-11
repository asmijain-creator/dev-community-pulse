-- Developer Community Pulse: run this once in the Supabase SQL editor.

-- What Sumit monitors. Edited from the /topics page; no code changes needed.
create table if not exists topics (
  id          bigserial primary key,
  category    text not null unique,
  description text not null default '',
  keywords    text[] not null default '{}',
  active      boolean not null default true,   -- soft delete keeps trend history
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- Every community post we have seen. One row per post across all runs (dedupe key = id).
-- Only id is NOT NULL so partial upserts (collector fields vs AI fields) never collide.
create table if not exists posts (
  id               text primary key,              -- "<source>:<external id>"
  source           text,                          -- hackernews | stackoverflow | github
  title            text,
  body             text,
  url              text,
  score            int default 0,
  comments         int default 0,
  is_answered      boolean,                       -- stackoverflow answered / github closed
  created_at       timestamptz,
  matched_keywords text[] default '{}',
  fetched_at       timestamptz default now(),
  -- filled in by Gemini
  relevant         boolean,
  category         text,
  pain_point       text,
  sentiment        text,
  is_unresolved    boolean,
  summary          text,
  classified_at    timestamptz,
  classify_error   text
);
create index if not exists posts_created_idx on posts (created_at);
create index if not exists posts_unclassified_idx on posts (created_at) where classified_at is null;

-- One row per pipeline run: run log + lock against double runs.
create table if not exists runs (
  id          bigserial primary key,
  trigger     text not null,                     -- cron | manual | cli
  status      text not null default 'running',   -- running | success | failed | skipped
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  stats       jsonb not null default '{}',
  error       text
);

-- One brief per day; re-running on the same day overwrites it (idempotent).
create table if not exists digests (
  period_end   date primary key,
  period_start date not null,
  content_md   text not null,
  stats        jsonb not null default '{}',
  created_at   timestamptz not null default now()
);

-- Snapshot of the numbers behind each brief, used for the dashboard table and chart.
create table if not exists digest_metrics (
  period_end    date not null references digests(period_end) on delete cascade,
  category      text not null,
  pain_point    text not null,
  mentions      int not null,
  prev_mentions int not null,
  change_pct    numeric,
  trend         text not null,
  engagement    int not null,
  unresolved    int not null,
  primary key (period_end, category, pain_point)
);

-- Week-over-week counts are done here in SQL, never by the AI.
create or replace function pain_point_trends(p_cur_start timestamptz, p_end timestamptz)
returns table (
  category      text,
  pain_point    text,
  mentions      bigint,
  prev_mentions bigint,
  engagement    bigint,
  unresolved    bigint
)
language sql stable as $$
  with labelled as (
    select category, pain_point, score, comments, is_unresolved,
           created_at >= p_cur_start as is_current
    from posts
    where relevant
      and pain_point is not null
      and created_at >= p_cur_start - (p_end - p_cur_start)
      and created_at <  p_end
  )
  select category,
         pain_point,
         count(*) filter (where is_current)                                   as mentions,
         count(*) filter (where not is_current)                               as prev_mentions,
         coalesce(sum(score + comments) filter (where is_current), 0)         as engagement,
         count(*) filter (where is_current and is_unresolved)                 as unresolved
  from labelled
  group by category, pain_point
$$;

-- The app talks to Supabase with the service-role key from the server only.
-- RLS on with no policies = the public anon key can read/write nothing.
alter table topics         enable row level security;
alter table posts          enable row level security;
alter table runs           enable row level security;
alter table digests        enable row level security;
alter table digest_metrics enable row level security;
