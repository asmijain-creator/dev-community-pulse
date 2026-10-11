-- Starting topics for a code review automation product. Sumit edits these later from /topics.
insert into topics (category, description, keywords) values
  ('Code Review Process',
   'How teams run code review: slow reviews, bottlenecks, review culture, PR size',
   array['code review', 'pull request review', 'code review bottleneck', 'large pull requests']),
  ('Automated Review Quality',
   'Bots, linters, static analysis and AI reviewers: noise, false positives, trust',
   array['false positive', 'AI code review', 'static analysis', 'linter noise']),
  ('CI/CD Integration',
   'Pipelines that gate merges: GitHub Actions, flaky tests, slow builds, merge queues',
   array['CI pipeline', 'GitHub Actions', 'flaky tests', 'merge queue']),
  ('Developer Workflow',
   'Day-to-day friction around shipping code: context switching, productivity, merge conflicts',
   array['developer productivity', 'merge conflicts'])
on conflict (category) do nothing;
