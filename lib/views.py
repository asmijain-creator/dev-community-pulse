"""Plain HTML views — no templating engine. Linear-style app shell.

Design tokens follow one scale: type 12/13/14/16/20/28px, spacing on a 4px grid.
"""
import re
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import quote

IST = timezone(timedelta(hours=5, minutes=30))

BASE_CSS = """
<style>
  :root {
    color-scheme: light;
    /* type scale */
    --fs-xs: 12px; --fs-sm: 13px; --fs-md: 14px; --fs-lg: 16px; --fs-xl: 20px; --fs-2xl: 28px;
    /* spacing scale (4px grid) */
    --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 20px; --s6: 24px; --s8: 32px; --s10: 40px; --s12: 48px;
    --radius: 10px; --radius-sm: 8px;
    /* colours: neutral surfaces, mint for "good / action", red for "problem" */
    --bg: #ffffff; --panel: #f8f9fb; --surface: #ffffff; --hover: #f3f5f8;
    --border: #e7e9ee; --border-soft: #f0f1f4;
    --text: #2f3242; --text-2: #4b4f63; --text-3: #6f7285; --text-4: #9a9cab;
    --accent: #00a67e; --accent-strong: #007a5c; --accent-soft: rgba(0,166,126,.12);
    --btn-bg: #007a5c; --btn-hover: #006b50; --btn-fg: #ffffff;
    --link: #007a5c; --bar: #00a67e; --bar-muted: #9fdcc9;
    --green: #00a67e; --red: #eb5b3c; --amber: #f5a623; --warn-text: #b86e00;
    --flash: rgba(0,166,126,.08);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      color-scheme: dark;
      --bg: #121314; --panel: #17191b; --surface: #1c1e21; --hover: #24272b;
      --border: #2c2f34; --border-soft: #222528;
      --text: #f2f3f5; --text-2: #c5c7ce; --text-3: #9a9ca6; --text-4: #6f727b;
      --accent: #00d09c; --accent-strong: #00d09c; --accent-soft: rgba(0,208,156,.14);
      --btn-bg: #00d09c; --btn-hover: #1fdcae; --btn-fg: #06261d;
      --link: #3fdcb2; --bar: #00d09c; --bar-muted: #1f6b57;
      --green: #00d09c; --red: #f0735a; --amber: #f5b13d; --warn-text: #f5b13d;
      --flash: rgba(0,208,156,.10);
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
          background: var(--accent); font-size: 11px; font-weight: 700; }
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
  .card-b a { color: var(--link); border-bottom: 1px solid var(--accent-soft); }
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
  .todo li.done::before { background: var(--btn-bg) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M4.5 8.2l2.3 2.3 4.7-4.9' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center/12px no-repeat;
                          border-color: var(--btn-bg); }

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
  .meter i u { display: block; height: 100%; background: var(--bar); }
  .zero { color: var(--text-4); }
  .warn { color: var(--warn-text); font-weight: 500; }
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
  .btn-primary { background: var(--btn-bg); border-color: var(--btn-bg); color: var(--btn-fg); font-weight: 600; }
  .btn-primary:hover { background: var(--btn-hover); }
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
  .flash.err { background: rgba(235,87,87,.1); border-color: rgba(235,87,87,.3); }
  .flash svg { color: var(--accent); } .flash.err svg { color: var(--red); }
  .muted { color: var(--text-3); }
  .hint { font-size: var(--fs-xs); color: var(--text-4); margin-top: var(--s3); }

  /* ---------- section tones ---------- */
  /* red = problems, amber = movement, green = opportunity, blue = to-do, ink = data, gray = parked */
  .tone-red { --tone: var(--red); } .tone-amber { --tone: var(--amber); } .tone-green { --tone: var(--green); }
  .tone-blue { --tone: #5367ff; } .tone-ink { --tone: var(--text-3); } .tone-gray { --tone: var(--text-4); }
  .ic.t { width: 24px; height: 24px; flex: none; border-radius: 6px; display: grid; place-items: center;
          background: color-mix(in srgb, var(--tone) 16%, transparent); color: var(--tone); }

  /* ---------- homepage summary cards ---------- */
  .sgrid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s3); margin-top: var(--s8); }
  .sgrid .wide { grid-column: 1 / -1; }
  .sum { display: block; background: var(--surface); border: 1px solid var(--border); border-top: 2px solid var(--tone);
         border-radius: var(--radius); padding: var(--s4) var(--s5); transition: border-color .15s, background .15s; }
  .sum:hover { background: var(--hover); border-color: color-mix(in srgb, var(--tone) 45%, var(--border)); border-top-color: var(--tone); }
  .sum-h { display: flex; align-items: center; gap: var(--s2); font-weight: 600; font-size: var(--fs-md);
           color: color-mix(in srgb, var(--tone) 70%, var(--text)); margin-bottom: var(--s3); }
  .sum-h small { color: var(--text-4); font-weight: 400; font-size: var(--fs-sm); }
  .sum-h .go { margin-left: auto; font-size: var(--fs-xs); font-weight: 500; color: var(--text-4); white-space: nowrap; }
  .sum:hover .go { color: var(--tone); }
  .sum-l { list-style: none; margin: 0; padding: 0; color: var(--text-2); font-size: var(--fs-sm); }
  .sum-l li { position: relative; padding: 3px 0 3px var(--s4); line-height: 1.5; }
  .sum-l li::before { content: ""; position: absolute; left: 2px; top: 11px; width: 5px; height: 5px; border-radius: 50%; background: var(--tone); opacity: .7; }
  .sum-l b { color: var(--text); font-weight: 600; }
  .sum-p { margin: 0; color: var(--text-2); font-size: var(--fs-sm); }
  .sum-f { margin-top: var(--s2); font-size: var(--fs-xs); color: var(--text-4); }
  table.mini { font-size: var(--fs-sm); }
  table.mini td { padding: 7px 0; border-bottom: 1px solid var(--border-soft); }
  table.mini td + td { padding-left: var(--s4); }
  table.mini tr:hover td { background: none; }
  table.mini td.pp { min-width: 0; }

  /* ---------- section pages ---------- */
  .back { display: inline-block; font-size: var(--fs-sm); color: var(--text-3); margin-bottom: var(--s4); }
  .back:hover { color: var(--text); }
  h1.sec-title { display: flex; align-items: center; gap: var(--s3); color: color-mix(in srgb, var(--tone) 70%, var(--text)); }
  h1.sec-title .ic.t { width: 32px; height: 32px; border-radius: 8px; }
  h1.sec-title .ic.t svg { width: 18px; height: 18px; }
  .card.accent { border-top: 2px solid var(--tone); margin-top: var(--s6); }
  .card.accent .card-b { padding-top: var(--s5); font-size: var(--fs-md); }
  .card-b li { margin: var(--s3) 0; }
  .pager { display: flex; justify-content: space-between; gap: var(--s3); margin-top: var(--s8); }
  .pn { flex: 1; max-width: 50%; border: 1px solid var(--border); border-radius: var(--radius); padding: var(--s3) var(--s4);
        font-size: var(--fs-sm); font-weight: 500; }
  .pn:hover { background: var(--hover); }
  .pn small { display: block; font-size: var(--fs-xs); font-weight: 400; color: var(--text-4); }
  .pn.r { text-align: right; margin-left: auto; }
  .rail a.on { color: var(--text); border-left-color: var(--tone); }
  .rail a:hover { border-left-color: var(--tone, var(--accent)); }

  /* ---------- pain point detail ---------- */
  tr[data-href] { cursor: pointer; }
  tr[data-href] td.pp a:hover { text-decoration: underline; }
  .chart { position: relative; }
  .chart-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: var(--s4) var(--s5); margin-top: var(--s6); position: relative; }
  .chart-card h3 { margin: 0; font-size: var(--fs-md); font-weight: 600; }
  .chart-card .sub { color: var(--text-3); font-size: var(--fs-xs); margin: 2px 0 var(--s3); }
  .chart svg { display: block; width: 100%; height: auto; overflow: visible; }
  .chart .grid { stroke: var(--border-soft); stroke-width: 1; }
  .chart .base { stroke: var(--border); stroke-width: 1; }
  .chart .ax { fill: var(--text-3); font-size: 11px; font-family: inherit; }
  .chart .val { fill: var(--text); font-size: 12px; font-weight: 600; font-family: inherit; }
  .chart .bar { fill: var(--bar-muted); } .chart .bar.cur { fill: var(--bar); }
  .chart .hit { fill: transparent; cursor: default; }
  .chart .hit:hover + .bar, .chart g:hover .bar { filter: brightness(.92); }
  .tip { position: absolute; pointer-events: none; background: var(--text); color: var(--bg); font-size: var(--fs-xs);
         padding: 6px 10px; border-radius: 6px; white-space: nowrap; transform: translate(-50%, -100%); margin-top: -8px; line-height: 1.45; }
  .tip[hidden] { display: none; }
  details.tv { margin-top: var(--s3); font-size: var(--fs-sm); }
  details.tv summary { cursor: pointer; color: var(--text-3); }
  details.tv table { margin-top: var(--s2); }
  .threads { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); }
  .thread { display: block; padding: var(--s3) var(--s5); border-bottom: 1px solid var(--border-soft); }
  .thread:last-child { border-bottom: 0; }
  .thread:hover { background: var(--hover); }
  .thread b { display: block; font-weight: 500; color: var(--text); margin: 4px 0 2px; }
  .thread .meta { display: flex; flex-wrap: wrap; gap: var(--s3); font-size: var(--fs-xs); color: var(--text-3); align-items: center; }
  .src { font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 4px; background: var(--hover); color: var(--text-2); }
  .src.hackernews, .src.hn { color: #c2410c; } .src.stackoverflow, .src.so { color: #b45309; } .src.github, .src.gh { color: var(--text); }
  .st-open { color: var(--warn-text); font-weight: 500; } .st-done { color: var(--green); font-weight: 500; }
  .stat em span { display: inline; font-size: inherit; font-weight: 600; color: var(--text-3); }
  .stat em span.up, .up { color: var(--red); } .stat em span.down, .down { color: var(--green); }

  /* ---------- run progress ---------- */
  .runbox { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: var(--s4);
            background: rgba(0,0,0,.55); backdrop-filter: blur(3px); }
  .runbox[hidden] { display: none; }
  .run-card { width: min(480px, 100%); background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
              padding: var(--s5) var(--s6); box-shadow: 0 24px 64px rgba(0,0,0,.45); }
  .run-h { display: flex; align-items: center; gap: var(--s3); font-size: var(--fs-lg); }
  .run-h b { font-weight: 600; }
  .run-time { margin-left: auto; font-variant-numeric: tabular-nums; color: var(--text-3); font-size: var(--fs-sm); }
  .run-note { color: var(--text-3); font-size: var(--fs-sm); margin: var(--s2) 0 var(--s4); }
  .spin { width: 16px; height: 16px; flex: none; border-radius: 50%; border: 2px solid var(--accent-soft); border-top-color: var(--accent);
          animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .steps { list-style: none; padding: 0; margin: 0 0 var(--s4); }
  .steps li { position: relative; padding: 7px 0 7px 30px; color: var(--text-4); font-size: var(--fs-sm); transition: color .2s; }
  .steps li::before { content: ""; position: absolute; left: 2px; top: 9px; width: 16px; height: 16px; border-radius: 50%;
                      border: 1.5px solid var(--border); box-sizing: border-box; }
  .steps li.active { color: var(--text); font-weight: 500; }
  .steps li.active::before { border: 2px solid var(--accent-soft); border-top-color: var(--accent); animation: spin .8s linear infinite; }
  .steps li.done { color: var(--text-3); }
  .steps li.done::before { border-color: var(--green); background: var(--green) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M4.5 8.2l2.3 2.3 4.7-4.9' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center/11px no-repeat; }
  .run-bar { height: 4px; border-radius: 2px; background: var(--border); overflow: hidden; }
  .run-bar u { display: block; height: 100%; width: 0; background: var(--bar); transition: width .5s linear; }
  @media (max-width: 860px) { .sgrid { grid-template-columns: minmax(0, 1fr); } .pn small { display: none; } }

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


# Brief sections in homepage order: (key, label, icon, tone). Matching keywords are in _MATCH.
SECTIONS = [
    ("overview", "Overview", "zap", "gray"),
    ("top-pain-points", "Top pain points", "flame", "red"),
    ("trending", "Trending", "trend", "amber"),
    ("opportunities", "Opportunities", "target", "green"),
    ("out-of-scope", "Out of scope", "shield", "gray"),
    ("sprint-actions", "Sprint actions", "check", "blue"),
]
_SECTION = {s[0]: s for s in SECTIONS}
SECTION_INTRO = {
    "overview": "The week at a glance.",
    "top-pain-points": "The problems developers mentioned most this week, with links to the original threads.",
    "trending": "What moved compared with last week. A topic only counts as a trend once it reaches 3 mentions.",
    "opportunities": "Problems that are still unsolved. These are the gaps worth building for.",
    "out-of-scope": "Complaints and doubts outside what we're building right now. Kept for context, not for action.",
    "sprint-actions": "Concrete next steps for Monday's sprint planning, each tied to a pain point.",
}
# Checked in this order, so "Unresolved pain points" lands in Opportunities, not Top pain points.
_MATCH = [
    ("out-of-scope", ("scope", "concern", "objection")),
    ("sprint-actions", ("action",)),
    ("trending", ("trend",)),
    ("opportunities", ("unsolved", "unresolved", "opportunit", "gap")),
    ("top-pain-points", ("pain point",)),
    ("overview", ("tl;dr", "summary", "overview")),
]


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _cat_class(category: str) -> str:
    return f"c{sum(map(ord, category or '')) % 7}"


def parse_brief(brief_html: str) -> list[dict]:
    """Split the rendered markdown at each <h2> into sections, in homepage order."""
    parts = re.split(r"<h2[^>]*>(.*?)</h2>", brief_html, flags=re.S)
    raw = []
    intro = re.sub(r"<h1[^>]*>.*?</h1>", "", parts[0], flags=re.S).strip()
    if _strip_tags(intro).strip():
        raw.append(("Overview", intro))
    raw += [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts), 2)]

    known, extra = {}, []
    for title, body in raw:
        low = _strip_tags(title).lower()
        key = next((k for k, words in _MATCH if any(w in low for w in words)), None)
        if key and key not in known:
            _, label, icon, tone = _SECTION[key]
            known[key] = {"key": key, "label": label, "icon": icon, "tone": tone, "body": body}
        else:
            slug = re.sub(r"[^a-z0-9]+", "-", low).strip("-") or "section"
            while slug in known or slug in [e["key"] for e in extra] or slug == "pain-points":
                slug += "-2"
            extra.append({"key": slug, "label": _strip_tags(title), "icon": "doc", "tone": "gray", "body": body})
    return [known[k] for k, *_ in SECTIONS if k in known] + extra


def _clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def _summary(body: str, n: int = 3) -> tuple[str, int]:
    """Short plain version of a section for the homepage: first n bullets or two sentences, no links."""
    body = re.sub(r"\s*\((?:\s*<a [^>]*>.*?</a>\s*,?\s*(?:and\s*)?)+\)", "", body, flags=re.S)
    items = re.findall(r"<li>(.*?)</li>", body, flags=re.S)
    if items:
        lines = []
        for item in items[:n]:
            m = re.match(r"\s*(?:<p>)?\s*<strong>(.*?)</strong>(.*)", item, flags=re.S)
            lead, rest = (m.group(1), m.group(2)) if m else ("", item)
            rest = _clip(_strip_tags(rest).strip(), 110)
            lead_html = f"<b>{escape(_strip_tags(lead))}</b>{'' if rest[:1] in ':,.' else ' '}" if lead else ""
            lines.append(f"<li>{lead_html}{escape(rest)}</li>")
        return f'<ul class="sum-l">{"".join(lines)}</ul>', max(0, len(items) - n)
    text = " ".join(_strip_tags(body).split())
    two = " ".join(re.split(r"(?<=[.!?])\s+", text)[:2])
    return f'<p class="sum-p">{escape(_clip(two, 240))}</p>', 0


def _nav_link(href: str, icon: str, label: str, active: bool) -> str:
    return f'<a href="{href}" class="{"on" if active else ""}">{_icon(icon)}{label}</a>'


RUN_OVERLAY = """
<div class="runbox" id="runbox" hidden>
  <div class="run-card" role="dialog" aria-modal="true" aria-labelledby="run-t">
    <div class="run-h"><span class="spin"></span><b id="run-t">Generating a new brief</b><span class="run-time" id="run-time">0:00</span></div>
    <p class="run-note" id="run-note">Usually takes about a minute. Keep this tab open: the brief reloads here when it's ready.</p>
    <ol class="steps" id="run-steps">
      <li data-at="0">Collecting posts from Hacker News, Stack Overflow and GitHub</li>
      <li data-at="12">Reading each post and naming its pain point</li>
      <li data-at="40">Comparing mentions with last week</li>
      <li data-at="48">Writing the summary</li>
      <li data-at="70">Saving it and emailing you</li>
    </ol>
    <div class="run-bar"><u id="run-bar"></u></div>
  </div>
