"""Plain HTML views — no templating engine. Linear-style app shell.

Design tokens follow one scale: type 12/13/14/16/20/28px, spacing on a 4px grid.
"""
import re
from html import escape

BASE_CSS = """
<style>
  :root {
    color-scheme: dark;
    /* type scale */
    --fs-xs: 12px; --fs-sm: 13px; --fs-md: 14px; --fs-lg: 16px; --fs-xl: 20px; --fs-2xl: 28px;
    /* spacing scale (4px grid) */
    --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 20px; --s6: 24px; --s8: 32px; --s10: 40px; --s12: 48px;
    --radius: 8px; --radius-sm: 6px;
    /* colours */
    --bg: #08090a; --panel: #0f1011; --surface: #141517; --hover: #1c1d20;
    --border: #23252a; --border-soft: #1a1b1e;
    --text: #f7f8f8; --text-2: #b4b8bf; --text-3: #8a8f98; --text-4: #62666d;
    --accent: #5e6ad2; --accent-hover: #6e79d9; --accent-soft: rgba(94,106,210,.16);
    --green: #4cb782; --red: #eb5757; --amber: #f2c94c;
    --flash: rgba(94,106,210,.12);
  }
  @media (prefers-color-scheme: light) {
    :root {
      color-scheme: light;
      --bg: #ffffff; --panel: #f7f8f9; --surface: #ffffff; --hover: #f0f1f3;
      --border: #e3e4e8; --border-soft: #eeeff1;
      --text: #1b1c1f; --text-2: #3c3f45; --text-3: #6b6f76; --text-4: #9a9ea6;
      --accent-soft: rgba(94,106,210,.10); --flash: rgba(94,106,210,.08);
    }
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--text); }
  body {
    font: 400 var(--fs-md)/1.6 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    -webkit-font-smoothing: antialiased; font-feature-settings: 'cv11', 'ss01';
  }
  a { color: inherit; text-decoration: none; }
  code { background: var(--hover); padding: 1px 6px; border-radius: 4px; font-size: var(--fs-sm); }
  svg.i { width: 16px; height: 16px; flex: none; stroke: currentColor; fill: none;
          stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }

  /* ---------- shell ---------- */
  .app { display: flex; min-height: 100vh; }
  .side { width: 232px; flex: none; position: sticky; top: 0; height: 100vh; overflow-y: auto;
          background: var(--panel); border-right: 1px solid var(--border-soft);
          display: flex; flex-direction: column; padding: var(--s3) var(--s2); font-size: var(--fs-sm); }
  .brand { display: flex; align-items: center; gap: var(--s2); padding: var(--s1) var(--s2) var(--s4); font-weight: 600; }
  .logo { width: 22px; height: 22px; border-radius: 6px; display: grid; place-items: center; color: #fff;
          background: linear-gradient(135deg, #5e6ad2, #8b5cf6); font-size: 11px; font-weight: 700; }
  .nav-h { color: var(--text-4); font-size: var(--fs-xs); font-weight: 500; padding: var(--s4) var(--s2) var(--s1); }
  .nav a { display: flex; align-items: center; gap: var(--s2); padding: 6px var(--s2); border-radius: var(--radius-sm);
           color: var(--text-3); font-weight: 500; }
  .nav a:hover { background: var(--hover); color: var(--text); }
  .nav a.on { background: var(--hover); color: var(--text); }
  .nav a small { margin-left: auto; color: var(--text-4); font-weight: 400; }
  .side-foot { margin-top: auto; padding: var(--s3) var(--s2) var(--s1); color: var(--text-4); font-size: var(--fs-xs); line-height: 1.5; }

  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .bar { position: sticky; top: 0; z-index: 5; height: 48px; display: flex; align-items: center; gap: var(--s3);
         padding: 0 var(--s6); background: color-mix(in srgb, var(--bg) 85%, transparent);
         backdrop-filter: blur(8px); border-bottom: 1px solid var(--border-soft); }
  .crumbs { display: flex; align-items: center; gap: var(--s2); font-size: var(--fs-sm); color: var(--text-3); min-width: 0; white-space: nowrap; }
  .crumbs b { color: var(--text); font-weight: 500; overflow: hidden; text-overflow: ellipsis; }
  .crumbs a:hover { color: var(--text); }
  .bar .right { margin-left: auto; display: flex; align-items: center; gap: var(--s2); }
  .m-nav { display: none; }

  .content { width: 100%; max-width: 1180px; margin: 0 auto; padding: var(--s10) var(--s8) var(--s12);
             display: grid; grid-template-columns: minmax(0, 1fr) 200px; gap: var(--s10); }
  .content.narrow { grid-template-columns: minmax(0, 1fr); max-width: 880px; }
  .rail { position: sticky; top: 80px; align-self: start; font-size: var(--fs-sm); }
  .rail h4 { margin: 0 0 var(--s2); font-size: var(--fs-xs); font-weight: 500; color: var(--text-4); }
  .rail a { display: block; padding: 4px 0 4px var(--s3); color: var(--text-3); border-left: 1px solid var(--border); }
  .rail a:hover { color: var(--text); border-left-color: var(--accent); }

  /* ---------- page header ---------- */
  .eyebrow { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-xs); color: var(--text-3);
             font-weight: 500; margin-bottom: var(--s2); }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); }
  h1 { font-size: var(--fs-2xl); line-height: 1.25; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 var(--s2); }
  .lede { color: var(--text-3); font-size: var(--fs-lg); margin: 0 0 var(--s8); max-width: 640px; }
  h2.sec { display: flex; align-items: center; gap: var(--s2); font-size: var(--fs-lg); font-weight: 600;
           letter-spacing: -0.01em; margin: var(--s10) 0 var(--s3); scroll-margin-top: 64px; }
  h2.sec small { font-size: var(--fs-sm); font-weight: 400; color: var(--text-4); }

  /* ---------- stats ---------- */
  .stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--s3); }
  .stat { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: var(--s4); min-width: 0; }
  .stat span { display: block; font-size: var(--fs-xs); color: var(--text-3); font-weight: 500; }
  .stat b { display: block; font-size: var(--fs-xl); font-weight: 600; margin-top: var(--s1);
            font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
  .stat em { display: block; font-style: normal; font-size: var(--fs-xs); color: var(--text-4); margin-top: 2px;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* ---------- brief cards ---------- */
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
          margin-bottom: var(--s3); scroll-margin-top: 64px; }
  .card-h { display: flex; align-items: center; gap: var(--s2); padding: var(--s3) var(--s5);
            border-bottom: 1px solid var(--border-soft); font-size: var(--fs-md); font-weight: 600; }
  .card-h .ic { width: 24px; height: 24px; border-radius: 6px; display: grid; place-items: center;
                background: var(--accent-soft); color: var(--accent); }
  .card-h .ic.red { background: rgba(235,87,87,.14); color: var(--red); }
  .card-h .ic.green { background: rgba(76,183,130,.14); color: var(--green); }
  .card-h .ic.amber { background: rgba(242,201,76,.16); color: #d4a72c; }
  .card-b { padding: var(--s4) var(--s5) var(--s5); color: var(--text-2); max-width: 76ch; }
  .card-b > :first-child { margin-top: 0; } .card-b > :last-child { margin-bottom: 0; }
  .card-b p { margin: var(--s2) 0; }
  .card-b ul, .card-b ol { margin: var(--s2) 0; padding-left: var(--s5); }
  .card-b li { margin: var(--s2) 0; padding-left: var(--s1); }
  .card-b li::marker { color: var(--text-4); }
  .card-b strong { color: var(--text); font-weight: 600; }
  .card-b a { color: var(--accent-hover); border-bottom: 1px solid var(--accent-soft); }
  .card-b a:hover { border-bottom-color: var(--accent); }
  .card-b h3 { font-size: var(--fs-md); color: var(--text); margin: var(--s4) 0 var(--s1); }

  /* sprint checklist */
  .todo ol, .todo ul { list-style: none; padding: 0; }
  .todo li { position: relative; padding: var(--s2) var(--s3) var(--s2) 40px; margin: 0 calc(-1 * var(--s3));
             border-radius: var(--radius-sm); cursor: pointer; }
  .todo li:hover { background: var(--hover); }
  .todo li::before { content: ""; position: absolute; left: var(--s3); top: 13px; width: 16px; height: 16px; border-radius: 50%;
                     border: 1.5px solid var(--text-4); }
  .todo li.done { color: var(--text-4); text-decoration: line-through; }
  .todo li.done::before { background: var(--accent) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M4.5 8.2l2.3 2.3 4.7-4.9' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center/12px no-repeat;
                          border-color: var(--accent); }

  /* ---------- table ---------- */
  .tools { display: flex; flex-wrap: wrap; gap: var(--s2); align-items: center; margin-bottom: var(--s3); }
  .chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--border); background: transparent;
          color: var(--text-3); font: inherit; font-size: var(--fs-xs); font-weight: 500; padding: 4px 10px;
          border-radius: 999px; cursor: pointer; }
  .chip:hover { color: var(--text); background: var(--hover); }
  .chip.on { background: var(--accent-soft); border-color: transparent; color: var(--text); }
  .chip.dotted::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--c); }
  .search { margin-left: auto; display: flex; align-items: center; gap: 6px; color: var(--text-4);
            border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 0 var(--s2); background: var(--surface); }
  .search input { border: 0; background: transparent; padding: 6px 0; width: 200px; color: var(--text); font: inherit; font-size: var(--fs-sm); outline: none; }
  .tbl { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
  th { text-align: left; font-weight: 500; color: var(--text-3); font-size: var(--fs-xs); padding: var(--s2) var(--s4);
       border-bottom: 1px solid var(--border); white-space: nowrap; user-select: none; }
  th[data-sort] { cursor: pointer; } th[data-sort]:hover { color: var(--text); }
  th[aria-sort=ascending]::after { content: " ↑"; } th[aria-sort=descending]::after { content: " ↓"; }
  td { padding: 10px var(--s4); border-bottom: 1px solid var(--border-soft); vertical-align: middle; }
  tbody tr:last-child td { border-bottom: 0; }
  tbody tr:hover td { background: var(--hover); }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  td.pp { color: var(--text); font-weight: 500; min-width: 240px; }
  td.pp::first-letter { text-transform: uppercase; }
  .meter { display: flex; align-items: center; gap: var(--s2); justify-content: flex-end; }
  .meter i { display: block; width: 56px; height: 4px; border-radius: 2px; background: var(--border); overflow: hidden; }
  .meter i u { display: block; height: 100%; background: var(--accent); }
  .zero { color: var(--text-4); }
  .warn { color: var(--amber); }
  .tfoot { padding: var(--s2) var(--s4); font-size: var(--fs-xs); color: var(--text-4); border-top: 1px solid var(--border-soft); }
  .empty { padding: var(--s8) var(--s4); text-align: center; color: var(--text-3); }

  /* pills: category colours */
  .pill { display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 999px;
          border: 1px solid var(--border); font-size: var(--fs-xs); color: var(--text-2); white-space: nowrap; }
  .pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--c, var(--text-4)); }
  .c0 { --c: #5e6ad2; } .c1 { --c: #4cb782; } .c2 { --c: #f2994a; } .c3 { --c: #eb5757; }
  .c4 { --c: #bb87fc; } .c5 { --c: #26b5ce; } .c6 { --c: #f2c94c; }

  /* ---------- buttons & forms ---------- */
  .btn { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 var(--s3); border-radius: var(--radius-sm);
         border: 1px solid var(--border); background: var(--surface); color: var(--text); font: inherit;
         font-size: var(--fs-sm); font-weight: 500; cursor: pointer; white-space: nowrap; }
  .btn:hover { background: var(--hover); }
  .btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
  .btn-primary:hover { background: var(--accent-hover); }
  .btn[disabled] { opacity: .65; cursor: progress; }
  form.inline { display: inline; margin: 0; }
  .field { display: flex; flex-direction: column; gap: 6px; min-width: 200px; }
  .field label { font-size: var(--fs-xs); color: var(--text-3); font-weight: 500; }
  .field input { background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius-sm);
                 padding: 7px 10px; font: inherit; font-size: var(--fs-sm); }
  .field input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  .form-row { display: flex; flex-wrap: wrap; gap: var(--s3); align-items: flex-end; padding: var(--s4) var(--s5) var(--s5); }
  .kw { display: inline-block; padding: 1px 8px; margin: 2px 4px 2px 0; border-radius: 4px; background: var(--hover);
        color: var(--text-2); font-size: var(--fs-xs); }
  .status { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-xs); color: var(--text-3); white-space: nowrap; }
  .status::before { content: ""; width: 8px; height: 8px; border-radius: 50%; border: 1.5px solid var(--text-4); }
  .status.on { color: var(--text-2); } .status.on::before { background: var(--green); border-color: var(--green); }

  .flash { display: flex; gap: var(--s2); align-items: center; background: var(--flash); border: 1px solid var(--accent-soft);
           padding: var(--s3) var(--s4); border-radius: var(--radius); margin-bottom: var(--s6); font-size: var(--fs-sm); }
  .muted { color: var(--text-3); }
  .hint { font-size: var(--fs-xs); color: var(--text-4); margin-top: var(--s3); }

  /* ---------- responsive ---------- */
  @media (max-width: 1180px) { .content { grid-template-columns: minmax(0, 1fr); max-width: 880px; } .rail { display: none; } }
  @media (max-width: 860px) {
    .side { display: none; }
    .m-nav { display: flex; gap: var(--s1); overflow-x: auto; padding: var(--s2) var(--s4); border-bottom: 1px solid var(--border-soft);
             font-size: var(--fs-sm); background: var(--panel); }
    .m-nav a { padding: 4px 10px; border-radius: var(--radius-sm); color: var(--text-3); white-space: nowrap; }
    .m-nav a.on { background: var(--hover); color: var(--text); }
    .bar { padding: 0 var(--s4); }
    .content { padding: var(--s6) var(--s4) var(--s10); }
    .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .search { margin-left: 0; width: 100%; } .search input { width: 100%; }
    .card-b, .card-h { padding-left: var(--s4); padding-right: var(--s4); }
    .hide-sm { display: none; }
  }
</style>
"""

