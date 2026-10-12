-- DevvIT migration 002: research workspace, radar, opportunities, evidence, alerts.
-- Additive and idempotent: only creates new tables/columns and indexes. Nothing is dropped or rewritten,
-- so existing posts, weekly_metrics, digests and topics are untouched. Safe to run more than once.
-- Run it once in Supabase -> SQL Editor.

-- ---------- monitoring ----------
alter table topics add column if not exists exclude_terms text[] not null default '{}';

-- One row per pipeline run: data freshness, per-source coverage, failures, duplicate-run protection.
create table if not exists runs (
  id          bigserial primary key,
  trigger     text not null,                       -- cron | manual
  status      text not null default 'running',     -- running | success | failed
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  stats       jsonb not null default '{}',         -- per-source counts, failures, tagged, pain points
  error       text
);
create index if not exists runs_started_idx on runs (started_at desc);

-- ---------- enrichment (filled by Gemini, new threads each run + one-time backfill) ----------
alter table posts add column if not exists summary     text;          -- AI summary, shown labelled as AI
alter table posts add column if not exists enriched_at timestamptz;

create table if not exists tool_mentions (
  id                 bigserial primary key,
  post_id            text not null references posts(id) on delete cascade,
  tool               text not null,                -- normalised tool / framework name
  sentiment          text not null default 'unknown'
                     check (sentiment in ('positive', 'negative', 'mixed', 'unknown')),
  praise             text,                         -- what the developer liked, if stated
  complaint          text,                         -- what they disliked, if stated
  missing_capability text,                         -- what they asked for, if stated
  created_at         timestamptz not null default now(),
  unique (post_id, tool)
);
create index if not exists tool_mentions_tool_idx on tool_mentions (tool);

-- ---------- radar ----------
create table if not exists radar_state (
  finding_key text primary key,                    -- stable key for the underlying issue (no duplicate alerts)
  label       text not null,
  status      text not null default 'new' check (status in ('new', 'relevant', 'dismissed', 'monitored')),
  first_seen  date,
  updated_at  timestamptz not null default now()
);

-- ---------- opportunities ----------
create table if not exists opportunities (
  pain_point text primary key,
  status     text not null default 'New'
             check (status in ('New', 'Investigating', 'Validating', 'Prioritized', 'In progress', 'Dismissed')),
  notes      text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists opportunity_log (
  id         bigserial primary key,
  pain_point text not null,
  status     text,
  note       text,
  created_at timestamptz not null default now()
);
-- Cached Gemini analysis per pain point and week, so it isn't regenerated on every view.
create table if not exists opportunity_insights (
  pain_point text not null,
  week_start date not null,
  content    jsonb not null,
  created_at timestamptz not null default now(),
  primary key (pain_point, week_start)
);

-- ---------- research library ----------
create table if not exists bookmarks (
  post_id    text primary key references posts(id) on delete cascade,
  note       text not null default '',
  created_at timestamptz not null default now()
);
create table if not exists collections (
  id          bigserial primary key,
  name        text not null unique,
  description text not null default '',
  created_at  timestamptz not null default now()
);
create table if not exists collection_items (
  collection_id bigint not null references collections(id) on delete cascade,
  post_id       text not null references posts(id) on delete cascade,
  note          text not null default '',
  added_at      timestamptz not null default now(),
  primary key (collection_id, post_id)
);
create table if not exists saved_questions (
  id         bigserial primary key,
  question   text not null,
  answer_md  text not null,
  evidence   jsonb not null default '{}',          -- date range, thread count, cited links
  created_at timestamptz not null default now()
);
create table if not exists reports (
  id         bigserial primary key,
  title      text not null,
  params     jsonb not null default '{}',
  content_md text not null,
  created_at timestamptz not null default now()
);

-- ---------- sprint planning ----------
create table if not exists plans (
  id          bigserial primary key,
  pain_point  text not null,
  problem     text not null default '',
  assumption  text not null default '',
  experiments text not null default '',
  questions   text not null default '',
  metrics     text not null default '',
  status      text not null default 'Draft' check (status in ('Draft', 'Ready', 'In progress', 'Done', 'Dropped')),
  notes       text not null default '',
  ai_draft    jsonb,                               -- AI suggestion kept separate until the user saves fields
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- ---------- alerts ----------
create table if not exists alert_rules (
  id         bigserial primary key,
  kind       text not null check (kind in ('spike', 'new_theme', 'unresolved', 'topic_change', 'stale')),
  target     text,                                 -- pain point or category; null = any
  threshold  numeric,
  active     boolean not null default true,
  created_at timestamptz not null default now()
);
create table if not exists alerts (
  id         bigserial primary key,
  rule_id    bigint references alert_rules(id) on delete cascade,
  dedupe_key text not null unique,                 -- same event never alerts twice
  title      text not null,
  reason     text not null,
  evidence   jsonb not null default '[]',
  week_start date,
  created_at timestamptz not null default now(),
  read_at    timestamptz,
  delivery   text not null default 'in-app'        -- in-app | email sent | email failed: ...
);

-- The app talks to Supabase with the service-role key from the server only.
-- RLS on with no policies = the public anon key can read/write none of these tables.
alter table runs                 enable row level security;
alter table tool_mentions        enable row level security;
alter table radar_state          enable row level security;
alter table opportunities        enable row level security;
alter table opportunity_log      enable row level security;
alter table opportunity_insights enable row level security;
alter table bookmarks            enable row level security;
alter table collections          enable row level security;
alter table collection_items     enable row level security;
alter table saved_questions      enable row level security;
alter table reports              enable row level security;
alter table plans                enable row level security;
alter table alert_rules          enable row level security;
alter table alerts               enable row level security;
