-- DevvIT migration 004: shared reports (Share feature).
-- Additive and idempotent: creates one new table. Nothing existing is changed. Safe to run more than once.
-- Independent of migrations 002 and 003. Run it once in Supabase -> SQL Editor.
--
-- A shared report is a frozen snapshot: the content shown to recipients is stored here when the report is
-- created and never recomputed, so later data changes don't silently change a report that was sent.
-- The share link itself is NOT stored: only token_hash (SHA-256 of the link token, used for lookup) and
-- token_nonce (from which the server re-derives the link with a server-side secret, so the owner can copy
-- it again). A copy of this table alone is not enough to open any report.

create table if not exists shared_reports (
  id                bigserial primary key,           -- internal only, never shown to recipients
  owner             text not null default 'admin',   -- DevvIT has a single admin owner (ADMIN_PASSWORD)
  kind              text not null check (kind in ('pain_point', 'opportunity', 'combined', 'weekly')),
  title             text not null,
  refs              jsonb not null default '[]',     -- what was selected, e.g. [{"type":"pain_point","name":"…"}]
  snapshot          jsonb not null,                  -- exactly what recipients see
  visibility        text not null default 'unlisted' check (visibility in ('private', 'unlisted')),
  token_hash        text not null unique,
  token_nonce       text not null,
  created_at        timestamptz not null default now(),
  expires_at        timestamptz,                     -- null = no expiry
  revoked_at        timestamptz,                     -- set = link stops working on the server
  last_accessed_at  timestamptz                      -- coarse (updated at most hourly), no visitor details
);
create index if not exists shared_reports_created_idx on shared_reports (created_at desc);

-- Server-only, like the other DevvIT tables: the app uses the service key; the public anon key can't read it.
alter table shared_reports enable row level security;