</div>
<script>
(() => {
  const box = document.getElementById('runbox'); let timer;
  const reset = () => {
    clearInterval(timer); box.hidden = true;
    document.querySelectorAll('form[data-run] button').forEach(b => b.disabled = false);
  };
  document.querySelectorAll('form[data-run]').forEach(f => f.addEventListener('submit', () => {
    f.querySelector('button').disabled = true; box.hidden = false;
    const steps = [...document.querySelectorAll('#run-steps li')], start = Date.now();
    const tick = () => {
      const s = (Date.now() - start) / 1000;
      document.getElementById('run-time').textContent = Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
      steps.forEach((li, i) => {
        const next = steps[i + 1], started = s >= +li.dataset.at, finished = next && s >= +next.dataset.at;
        li.className = finished ? 'done' : started ? 'active' : '';
      });
      document.getElementById('run-bar').style.width = Math.min(95, s / 80 * 100) + '%';
      if (s > 120) document.getElementById('run-note').textContent = 'Taking longer than usual, still working. The server stops after 5 minutes.';
    };
    tick(); timer = setInterval(tick, 500);
  }));
  window.addEventListener('pageshow', e => { if (e.persisted) reset(); });
})();
</script>"""


def _page(title: str, body: str, *, active: str = "", crumbs: str = "", actions: str = "",
          history: list[dict] | None = None, current_week: str | None = None, script: str = "") -> str:
    hist_links = "".join(
        f'<a href="/history/{escape(h["week_start"])}" class="{"on" if h["week_start"] == current_week else ""}">'
        f'{_icon("clock")}{escape(h["week_start"])}{"<small>Latest</small>" if i == 0 else ""}</a>'
        for i, h in enumerate(history or [])
    )
    hist_block = f'<div class="nav-h">Past briefs</div><nav class="nav">{hist_links}</nav>' if hist_links else ""
    links = [("/", "doc", "Latest brief", "brief"), ("/pain-points", "flame", "Pain points", "points"),
             ("/topics", "tag", "Topics", "topics"), ("/health", "pulse", "Health", "health")]
    nav = "".join(_nav_link(href, icon, label, active == key) for href, icon, label, key in links)
    m_nav = "".join(f'<a href="{href}" class="{"on" if active == key else ""}">{label}</a>'
                    for href, _, label, key in links)
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
{RUN_OVERLAY}
{script}
</body></html>"""