# Line icons drawn on a 16px grid.
_ICONS = {
    "doc": '<path d="M4 2.5h5.5L12 5v8.5H4z"/><path d="M9.5 2.5V5H12M6 8h4M6 10.5h4"/>',
    "tag": '<path d="M2.5 8.6V3h5.6l5.4 5.4-5.6 5.6z"/><circle cx="5.5" cy="6" r=".8"/>',
    "pulse": '<path d="M1.5 8h3l2-4.5 3 9 2-4.5h3"/>',
    "play": '<path d="M5 3.5v9l7-4.5z"/>',
    "flame": '<path d="M8 14c2.5 0 4-1.7 4-4 0-3-3-4.5-3-7.5C6.5 4 5.5 6 6 8 5 7.5 4.5 6.5 4.5 6 4 7 4 8.5 4 10c0 2.3 1.5 4 4 4z"/>',
    "trend": '<path d="M1.5 11.5l4-4 3 3 6-6"/><path d="M10.5 4.5h4v4"/>',
    "target": '<circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="3"/><circle cx="8" cy="8" r=".5"/>',
    "shield": '<path d="M8 1.5l5.5 2v4c0 3.3-2.3 5.8-5.5 7-3.2-1.2-5.5-3.7-5.5-7v-4z"/>',
    "check": '<circle cx="8" cy="8" r="6.5"/><path d="M5.3 8.2l1.9 1.9 3.6-3.8"/>',
    "zap": '<path d="M9 1.5L3 9h5l-1 5.5L13 7H8z"/>',
    "search": '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/>',
    "clock": '<circle cx="8" cy="8" r="6.5"/><path d="M8 4.5V8l2.5 1.5"/>',
}


