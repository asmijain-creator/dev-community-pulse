"""Plain HTML views — no templating engine. Clean dark Linear-style."""

BASE_CSS = """
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    background: #0a0a0a; color: #e5e5e5;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', system-ui, sans-serif;
    margin: 0; padding: 0; line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 920px; margin: 0 auto; padding: 48px 24px 96px; }
  h1 { font-size: 28px; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 4px; }
  h2 { font-size: 20px; font-weight: 600; margin: 36px 0 14px; letter-spacing: -0.01em; }
  h3 { font-size: 15px; font-weight: 500; color: #a3a3a3; margin: 20px 0 8px; }
  .sub { color: #737373; font-size: 13px; margin-bottom: 24px; }
  a { color: #8ab4f8; text-decoration: none; }
  a:hover { text-decoration: underline; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0 24px;
          background: #0f0f0f; border: 1px solid #1f1f1f; border-radius: 8px; overflow: hidden; }
  th, td { text-align: left; padding: 11px 14px; border-bottom: 1px solid #1a1a1a; font-size: 13px; }
  tr:last-child td { border-bottom: none; }
  th { color: #737373; font-weight: 500; text-transform: uppercase;
       letter-spacing: 0.04em; font-size: 10.5px; background: #111; }
  .brief { background: #0f0f0f; border: 1px solid #1f1f1f; border-radius: 10px;
           padding: 24px 28px; }
  .brief p { margin: 10px 0; }
  .brief ul, .brief ol { padding-left: 22px; }
  .brief li { margin: 4px 0; }
  .brief code { background: #1a1a1a; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
  .brief h2 { margin-top: 24px; font-size: 17px; border-top: 1px solid #1f1f1f;
              padding-top: 20px; }
  .brief h2:first-child { border-top: none; padding-top: 0; margin-top: 0; }
  .nav { display: flex; gap: 20px; margin: 20px 0 28px; font-size: 13px;
         padding-bottom: 16px; border-bottom: 1px solid #1a1a1a; }
  .nav a { color: #a3a3a3; }
  .nav a:hover { color: #fff; text-decoration: none; }
  .btn { display: inline-block; background: #262626; color: #fff; border: 1px solid #333;
         border-radius: 6px; padding: 8px 14px; font-size: 13px; cursor: pointer;
         font-family: inherit; }
  .btn:hover { background: #333; }
  .btn-primary { background: #2563eb; border-color: #2563eb; }
  .btn-primary:hover { background: #1d4ed8; }
  form.inline { display: inline; margin-right: 6px; }
  input, select {
    background: #0f0f0f; color: #e5e5e5; border: 1px solid #262626;
    border-radius: 6px; padding: 8px 10px; font-size: 13px; font-family: inherit;
  }
  input:focus { outline: none; border-color: #3b82f6; }
  input[type=text] { width: 240px; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 12px;
          background: #1f1f1f; font-size: 11px; color: #a3a3a3; }
  .trend-up { color: #4ade80; }
  .trend-down { color: #f87171; }
  .trend-new { color: #fbbf24; }
  .muted { color: #737373; }
  .flash { background: #0f1b2d; border: 1px solid #1e3a5f; color: #93c5fd;
           padding: 10px 14px; border-radius: 6px; margin: 12px 0; font-size: 13px; }
  .err { background: #2d0f0f; border: 1px solid #5f1e1e; color: #fca5a5; }
</style>
"""

NAV = """
<div class="nav">
  <a href="/">Latest brief</a>
  <a href="/topics">Topics</a>
  <a href="/api/health">Health</a>
</div>
"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
{BASE_CSS}
</head><body><div class="wrap">{body}</div></body></html>"""


def not_configured(missing: list[str]) -> str:
    items = "".join(f"<li><code>{m}</code></li>" for m in missing)
    body = f"""
<h1>Server not configured</h1>
<div class="sub">Set these environment variables on Vercel, then redeploy
(env changes only take effect after a redeploy).</div>
<ul>{items}</ul>
<p class="muted">After redeploy, open <a href="/api/health">/api/health</a>
to confirm. Then come back to <a href="/">/</a> and click <b>Run now</b>.</p>
"""
    return _page("Not configured", body)


def dashboard(brief_html: str, metrics_rows: list[dict], history: list[dict],
              week_start: str | None, flash: str | None = None) -> str:
    rows_html = ""
    for m in metrics_rows[:25]:
        rows_html += (
            f"<tr><td>{m['pain_point']}</td>"
            f"<td>{m.get('category') or ''}</td>"
            f"<td>{m['mention_count']}</td>"
            f"<td>{m.get('unresolved_count', 0)}</td>"
            f"<td>{m.get('engagement', 0)}</td></tr>"
        )
    if not rows_html:
        rows_html = ("<tr><td colspan=5 class='muted'>"
                     "No metrics yet. Click <b>Run now</b> to generate the first brief."
                     "</td></tr>")
    hist_html = "".join(
        f"<li><a href='/history/{h['week_start']}'>{h['week_start']}</a></li>"
        for h in history
    )
    week_sub = f"Week of {week_start}" if week_start else "No brief yet"
    flash_html = f"<div class='flash'>{flash}</div>" if flash else ""
    body = f"""
<h1>Dev Community Pulse</h1>
<div class="sub">{week_sub} · pain points, trends, and product gaps from HN, Stack Overflow, GitHub.</div>
{NAV}
{flash_html}
<form class="inline" method="post" action="/run-now">
  <button class="btn btn-primary" type="submit">Run now</button>
</form>
<span class="muted" style="font-size:12px; margin-left:8px">
  Fetches last 7 days, tags with Gemini, writes the brief. Takes ~30-60s.
</span>

<h2>Brief</h2>
<div class="brief">{brief_html}</div>

<h2>Pain point mentions</h2>
<table>
  <thead><tr>
    <th>Pain point</th><th>Category</th><th>Mentions</th>
    <th>Unresolved</th><th>Engagement</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>

<h2>Past briefs</h2>
<ul>{hist_html or "<li class='muted'>None yet.</li>"}</ul>
"""
    return _page("Dev Community Pulse", body)


def topics_page(topics: list[dict]) -> str:
    rows = ""
    for t in topics:
        kws = ", ".join(t["keywords"])
        state = "<span class='pill'>active</span>" if t["active"] else "<span class='pill'>paused</span>"
        rows += f"""<tr>
  <td>{state}</td>
  <td>{t['category']}</td>
  <td class='muted'>{kws}</td>
  <td>
    <form class='inline' method='post' action='/topics/toggle/{t['id']}'>
      <button class='btn' type='submit'>Toggle</button>
    </form>
  </td>
</tr>"""
    body = f"""
<h1>Topics</h1>
<div class="sub">Edit categories + keywords. Changes apply on the next run — no deploy needed.</div>
{NAV}

<form method="post" action="/topics/add" style="margin: 8px 0 28px;">
  <input type="text" name="category" placeholder="Category (e.g. Code Review)" required />
  <input type="text" name="keywords" placeholder="keywords, comma separated"
         required style="width:360px" />
  <button class="btn" type="submit">Add topic</button>
</form>

<table>
  <thead><tr><th>Status</th><th>Category</th><th>Keywords</th><th></th></tr></thead>
  <tbody>{rows or "<tr><td colspan=4 class='muted'>No topics yet. Run the schema SQL in Supabase to seed defaults.</td></tr>"}</tbody>
</table>
"""
    return _page("Topics", body)