RUN_BUTTON = (
    '<form class="inline" method="post" action="/run-now" data-run>'
    '<button class="btn btn-primary" type="submit" title="Collects the last 7 days of posts and writes a fresh brief">'
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


def _flash(flash: str | None) -> str:
    if not flash:
        return ""
    bad = "failed" in flash.lower()
    return (f'<div class="flash{" err" if bad else ""}" role="status">'
            f'{_icon("pulse" if bad else "check")}{escape(flash)}</div>')


def _week_title(week: str | None) -> str:
    return f"Week of {week}" if week else "No brief yet"


def _is_latest(week: str | None, history: list[dict]) -> bool:
    return week is None or not history or week == history[0]["week_start"]


def _meter(n: int, max_m: int) -> str:
    return f'<span class="meter">{n}<i><u style="width:{n * 100 / (max_m or 1):.0f}%"></u></i></span>'


def dashboard(brief_html: str, metrics_rows: list[dict], history: list[dict],
              week_start: str | None, flash: str | None = None) -> str:
    """Homepage: headline numbers and a short version of every section, each linking to its full page."""
    is_latest = _is_latest(week_start, history)
    title = _week_title(week_start)
    base = f"/brief/{escape(week_start or '')}"

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

    def card(s: dict, wide: bool = False) -> str:
        summary, more = _summary(s["body"])
        foot = f'<div class="sum-f">+{more} more</div>' if more else ""
        return (f'<a class="sum tone-{s["tone"]}{" wide" if wide else ""}" href="{base}/{s["key"]}">'
                f'<div class="sum-h"><span class="ic t">{_icon(s["icon"])}</span>{escape(s["label"])}'
                f'<span class="go">Read more →</span></div>{summary}{foot}</a>')

    # Preview of the pain point table; the full one lives on its own page.
    max_m = max((m["mention_count"] for m in metrics_rows), default=0)
    preview_rows = "".join(
        f'<tr><td class="pp">{escape(m["pain_point"])}</td>'
        f'<td class="hide-sm"><span class="pill {_cat_class(m.get("category") or "Other")}">{escape(m.get("category") or "Other")}</span></td>'
        f'<td class="n">{_meter(m["mention_count"], max_m)}</td></tr>'
        for m in metrics_rows[:5]
    )
    all_card = (f'<a class="sum tone-ink wide" href="{base}/pain-points">'
                f'<div class="sum-h"><span class="ic t">{_icon("search")}</span>All pain points'
                f'<small>{len(metrics_rows)}</small><span class="go">View all →</span></div>'
                f'<table class="mini"><tbody>{preview_rows}</tbody></table>'
                + (f'<div class="sum-f">+{len(metrics_rows) - 5} more pain points</div>' if len(metrics_rows) > 5 else "")
                + '</a>') if metrics_rows and week_start else ""

    sections = parse_brief(brief_html) if week_start else []
    by_key = {s["key"]: s for s in sections}
    grid = ""
    if "overview" in by_key:
        grid += card(by_key["overview"], wide=True)
    if "top-pain-points" in by_key:
        grid += card(by_key["top-pain-points"], wide=True)
    grid += all_card
    grid += "".join(card(s) for s in sections if s["key"] not in ("overview", "top-pain-points"))
    if not grid:
        grid = '<div class="card wide"><div class="empty">No brief yet. Click <b>Run now</b> to generate the first one.</div></div>'

    if is_latest:
        hour = datetime.now(IST).hour
        greeting = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 17 else "Good evening"
        eyebrow = f'<span class="dot"></span>Latest brief · {escape(title)}'
        heading = f"{greeting}, Sumit"
        lede = ("Here's what developers said this week on Hacker News, Stack Overflow and GitHub. "
                "Start with the top pain points, then open any card for the details and sources.")
    else:
        eyebrow = '<span class="dot" style="background:var(--text-4)"></span>Past brief'
        heading = title
        lede = "A brief from an earlier week. Open any card for the details and sources."
    body = f"""
<main class="content narrow">
  <div>
    {_flash(flash)}
    <div class="eyebrow">{eyebrow}</div>
    <h1>{escape(heading)}</h1>
    <p class="lede">{lede}</p>
    {stats}
    <div class="sgrid">{grid}</div>
  </div>
</main>"""
    crumbs = f'<a href="/">Briefs</a><span>/</span><b>{escape(title)}</b>'
    return _page(f"{title} · Dev Community Pulse", body, active="brief" if is_latest else "",
                 crumbs=crumbs, actions=RUN_BUTTON, history=history, current_week=week_start,
                 script=CLEAR_RUN_JS)


CLEAR_RUN_JS = """<script>
// drop ?run=… so a refresh doesn't repeat the message
if (location.search.includes('run=')) history.replaceState(null, '', location.pathname);
</script>"""


def _rail(week: str, sections: list[dict], current: str) -> str:
    base = f"/brief/{escape(week)}"
    links = "".join(
        f'<a href="{base}/{s["key"]}" class="tone-{s["tone"]}{" on" if s["key"] == current else ""}">{escape(s["label"])}</a>'
        for s in sections
    )
    links += f'<a href="{base}/pain-points" class="tone-ink{" on" if current == "pain-points" else ""}">All pain points</a>'
    return f'<aside class="rail"><h4>In this brief</h4>{links}</aside>'


def section_page(week: str, sections: list[dict], key: str, history: list[dict]) -> str:
    """Full text of one brief section, with links to the others."""
    i = next(idx for idx, s in enumerate(sections) if s["key"] == key)
    s = sections[i]
    base = f"/brief/{escape(week)}"
    prev_link = (f'<a class="pn" href="{base}/{sections[i - 1]["key"]}"><small>Previous</small>← {escape(sections[i - 1]["label"])}</a>'
                 if i > 0 else f'<a class="pn" href="/history/{escape(week)}"><small>Back</small>← Brief overview</a>')
    next_link = (f'<a class="pn r" href="{base}/{sections[i + 1]["key"]}"><small>Next</small>{escape(sections[i + 1]["label"])} →</a>'
                 if i + 1 < len(sections) else f'<a class="pn r" href="{base}/pain-points"><small>Next</small>All pain points →</a>')
    todo = " todo" if key == "sprint-actions" else ""
    hint = '<p class="hint">Click an action to tick it off. Ticks are saved in this browser.</p>' if todo else ""
    note = f'<p class="lede">{SECTION_INTRO[key]}</p>' if key in SECTION_INTRO else ""

    title = _week_title(week)
    body = f"""
<main class="content">
  <div>
    <a class="back" href="/history/{escape(week)}">← {escape(title)}</a>
    <h1 class="sec-title tone-{s['tone']}"><span class="ic t">{_icon(s['icon'])}</span>{escape(s['label'])}</h1>
    {note}
    <section class="card tone-{s['tone']} accent"><div class="card-b{todo}">{s['body']}</div></section>
    {hint}
    <nav class="pager">{prev_link}{next_link}</nav>
  </div>
  {_rail(week, sections, key)}
</main>"""
    crumbs = (f'<a href="/">Briefs</a><span>/</span><a href="/history/{escape(week)}">{escape(title)}</a>'
              f'<span>/</span><b>{escape(s["label"])}</b>')
    return _page(f"{s['label']} · {title}", body, crumbs=crumbs, actions=RUN_BUTTON,
                 history=history, current_week=week, script=_todo_js(week) if todo else "")


def pain_points_page(week: str | None, metrics_rows: list[dict], sections: list[dict], history: list[dict]) -> str:
    """Every pain point for the week, with category filters, search and sorting."""
    max_m = max((m["mention_count"] for m in metrics_rows), default=0)
    categories = sorted({m.get("category") or "Other" for m in metrics_rows})
    rows_html = ""
    for m in metrics_rows:
        cat = m.get("category") or "Other"
        n, u, e = m["mention_count"], m.get("unresolved_count") or 0, m.get("engagement") or 0
        href = _point_href(m["pain_point"], week)
        rows_html += (
            f'<tr data-cat="{escape(cat)}" data-href="{href}">'
            f'<td class="pp"><a href="{href}">{escape(m["pain_point"])}</a></td>'
            f'<td><span class="pill {_cat_class(cat)}">{escape(cat)}</span></td>'
            f'<td class="n" data-v="{n}">{_meter(n, max_m)}</td>'
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
</table><div class="tfoot" id="count">{len(metrics_rows)} pain points</div></div>
<p class="hint">Unresolved: threads without an accepted answer or fix. Engagement: votes plus comments.</p>"""
    else:
        table = '<div class="tbl"><div class="empty">No pain points yet. Click <b>Run now</b> to generate the first brief.</div></div>'

    title = _week_title(week)
    back = f'<a class="back" href="/history/{escape(week)}">← {escape(title)}</a>' if week else ""
    body = f"""
<main class="content{"" if week else " narrow"}">
  <div>
    {back}
    <h1 class="sec-title tone-ink"><span class="ic t">{_icon("search")}</span>All pain points</h1>
    <p class="lede">Every problem developers raised in the {escape(title.lower())}. Click a row to see its history and the threads behind it.</p>
    {table}
  </div>
  {_rail(week, sections, "pain-points") if week else ""}
</main>"""
    crumbs = (f'<a href="/">Briefs</a><span>/</span>'
              + (f'<a href="/history/{escape(week)}">{escape(title)}</a><span>/</span>' if week else "")
              + "<b>All pain points</b>")
    return _page(f"All pain points · {title}", body, active="points" if _is_latest(week, history) else "",
                 crumbs=crumbs, actions=RUN_BUTTON, history=history, current_week=week, script=TABLE_JS)


def _point_href(name: str, week: str | None) -> str:
    return escape(f"/pain-point?name={quote(name)}" + (f"&week={quote(week)}" if week else ""))


def _short_date(week: str) -> str:
    try:
        return datetime.strptime(week, "%Y-%m-%d").strftime("%b %d")
    except ValueError:
        return week


def _bar_chart(points: list[dict], current: str | None) -> str:
    """Mentions per week as an SVG bar chart: one series, thin bars, rounded tops, hover tooltips."""
    w, h, left, top, bottom = 640, 200, 28, 20, 26
    plot_w, plot_h = w - left - 8, h - top - bottom
    top_val = max([p["mention_count"] for p in points] + [3])
    step = max(1, -(-top_val // 3))          # 3 gridlines, whole numbers
    y_max = step * 3
    slot = plot_w / max(len(points), 1)
    bw = min(40, slot * 0.56)
    y = lambda v: top + plot_h - v / y_max * plot_h
    parts = [f'<line class="grid" x1="{left}" x2="{w - 8}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
             f'<text class="ax" x="{left - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>'
             for v in range(step, y_max + 1, step)]
    parts.append(f'<line class="base" x1="{left}" x2="{w - 8}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>'
                 f'<text class="ax" x="{left - 8}" y="{y(0) + 4:.1f}" text-anchor="end">0</text>')
    for i, p in enumerate(points):
        v = p["mention_count"]
        cx = left + slot * i + slot / 2
        x0, x1, yt, yb = cx - bw / 2, cx + bw / 2, y(v), y(0)
        r = min(4, (yb - yt) / 2, bw / 2)
        bar = (f"M{x0:.1f},{yb:.1f} V{yt + r:.1f} Q{x0:.1f},{yt:.1f} {x0 + r:.1f},{yt:.1f} "
               f"H{x1 - r:.1f} Q{x1:.1f},{yt:.1f} {x1:.1f},{yt + r:.1f} V{yb:.1f} Z") if v else ""
        cur = p["week_start"] == current
        tip = (f'Week of {_short_date(p["week_start"])}: {v} mention{"s" if v != 1 else ""}, '
               f'{p.get("unresolved_count") or 0} unresolved')
        parts.append(
            f'<g data-tip="{escape(tip)}" data-x="{cx / w * 100:.2f}" data-y="{yt / h * 100:.2f}">'
            f'<rect class="hit" x="{cx - slot / 2:.1f}" y="{top}" width="{slot:.1f}" height="{plot_h}"/>'
            + (f'<path class="bar{" cur" if cur else ""}" d="{bar}"/>' if bar else "")
            + (f'<text class="val" x="{cx:.1f}" y="{yt - 6:.1f}" text-anchor="middle">{v}</text>' if cur else "")
            + f'<text class="ax" x="{cx:.1f}" y="{h - 6}" text-anchor="middle">{_short_date(p["week_start"])}</text></g>')
    return (f'<div class="chart"><svg viewBox="0 0 {w} {h}" role="img" aria-label="Mentions per week">'
            f'{"".join(parts)}</svg><div class="tip" hidden></div></div>')


def pain_point_page(name: str, week: str | None, weeks: list[dict], threads: list[dict], history: list[dict]) -> str:
    """One pain point: headline numbers, mentions per week, and the threads it came from."""
    cur = next((p for p in weeks if p["week_start"] == week), weeks[-1] if weeks else None)
    idx = weeks.index(cur) if cur else -1
    prev = weeks[idx - 1] if idx > 0 else None
    n = cur["mention_count"] if cur else 0
    category = (cur or {}).get("category") or "Other"
    if prev:
        d = n - prev["mention_count"]
        change = (f'<span class="{"up" if d > 0 else "down" if d < 0 else ""}">'
                  f'{"↑" if d > 0 else "↓" if d < 0 else "→"} {abs(d) if d else "no change"}</span> vs previous brief')
    else:
        change = "first week tracked"
    stats = f"""
<div class="stats">
  <div class="stat"><span>Mentions</span><b>{n}</b><em>{change}</em></div>
  <div class="stat"><span>Unresolved</span><b>{(cur or {}).get("unresolved_count") or 0}</b><em>threads without a fix</em></div>
  <div class="stat"><span>Engagement</span><b>{(cur or {}).get("engagement") or 0:,}</b><em>votes + comments</em></div>
  <div class="stat"><span>Weeks seen</span><b>{sum(1 for p in weeks if p["mention_count"])}</b><em>of the last {len(weeks)} tracked</em></div>
</div>"""
    note = ('<p class="hint">Tracking started this week. A new bar is added every Friday.</p>'
            if len(weeks) < 2 else "")
    table_rows = "".join(
        f'<tr><td>{escape(p["week_start"])}</td><td class="n">{p["mention_count"]}</td>'
        f'<td class="n">{p.get("unresolved_count") or 0}</td><td class="n">{p.get("engagement") or 0:,}</td></tr>'
        for p in reversed(weeks))
    chart = f"""
<section class="chart-card">
  <h3>Mentions per week</h3>
  <p class="sub">How often developers raised this, week by week. The highlighted bar is the week you're viewing.</p>
  {_bar_chart(weeks, week)}
  {note}
  <details class="tv"><summary>Show as a table</summary>
    <div class="tbl"><table><thead><tr><th>Week</th><th class="n">Mentions</th><th class="n">Unresolved</th><th class="n">Engagement</th></tr></thead>
    <tbody>{table_rows}</tbody></table></div></details>
</section>"""

    labels = {"hackernews": "Hacker News", "hn": "Hacker News", "stackoverflow": "Stack Overflow",
              "so": "Stack Overflow", "github": "GitHub", "gh": "GitHub"}
    items = ""
    for t in threads:
        src = (t.get("source") or "").lower()
        state = ('<span class="st-open">Unresolved</span>' if t.get("is_unresolved")
                 else '<span class="st-done">Resolved</span>')
        url = t.get("url") or ""
        safe_url = escape(url) if url.startswith(("https://", "http://")) else "#"
        items += (f'<a class="thread" href="{safe_url}" target="_blank" rel="noopener noreferrer">'
                  f'<div class="meta"><span class="src {escape(src)}">{escape(labels.get(src, src or "Source"))}</span>'
                  f'<span>{escape((t.get("created_at") or "")[:10])}</span></div>'
                  f'<b>{escape(t.get("title") or "Untitled thread")}</b>'
                  f'<div class="meta"><span>▲ {t.get("score") or 0}</span><span>{t.get("comments") or 0} comments</span>{state}</div></a>')
    threads_html = (f'<div class="threads">{items}</div>' if items
                    else '<div class="tbl"><div class="empty">No threads stored for this pain point.</div></div>')

    title = name[:1].upper() + name[1:]
    back = (f'<a class="back" href="/brief/{escape(week)}/pain-points">← All pain points</a>' if week
            else '<a class="back" href="/pain-points">← All pain points</a>')
    body = f"""
<main class="content narrow">
  <div>
    {back}
    <h1>{escape(title)}</h1>
    <p class="lede" style="margin-bottom:var(--s6)"><span class="pill {_cat_class(category)}">{escape(category)}</span>
      &nbsp;{escape(_week_title(week)) if week else ""}</p>
    {stats}
    {chart}
    <h2 class="sec">Threads behind it <small>{len(threads)}</small></h2>
    {threads_html}
  </div>
</main>"""
    crumbs = (f'<a href="/">Briefs</a><span>/</span><a href="/brief/{escape(week or "")}/pain-points">All pain points</a>'
              f'<span>/</span><b>{escape(title)}</b>')
    return _page(f"{title} · Dev Community Pulse", body, active="points", crumbs=crumbs, actions=RUN_BUTTON,
                 history=history, current_week=week, script=CHART_JS)


CHART_JS = """<script>
(() => {
  // per-bar tooltip; hit area is the whole week column
  document.querySelectorAll('.chart').forEach(chart => {
    const tip = chart.querySelector('.tip');
    chart.querySelectorAll('g[data-tip]').forEach(g => {
      g.addEventListener('mouseenter', () => {
        tip.textContent = g.dataset.tip; tip.hidden = false;
        tip.style.left = g.dataset.x + '%'; tip.style.top = g.dataset.y + '%';
      });
      g.addEventListener('mouseleave', () => tip.hidden = true);
    });
  });
})();
</script>"""


def _todo_js(week: str) -> str:
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
})();
</script>"""


TABLE_JS = """<script>
(() => {
  // filter by category + text, sort by column
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
  rows.forEach(r => r.addEventListener('click', e => { if (!e.target.closest('a')) location.href = r.dataset.href; }));
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