def _icon(name: str) -> str:
    return f'<svg class="i" viewBox="0 0 16 16" aria-hidden="true">{_ICONS[name]}</svg>'


# Brief section heading keyword -> (icon, colour, short label for the outline)
_SECTION_STYLE = [
    ("tl;dr", ("zap", "", "Summary")),
    ("summary", ("zap", "", "Summary")),
    ("overview", ("zap", "", "Overview")),
    ("pain point", ("flame", "red", "Top pain points")),
    ("trend", ("trend", "", "Trending")),
    ("unsolved", ("target", "green", "Opportunities")),
    ("unresolved", ("target", "green", "Opportunities")),
    ("opportunit", ("target", "green", "Opportunities")),
    ("objection", ("shield", "amber", "Sales objections")),
    ("action", ("check", "", "Sprint actions")),
]


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _section_style(title: str) -> tuple[str, str, str]:
    low = title.lower()
    for key, style in _SECTION_STYLE:
        if key in low:
            return style
    return "doc", "", _strip_tags(title)


def _cat_class(category: str) -> str:
    return f"c{sum(map(ord, category or '')) % 7}"


def _split_brief(brief_html: str) -> list[dict]:
    """Turn the rendered markdown into one card per <h2> section."""
    parts = re.split(r"<h2[^>]*>(.*?)</h2>", brief_html, flags=re.S)
    intro = re.sub(r"<h1[^>]*>.*?</h1>", "", parts[0], flags=re.S).strip()
    sections = []
    if intro:
        sections.append({"title": "Overview", "body": intro})
    for i in range(1, len(parts), 2):
        sections.append({"title": parts[i].strip(), "body": parts[i + 1].strip()})
    return sections


