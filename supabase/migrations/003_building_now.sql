-- DevvIT migration 003: Building Now (what developers are publicly building).
-- Additive and idempotent: only creates new tables and indexes. Existing tables (posts, weekly_metrics,
-- digests, topics and everything from migration 002) are not touched. Safe to run more than once.
-- Independent of migration 002: either can be run first.
-- Run it once in Supabase -> SQL Editor.

-- One row per public discussion that was classified, relevant or not. Irrelevant rows are kept so the
-- same discussion is never sent to Gemini twice. Rows are never deleted or rewritten by the app.
create table if not exists build_items (
  discussion_id    text primary key,                 -- same id format as posts.id, e.g. 'hn:41234567'
  source           text not null,                    -- hn | stackoverflow | github
  origin           text not null,                    -- show_hn (build-focused collection) | posts (existing thread)
  discussion_url   text not null,                    -- the original public discussion
  project_url      text,                             -- link the author shared, when there is one
  title_raw        text not null,                    -- discussion title exactly as posted
  posted_at        timestamptz not null,
  score            int not null default 0,
  comments         int not null default 0,
  in_posts         boolean not null default false,   -- the same thread is also in posts (pain point pipeline)
  relevant         boolean not null,                 -- true = describes build activity
  exclusion_reason text,                             -- why it was excluded (not_build, advertisement, job_post, low_confidence…)
  activity_type    text,                             -- side_project | product | prototype | open_source | experiment | tool | other
  project_title    text,
  title_is_ai      boolean not null default false,   -- true = descriptive title written by AI (post doesn't name it)
  summary          text,                             -- AI summary, shown labelled as AI
  category         text,
  stage            text,                             -- only set when the post states it (stage_quote is verbatim)
  stage_quote      text,
  excerpt          text,                             -- verbatim text from the post, checked by the server
  confidence       real,                             -- Gemini's own 0-1 classification confidence
  model            text,
  classified_at    timestamptz not null default now()
);
create index if not exists build_items_posted_idx on build_items (posted_at desc);
create index if not exists build_items_url_idx on build_items (discussion_url);
create index if not exists build_items_relevant_idx on build_items (relevant, posted_at desc);

-- Technologies mentioned in a build discussion. explicit = the name appears in the post text;
-- otherwise it is an AI inference and is labelled as such (and left out of counts).
create table if not exists build_technologies (
  id             bigserial primary key,
  discussion_id  text not null references build_items(discussion_id) on delete cascade,
  name           text not null,                      -- display name, e.g. 'Next.js'
  key            text not null,                      -- normalised key, e.g. 'nextjs'
  kind           text not null default 'other',      -- framework | language | api | ai_model | dev_tool | infrastructure | database | other
  explicit       boolean not null,
  unique (discussion_id, key)
);
create index if not exists build_technologies_key_idx on build_technologies (key);

-- Problems builders report. explicit = the evidence quote appears verbatim in the post.
create table if not exists build_blockers (
  id             bigserial primary key,
  discussion_id  text not null references build_items(discussion_id) on delete cascade,
  kind           text not null,                      -- integration | deployment | api_limits | tool_reliability | performance | testing_debugging | ai_agent_reliability | code_review | other
  detail         text not null,
  quote          text,
  explicit       boolean not null
);
create index if not exists build_blockers_item_idx on build_blockers (discussion_id);
create index if not exists build_blockers_kind_idx on build_blockers (kind);

-- One row per Building Now update: what was collected, classified, skipped or failed (freshness + coverage).
create table if not exists build_refreshes (
  id           bigserial primary key,
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  trigger      text not null,                        -- cron | manual
  stats        jsonb not null default '{}'
);
create index if not exists build_refreshes_started_idx on build_refreshes (started_at desc);

-- Server-only access, like the other workspace tables: the app uses the service key, the public anon key gets nothing.
alter table build_items        enable row level security;
alter table build_technologies enable row level security;
alter table build_blockers     enable row level security;
alter table build_refreshes    enable row level security;
