-- Dev Community Pulse schema
-- Run this once in Supabase SQL editor.

create table if not exists topics (
  id serial primary key,
  category text not null,
  keywords text[] not null,
  active boolean default true,
  created_at timestamptz default now()
);

create table if not exists posts (
  id text primary key,                 -- "{source}:{external_id}"
  source text not null,                -- hn | stackoverflow | github
  title text,
  body text,
  url text,
  score int default 0,
  comments int default 0,
  created_at timestamptz,
  topic_id int references topics(id) on delete set null,
  pain_point text,                     -- Gemini-normalized label
  category text,                       -- Gemini-chosen category
  sentiment text,                      -- negative | neutral | positive
  is_unresolved boolean,
  week_start date,                     -- Friday-to-Thursday week bucket
  inserted_at timestamptz default now()
);

create index if not exists posts_week_start_idx on posts(week_start);
create index if not exists posts_pain_point_idx on posts(pain_point);
create index if not exists posts_created_at_idx on posts(created_at);

create table if not exists weekly_metrics (
  week_start date not null,
  pain_point text not null,
  category text,
  mention_count int default 0,
  engagement int default 0,
  unresolved_count int default 0,
  primary key (week_start, pain_point)
);

create table if not exists digests (
  week_start date primary key,
  content_md text,
  created_at timestamptz default now()
);

-- Seed topics (edit any time from /topics or here)
insert into topics (category, keywords) values
  ('Code Review',
    array['code review','pr review','pull request review','code reviewer',
          'false positive','noisy reviews','review bot','review automation',
          'code review culture']),
  ('CI/CD',
    array['ci pipeline','github actions','flaky tests','build time',
          'ci failing','pipeline slow','ci cd','jenkins slow','test flakiness']),
  ('Developer Workflow',
    array['developer productivity','dev experience','local setup',
          'onboarding developers','git workflow','merge conflicts','monorepo'])
on conflict do nothing;