def _nav_link(href: str, icon: str, label: str, active: bool) -> str:
    return f'<a href="{href}" class="{"on" if active else ""}">{_icon(icon)}{label}</a>'


def _page(title: str, body: str, *, active: str = "", crumbs: str = "", actions: str = "",
          history: list[dict] | None = None, current_week: str | None = None, script: str = "") -> str:
    hist_links = "".join(
        f'<a href="/history/{escape(h["week_start"])}" class="{"on" if h["week_start"] == current_week else ""}">'
        f'{_icon("clock")}{escape(h["week_start"])}{"<small>Latest</small>" if i == 0 else ""}</a>'
        for i, h in enumerate(history or [])
    )
    hist_block = f'<div class="nav-h">Past briefs</div><nav class="nav">{hist_links}</nav>' if hist_links else ""
    nav = (_nav_link("/", "doc", "Latest brief", active == "brief")
           + _nav_link("/topics", "tag", "Topics", active == "topics")
           + _nav_link("/health", "pulse", "Health", active == "health"))
    m_nav = (f'<a href="/" class="{"on" if active == "brief" else ""}">Latest brief</a>'
             f'<a href="/topics" class="{"on" if active == "topics" else ""}">Topics</a>'
             f'<a href="/health" class="{"on" if active == "health" else ""}">Health</a>')
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
{BASE_CSS}
</head><body>
<div class="app">
  <aside class="side">
    <div class="brand"><span class="logo">DP</span>Dev Community Pulse</div>
    <nav class="nav">{nav}</nav>
    {hist_block}
    <div class="side-foot">New brief every Friday, 8:30 AM IST.<br>Sources: Hacker News, Stack Overflow, GitHub.</div>
  </aside>
  <div class="main">
    <header class="bar">
      <div class="crumbs">{crumbs}</div>
      <div class="right">{actions}</div>
    </header>
    <nav class="m-nav">{m_nav}</nav>
    {body}
  </div>
