-- DevvIT migration 005: Building Now projects, activity history, pain point links and the project watchlist.
-- Additive and idempotent: creates new tables, adds nullable columns and indexes. Nothing is dropped,
-- rewritten or deleted, so existing build discussions, technologies and blockers keep their history.
-- Needs migration 003 (build_items). Safe to run more than once. Run it once in Supabase -> SQL Editor.

create extension if not exists pgcrypto;   -- gen_random_uuid()

-- One row per distinct project. Several public observations (a Show HN post, a later update, GitHub
-- releases) point at the same project through project_key, so the project keeps one history.
--   project_key: 'gh:owner/repo' (public repository) > 'url:host/path' (project site)
--                > 'name:platform:handle:name' (named by its builder) > 'item:<discussion id>' (one-off)
-- Fields below project_key are derived from the observations and refreshed after each update;
-- the observations themselves (build_items) are never rewritten.
create table if not exists build_projects (
  id                  uuid primary key default gen_random_uuid(),
  project_key         text not null unique,
  project_name        text not null,
  name_is_ai          boolean not null default false,  -- true = descriptive title written by AI, the post doesn't name it
  description         text,                            -- AI summary of the latest observation, shown labelled as AI
  category            text,
  project_url         text,
  repository_url      text,
  builder_platform    text,                            -- hn | github | stackoverflow
  builder_username    text,                            -- public handle exactly as shown on the platform
  builder_profile_url text,
  build_stage         text not null default 'unknown'
                      check (build_stage in ('idea', 'prototype', 'mvp', 'beta', 'launched', 'unknown')),
  stage_quote         text,                            -- verbatim words that state the stage
  current_focus       text,
  focus_quote         text,
  focus_observed_at   timestamptz,                     -- publication date of the post that states the focus
  first_seen_at       timestamptz not null,            -- first COLLECTED by DevvIT (not the post date)
  last_observed_at    timestamptz not null,            -- latest observation COLLECTED by DevvIT
  first_published_at  timestamptz,                     -- earliest original post date
  last_published_at   timestamptz,                     -- latest original post date
  review_status       text not null default 'ok' check (review_status in ('ok', 'flagged')),
  review_note         text not null default '',
  releases_checked_at timestamptz,                     -- last time public GitHub releases were fetched
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);
create index if not exists build_projects_last_obs_idx  on build_projects (last_observed_at desc);
create index if not exists build_projects_first_seen_idx on build_projects (first_seen_at);
create index if not exists build_projects_category_idx  on build_projects (category);
create index if not exists build_projects_stage_idx     on build_projects (build_stage);
create index if not exists build_projects_builder_idx   on build_projects (builder_platform, builder_username);
create index if not exists build_projects_name_idx      on build_projects (lower(project_name));

-- build_items stays the append-only observation log (one row per public discussion or release).
alter table build_items add column if not exists project_id  uuid references build_projects(id) on delete set null;
alter table build_items add column if not exists author      text;   -- public handle of the poster
alter table build_items add column if not exists author_url  text;
alter table build_items add column if not exists event_type  text
  check (event_type is null or event_type in ('project_announcement', 'product_launch', 'feature_update', 'public_demo',
                                              'repository_update', 'technical_question', 'reported_blocker', 'unclear'));
alter table build_items add column if not exists event_quote text;   -- verbatim words that support event_type
alter table build_items add column if not exists focus       text;   -- what the builder says they're working on now
alter table build_items add column if not exists focus_quote text;   -- verbatim support for focus
alter table build_items add column if not exists enriched_at timestamptz;   -- event/focus extraction done
create index if not exists build_items_project_idx on build_items (project_id, posted_at desc);
create index if not exists build_items_author_idx  on build_items (source, author);

-- Links from a reported blocker to an EXISTING DevvIT pain point (pain points are identified by their label).
--   same_thread: the discussion itself is tagged with that pain point by the pain point pipeline
--   ai_match:    Gemini judged the blocker and pain point describe the same problem; reason in link_basis
-- Nothing here creates pain points. link_status lets the admin confirm or reject a suggestion.
alter table build_blockers add column if not exists pain_point  text;
alter table build_blockers add column if not exists link_basis  text;
alter table build_blockers add column if not exists link_method text
  check (link_method is null or link_method in ('same_thread', 'ai_match', 'none'));
alter table build_blockers add column if not exists link_status text
  check (link_status is null or link_status in ('suggested', 'confirmed', 'rejected'));
alter table build_blockers add column if not exists linked_at   timestamptz;
create index if not exists build_blockers_pain_point_idx on build_blockers (pain_point);

-- Saved projects. DevvIT has a single owner (ADMIN_PASSWORD), like shared_reports.owner; the owner column
-- keeps the table ready for per-user accounts without changing global project records.
create table if not exists build_watchlist (
  owner       text not null default 'admin',
  project_id  uuid not null references build_projects(id) on delete cascade,
  note        text not null default '',
  alert_prefs jsonb not null default '{}',
  saved_at    timestamptz not null default now(),
  primary key (owner, project_id)
);

-- Server-only, like every DevvIT table: the app uses the service key; the public anon key gets nothing.
alter table build_projects  enable row level security;
alter table build_watchlist enable row level security;