</div>
<script>
document.querySelectorAll('form[data-busy]').forEach(f => f.addEventListener('submit', () => {{
  const b = f.querySelector('button'); b.disabled = true; b.lastChild.textContent = f.dataset.busy;
}}));
</script>
{script}
</body></html>"""


RUN_BUTTON = (
    '<form class="inline" method="post" action="/run-now" data-busy=" Running… about a minute">'
    '<button class="btn btn-primary" type="submit" title="Fetches the last 7 days, tags posts with Gemini and writes a new brief">'
    f'{_icon("play")}<span> Run now</span></button></form>'
)


def not_configured(missing: list[str]) -> str:
    items = "".join(f"<li><code>{escape(m)}</code></li>" for m in missing)
    body = f"""
<main class="content narrow">
  <div>
    <div class="eyebrow"><span class="dot" style="background:var(--amber)"></span>Setup needed</div>
    <h1>Almost there</h1>
    <p class="lede">The server is missing some settings. Add them in Vercel, then redeploy
    (environment changes only take effect after a redeploy).</p>
    <section class="card">
      <div class="card-h"><span class="ic amber">{_icon("tag")}</span>Missing environment variables</div>
      <div class="card-b"><ul>{items}</ul>
        <p class="muted">After redeploying, open the <a href="/health">Health</a> page to confirm,
        then come back here and click <b>Run now</b>.</p></div>
    </section>
  </div>
</main>"""
    return _page("Setup needed · Dev Community Pulse", body,
                 crumbs="<b>Dev Community Pulse</b>")


def dashboard(brief_html: str, metrics_rows: list[dict], history: list[dict],
              week_start: str | None, flash: str | None = None) -> str:
    latest_week = history[0]["week_start"] if history else None
    is_latest = week_start is None or week_start == latest_week

    # ---- headline numbers ----
    total = sum(m["mention_count"] for m in metrics_rows)
    unresolved = sum(m.get("unresolved_count") or 0 for m in metrics_rows)
    engagement = sum(m.get("engagement") or 0 for m in metrics_rows)
    top = metrics_rows[0]["pain_point"] if metrics_rows else "—"
    stats = f"""
<div class="stats">
  <div class="stat"><span>Pain points</span><b>{len(metrics_rows)}</b><em>tracked this week</em></div>
  <div class="stat"><span>Mentions</span><b>{total}</b><em title="{escape(top)}">Top: {escape(top)}</em></div>
  <div class="stat"><span>Unresolved</span><b>{unresolved}</b><em>{round(unresolved * 100 / total) if total else 0}% of mentions</em></div>
  <div class="stat"><span>Engagement</span><b>{engagement:,}</b><em>votes + comments</em></div>
</div>"""

    # ---- brief as cards ----
    cards, outline, used = "", "", set()
    for s in _split_brief(brief_html):
        icon, colour, short = _section_style(s["title"])
        sid = re.sub(r"[^a-z0-9]+", "-", short.lower()).strip("-") or "section"
        while sid in used:
            sid += "-2"
        used.add(sid)
        extra = " todo" if icon == "check" else ""
        cards += (f'<section class="card" id="{sid}"><div class="card-h"><span class="ic {colour}">{_icon(icon)}</span>'
                  f'{s["title"]}</div><div class="card-b{extra}">{s["body"]}</div></section>')
        outline += f'<a href="#{sid}">{escape(short)}</a>'
    if not cards:
        cards = '<section class="card"><div class="empty">No brief yet. Click <b>Run now</b> to generate the first one.</div></section>'

    # ---- pain point table ----
    max_m = max((m["mention_count"] for m in metrics_rows), default=0) or 1
    categories = sorted({m.get("category") or "Other" for m in metrics_rows})
    rows_html = ""
    for m in metrics_rows:
        cat = m.get("category") or "Other"
        n, u, e = m["mention_count"], m.get("unresolved_count") or 0, m.get("engagement") or 0
        rows_html += (
            f'<tr data-cat="{escape(cat)}">'
            f'<td class="pp">{escape(m["pain_point"])}</td>'
            f'<td><span class="pill {_cat_class(cat)}">{escape(cat)}</span></td>'
            f'<td class="n" data-v="{n}"><span class="meter">{n}<i><u style="width:{n * 100 / max_m:.0f}%"></u></i></span></td>'
            f'<td class="n {"warn" if u else "zero"}" data-v="{u}">{u}</td>'
            f'<td class="n {"" if e else "zero"}" data-v="{e}">{e:,}</td></tr>'
        )
    chips = '<button class="chip on" data-cat="">All</button>' + "".join(
        f'<button class="chip dotted {_cat_class(c)}" data-cat="{escape(c)}">{escape(c)}</button>'
        for c in categories
    )
    if rows_html:
        table = f"""
<div class="tools">{chips}
  <label class="search">{_icon("search")}<input id="q" type="search" placeholder="Filter pain points…" aria-label="Filter pain points"></label>
</div>
<div class="tbl"><table id="pp">
  <thead><tr><th data-sort="text">Pain point</th><th data-sort="text">Category</th>
    <th class="n" data-sort="num" aria-sort="descending">Mentions</th><th class="n" data-sort="num">Unresolved</th>
    <th class="n" data-sort="num">Engagement</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table><div class="tfoot" id="count">{len(metrics_rows)} pain points</div></div>"""
    else:
        table = '<div class="tbl"><div class="empty">No metrics yet. Click <b>Run now</b> to generate the first brief.</div></div>'

    flash_html = f'<div class="flash">{escape(flash)}</div>' if flash else ""
    title = f"Week of {week_start}" if week_start else "No brief yet"
    eyebrow = ('<span class="dot"></span>Latest brief' if is_latest
               else '<span class="dot" style="background:var(--text-4)"></span>Past brief')
    body = f"""
<main class="content">
  <div>
    {flash_html}
    <div class="eyebrow">{eyebrow}</div>
    <h1>{escape(title)}</h1>
    <p class="lede">Pain points, trends and product gaps developers raised on Hacker News, Stack Overflow and GitHub.</p>
    {stats}
    <h2 class="sec" id="brief">Brief</h2>
    {cards}
    <h2 class="sec" id="numbers">All pain points <small>{len(metrics_rows)}</small></h2>
    {table}
  </div>
  <aside class="rail"><h4>On this page</h4>{outline}<a href="#numbers">All pain points</a></aside>
</main>"""
    crumbs = f'<a href="/">Briefs</a><span>/</span><b>{escape(title)}</b>'
    return _page(f"{title} · Dev Community Pulse", body, active="brief" if is_latest else "",
                 crumbs=crumbs, actions=RUN_BUTTON, history=history, current_week=week_start,
                 script=_dashboard_js(week_start or ""))


def _dashboard_js(week: str) -> str:
    return """<script>
(() => {
  // sprint checklist, remembered per week in this browser
  const key = 'pulse-todo-""" + re.sub(r"[^0-9-]", "", week) + """';
  let done = {}; try { done = JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) {}
  document.querySelectorAll('.todo li').forEach((li, i) => {
    li.classList.toggle('done', !!done[i]);
    li.addEventListener('click', e => {
      if (e.target.closest('a')) return;
      done[i] = li.classList.toggle('done');
      try { localStorage.setItem(key, JSON.stringify(done)); } catch (e) {}
    });
  });

  // table: filter by category + text, sort by column
  const table = document.getElementById('pp'); if (!table) return;
  const rows = [...table.tBodies[0].rows], q = document.getElementById('q'), count = document.getElementById('count');
  let cat = '';
  const apply = () => {
    const term = q.value.trim().toLowerCase(); let shown = 0;
    rows.forEach(r => {
      const ok = (!cat || r.dataset.cat === cat) && (!term || r.innerText.toLowerCase().includes(term));
      r.hidden = !ok; shown += ok;
    });
    count.textContent = shown === rows.length ? rows.length + ' pain points' : shown + ' of ' + rows.length + ' pain points';
  };
  q.addEventListener('input', apply);
  document.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => {
    document.querySelectorAll('.chip').forEach(x => x.classList.toggle('on', x === c));
    cat = c.dataset.cat; apply();
  }));
  table.querySelectorAll('th[data-sort]').forEach((th, col) => th.addEventListener('click', () => {
    const asc = th.getAttribute('aria-sort') === 'descending';
    table.querySelectorAll('th').forEach(x => x.removeAttribute('aria-sort'));
    th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
    const val = r => th.dataset.sort === 'num' ? +r.cells[col].dataset.v : r.cells[col].innerText.toLowerCase();
    rows.sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * (asc ? 1 : -1));
    rows.forEach(r => table.tBodies[0].appendChild(r));
  }));
})();
</script>"""


def topics_page(topics: list[dict]) -> str:
    rows = ""
    for t in topics:
        kws = "".join(f'<span class="kw">{escape(k)}</span>' for k in t["keywords"])
        on = t["active"]
        rows += f"""<tr>
  <td><span class="status {'on' if on else ''}">{'Active' if on else 'Paused'}</span></td>
  <td><span class="pill {_cat_class(t['category'])}">{escape(t['category'])}</span></td>
  <td style="min-width:220px">{kws}</td>
  <td class="n">
    <form class="inline" method="post" action="/topics/toggle/{int(t['id'])}">
      <button class="btn" type="submit">{'Pause' if on else 'Resume'}</button>
    </form>
  </td>
</tr>"""
    active = sum(1 for t in topics if t["active"])
    table = (f"""<div class="tbl"><table>
  <thead><tr><th>Status</th><th>Category</th><th>Keywords</th><th></th></tr></thead>
  <tbody>{rows}</tbody></table>
  <div class="tfoot">{active} of {len(topics)} topics active</div></div>"""
             if rows else
             '<div class="tbl"><div class="empty">No topics yet. Add one above, or run the schema SQL in Supabase to seed defaults.</div></div>')
    body = f"""
<main class="content narrow">
  <div>
    <h1>Topics</h1>
    <p class="lede">The categories and keywords searched on every run. Changes apply on the next run, no deploy needed.</p>
    <section class="card">
      <div class="card-h"><span class="ic">{_icon("tag")}</span>Add a topic</div>
      <form method="post" action="/topics/add" class="form-row">
        <div class="field" style="flex:1 1 200px"><label for="cat">Category</label>
          <input id="cat" type="text" name="category" placeholder="e.g. Code Review" required></div>
        <div class="field" style="flex:2 1 300px"><label for="kw">Keywords, comma separated</label>
          <input id="kw" type="text" name="keywords" placeholder="code review, pull request, review bot" required></div>
        <button class="btn btn-primary" type="submit">Add topic</button>
      </form>
    </section>
    <h2 class="sec">All topics <small>{len(topics)}</small></h2>
    {table}
    <p class="hint">Paused topics are skipped when collecting posts; their history is kept.</p>
  </div>
</main>"""
    return _page("Topics · Dev Community Pulse", body, active="topics",
                 crumbs='<a href="/">Dev Community Pulse</a><span>/</span><b>Topics</b>',
                 actions=RUN_BUTTON)


def health_page(groups: list[tuple[str, list[dict]]]) -> str:
    """groups: [(title, [{"label", "ok": True|False|None, "detail"}])]; None = optional and not set."""
    failing = sum(1 for _, checks in groups for c in checks if c["ok"] is False)
    cards = ""
    for title, checks in groups:
        rows = "".join(
            f'<tr><td><span class="status {"on" if c["ok"] else ""}" '
            f'style="{"" if c["ok"] is not False else "color:var(--red)"}">'
            f'{"OK" if c["ok"] else "Failing" if c["ok"] is False else "Not set"}</span></td>'
            f'<td style="color:var(--text);font-weight:500">{escape(c["label"])}</td>'
            f'<td class="muted">{escape(c["detail"])}</td></tr>'
            for c in checks
        )
        cards += f'<h2 class="sec">{escape(title)}</h2><div class="tbl"><table style="table-layout:fixed"><colgroup><col style="width:120px"><col style="width:34%"><col></colgroup><tbody>{rows}</tbody></table></div>'
    dot, headline = (("var(--green)", "All systems working") if not failing
                     else ("var(--red)", f"{failing} check{'s' if failing > 1 else ''} failing"))
    body = f"""
<main class="content narrow">
  <div>
    <div class="eyebrow"><span class="dot" style="background:{dot}"></span>{headline}</div>
    <h1>Health</h1>
    <p class="lede">Whether the settings, database and weekly schedule are working. Secret values are never shown.</p>
    {cards}
    <p class="hint">For monitoring tools, the same status is available as JSON at <a href="/api/health" style="text-decoration:underline">/api/health</a>.</p>
  </div>
</main>"""
    return _page("Health · Dev Community Pulse", body, active="health",
                 crumbs='<a href="/">Dev Community Pulse</a><span>/</span><b>Health</b>',
                 actions=RUN_BUTTON)
