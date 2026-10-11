"""Plain HTML views — no templating engine. Linear-style app shell.

Design tokens follow one scale: type 12/13/14/16/20/28px, spacing on a 4px grid.
"""
import re
from datetime import date, datetime, timedelta, timezone
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
    --radius: 12px; --radius-sm: 8px;
    --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    --serif: 'Newsreader', 'Iowan Old Style', Georgia, serif;
    /* warm paper surfaces; rust = rising / problem, blue = falling, ink = emphasis */
    --bg: #f4f3ef; --panel: #f9f8f5; --surface: #ffffff; --hover: #f6f5f1; --chip: #efede8;
    --border: #e5e2db; --border-soft: #efede8;
    --text: #1c1b19; --text-2: #45423d; --text-3: #75716a; --text-4: #a39f97;
    --ink: #18181b; --ink-hover: #2c2c30; --accent: #b9410f; --accent-strong: #b9410f; --accent-on-ink: #f0a06c;
    --accent-soft: rgba(194,65,12,.10);
    --up: #b9410f; --up-bg: #fbe7da; --down: #1d4ed8; --down-bg: #e2eafc;
    --peach: #fbeadf; --peach-border: #f3d3bf;
    --series-0: #c2410c; --series-1: #2563eb; --series-2: #1c1b19;
    --btn-bg: #18181b; --btn-hover: #2c2c30; --btn-fg: #ffffff;
    --link: #b9410f; --bar: #c2410c; --bar-muted: #f1c4a6;
    --green: #15803d; --red: #c2410c; --amber: #b45309; --warn-text: #b45309;
    --flash: rgba(194,65,12,.07);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      color-scheme: dark;
      --bg: #141311; --panel: #1a1917; --surface: #1e1d1b; --hover: #262522; --chip: #2a2926;
      --border: #33312d; --border-soft: #282724;
      --text: #f2f0eb; --text-2: #cfccc4; --text-3: #9d9990; --text-4: #6f6b64;
      --ink: #f2f0eb; --ink-hover: #ffffff; --accent: #f08a52; --accent-strong: #f08a52; --accent-on-ink: #b9410f;
      --accent-soft: rgba(240,138,82,.14);
      --up: #f59a68; --up-bg: #3a2418; --down: #8fb0ff; --down-bg: #1b2742;
      --peach: #2a201a; --peach-border: #4a3122;
      --series-0: #f08a52; --series-1: #6f9bff; --series-2: #e8e5de;
      --btn-bg: #f2f0eb; --btn-hover: #ffffff; --btn-fg: #141311;
      --link: #f59a68; --bar: #f08a52; --bar-muted: #6b3a22;
      --green: #4ade80; --red: #f08a52; --amber: #f5b13d; --warn-text: #f5b13d;
      --flash: rgba(240,138,82,.10);
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

  /* ================= Friday Brief ================= */
  body { background: var(--bg); }
  .mono { font-family: var(--mono); }
  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
  .topnav { position: sticky; top: 0; z-index: 20; background: color-mix(in srgb, var(--bg) 90%, transparent);
            backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); }
  .topnav-in { max-width: 1240px; margin: 0 auto; height: 60px; display: flex; align-items: center; gap: var(--s4); padding: 0 var(--s6); }
  .brand2 { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 15px; white-space: nowrap; }
  .brand2 i { width: 26px; height: 26px; border-radius: 7px; background: var(--ink); color: var(--accent-on-ink); display: grid; place-items: center; }
  .scope { font-family: var(--mono); font-size: 11px; color: var(--text-3); border: 1px solid var(--border); border-radius: 999px;
           padding: 3px 10px; white-space: nowrap; }
  .tabs { margin-left: auto; display: flex; gap: 2px; overflow-x: auto; }
  .tabs a { padding: 7px 14px; border-radius: 8px; font-size: var(--fs-md); color: var(--text-2); white-space: nowrap; }
  .tabs a:hover { background: var(--hover); color: var(--text); }
  .tabs a.on { background: var(--chip); color: var(--text); font-weight: 500; }
  .nav-right { display: flex; align-items: center; gap: var(--s2); }
  .wpick select { font: inherit; font-size: var(--fs-sm); color: var(--text-2); background: var(--surface); border: 1px solid var(--border);
                  border-radius: 8px; padding: 6px 10px; cursor: pointer; }
  .crumbs-row { max-width: 1180px; margin: var(--s5) auto 0; padding: 0 var(--s8); }
  .main, .app { display: block; }
  .content { padding-top: var(--s6); }
  .foot { max-width: 1240px; margin: 0 auto; padding: var(--s6); display: flex; justify-content: space-between; gap: var(--s4);
          font-size: var(--fs-xs); color: var(--text-3); border-top: 1px solid var(--border); }
  .foot a:hover { color: var(--text); }

  .fb { max-width: 1240px; margin: 0 auto; padding: var(--s8) var(--s6) var(--s12); }
  .fb-eyebrow { font-family: var(--mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
  .fb-h1 { font-family: var(--serif); font-weight: 400; font-size: 44px; line-height: 1.1; letter-spacing: -.015em; margin: 10px 0 10px; }
  .fb-sub { color: var(--text-2); max-width: 640px; margin: 0; font-size: var(--fs-md); line-height: 1.6; }
  .fb-head { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--s6); align-items: end; }
  .fb-actions { display: flex; flex-direction: column; align-items: flex-end; gap: var(--s3); }
  .gen { font-size: 11px; color: var(--text-3); white-space: nowrap; }
  .fb-btns { display: flex; gap: var(--s2); }
  .btn { height: 38px; padding: 0 var(--s4); border-radius: 9px; font-size: var(--fs-md); }
  .btn-primary { background: var(--ink); border-color: var(--ink); color: var(--bg); }
  .btn-primary:hover { background: var(--ink-hover); }
  .topnav .btn { height: 34px; }

  .kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: var(--s6); }
  .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; min-width: 0; }
  .kpi .l { font-size: var(--fs-sm); color: var(--text-2); }
  .kpi .v { font-size: 30px; font-weight: 700; letter-spacing: -.02em; margin-top: var(--s2); display: flex; align-items: center; gap: var(--s2); flex-wrap: wrap; }
  .kpi .v small { font-size: var(--fs-sm); font-weight: 400; color: var(--text-3); letter-spacing: 0; }
  .kpi .s { font-size: var(--fs-xs); color: var(--text-3); margin-top: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .kpi.dark { background: var(--ink); border-color: var(--ink); color: var(--bg); }
  .kpi.dark .l, .kpi.dark .s { color: color-mix(in srgb, var(--bg) 70%, var(--ink)); }
  .kpi.dark .v small { color: var(--accent-on-ink); font-size: 12px; }
  .chg { font-family: var(--mono); font-size: 11px; font-weight: 500; padding: 2px 6px; border-radius: 4px; white-space: nowrap; letter-spacing: 0; }
  .chg.up { background: var(--up-bg); color: var(--up); } .chg.down { background: var(--down-bg); color: var(--down); }
  .chg.flat { background: var(--chip); color: var(--text-3); }

  .row2 { display: grid; grid-template-columns: minmax(0, 2.1fr) minmax(0, 1fr); gap: 14px; margin-top: 14px; }
  .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 22px 24px; min-width: 0; }
  .panel-h { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--s4); }
  .panel h2, .ph, .sec-h h2 { font-size: 17px; font-weight: 600; margin: 0; letter-spacing: -.01em; }
  .panel-h .meta { font-family: var(--mono); font-size: 11px; color: var(--text-3); white-space: nowrap; padding-top: 4px; }
  .sub { font-size: var(--fs-xs); color: var(--text-3); margin: 4px 0 0; line-height: 1.5; }
  .plan { list-style: none; padding: 0; margin: var(--s4) 0 0; }
  .plan li { display: flex; gap: 14px; padding: 7px 0; font-size: var(--fs-md); line-height: 1.6; color: var(--text-2); }
  .plan li b { color: var(--text); font-weight: 600; }
  .plan .n { flex: none; width: 24px; height: 24px; margin-top: 1px; border-radius: 6px; display: grid; place-items: center;
             font-size: 12px; font-weight: 600; background: var(--up-bg); color: var(--up); }
  .plan li:nth-child(3) .n { background: var(--down-bg); color: var(--down); }
  .readmore { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: var(--s4); padding-top: var(--s4);
              border-top: 1px solid var(--border-soft); font-size: var(--fs-xs); color: var(--text-3); }
  .readmore a { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--border); border-radius: 999px; padding: 4px 10px; color: var(--text-2); }
  .readmore a::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--tone); }
  .readmore a:hover { background: var(--hover); color: var(--text); }
  .opp { background: var(--peach); border: 1px solid var(--peach-border); border-radius: 14px; padding: 22px 24px; display: flex; flex-direction: column; min-width: 0; }
  .opp-q { font-family: var(--serif); font-size: 25px; line-height: 1.25; margin: 14px 0 10px; color: var(--text); }
  .opp p { font-size: var(--fs-sm); color: var(--text-2); margin: 0; line-height: 1.55; }
  .opp-link { margin-top: auto; padding-top: var(--s5); font-size: var(--fs-sm); font-weight: 600; color: var(--up); text-decoration: underline; text-underline-offset: 3px; }

  .seg { display: inline-flex; background: var(--chip); border-radius: 10px; padding: 3px; flex: none; }
  .seg button { border: 0; background: none; padding: 6px 14px; border-radius: 8px; font: inherit; font-size: var(--fs-sm); color: var(--text-3); cursor: pointer; }
  .seg button.on { background: var(--surface); color: var(--text); font-weight: 500; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
  .rank-wrap { overflow-x: auto; margin-top: var(--s4); }
  table.rank { width: 100%; border-collapse: collapse; font-size: var(--fs-md); }
  .rank th { font-family: var(--mono); font-size: 11px; font-weight: 400; letter-spacing: .06em; text-transform: uppercase; color: var(--text-3);
             text-align: left; padding: 10px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  .rank td { padding: 13px 10px; border-bottom: 1px solid var(--border-soft); vertical-align: middle; }
  .rank tbody tr { cursor: pointer; } .rank tbody tr:hover td { background: var(--hover); }
  .rank .num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .rank td.num { color: var(--text-3); } .rank td.cur { color: var(--text); font-weight: 700; }
  .rank .idx { font-family: var(--mono); color: var(--text-3); width: 36px; }
  .rank .tn { min-width: 240px; } .rank .tn b { display: block; font-weight: 600; } .rank .tn small { color: var(--text-3); font-size: var(--fs-xs); }
  .spark polyline { fill: none; stroke-width: 1.6; stroke-linejoin: round; stroke-linecap: round; }
  .spark.up polyline { stroke: var(--up); } .spark.up circle { fill: var(--up); }
  .spark.down polyline { stroke: var(--down); } .spark.down circle { fill: var(--down); }
  .cov { font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 999px; white-space: nowrap; }
  .cov.bad { background: var(--ink); color: var(--bg); } .cov.mid { background: var(--chip); color: var(--text-2); }
  .cov.ok { border: 1px solid var(--border); color: var(--text-3); font-weight: 500; }
  .more { display: inline-block; margin-top: var(--s4); font-size: var(--fs-sm); font-weight: 500; color: var(--text-2); }
  .more:hover { color: var(--text); }

  .legend { display: flex; flex-wrap: wrap; gap: var(--s4); margin: var(--s2) 0 var(--s2); font-size: var(--fs-xs); color: var(--text-2); }
  .lg { display: inline-flex; align-items: center; gap: 6px; }
  .lg i { width: 16px; border-top: 2px solid var(--c); }
  .lg.s2 i { border-top-style: dashed; }
  .lc { position: relative; }
  .lc svg { display: block; width: 100%; height: auto; overflow: visible; }
  .lc .grid { stroke: var(--border-soft); } .lc .ax { fill: var(--text-3); font-size: 11px; font-family: var(--mono); }
  .lc .ln { fill: none; stroke-width: 2; stroke: var(--c); stroke-linejoin: round; stroke-linecap: round; }
  .lc .s2.ln { stroke-dasharray: 5 4; }
  .lc .pt { fill: var(--c); stroke: var(--surface); stroke-width: 2; }
  .lc .dl { fill: var(--text); font-size: 12px; font-weight: 600; font-family: inherit; }
  .s0 { --c: var(--series-0); } .s1 { --c: var(--series-1); } .s2 { --c: var(--series-2); }
  .lc .xh { stroke: var(--text-4); stroke-width: 1; opacity: 0; } .lc g:hover .xh { opacity: 1; }
  .lc .hit { fill: transparent; }
  .srow { margin: 14px 0; font-size: var(--fs-md); }
  .srow > div { display: flex; justify-content: space-between; margin-bottom: 6px; }
  .srow .mono { font-size: var(--fs-xs); color: var(--text-3); }
  .srow i { display: block; height: 6px; border-radius: 3px; background: var(--chip); overflow: hidden; }
  .srow u { display: block; height: 100%; border-radius: 3px; }
  u.s-hn { background: var(--series-0); } u.s-so { background: var(--series-1); } u.s-gh { background: var(--series-2); }

  .sec-h { display: flex; justify-content: space-between; align-items: flex-end; gap: var(--s4); margin: var(--s10) 0 var(--s4); }
  .sec-h .more { margin: 0; font-size: 11px; }
  .ucards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
  .ucard { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; display: flex; flex-direction: column; gap: var(--s2); min-width: 0; }
  .u-top { display: flex; justify-content: space-between; gap: var(--s2); align-items: center; }
  .schip { font-family: var(--mono); font-size: 11px; background: var(--chip); border-radius: 5px; padding: 2px 8px; color: var(--text-2); }
  .u-cat { font-size: 11px; font-weight: 600; color: var(--up); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ucard h3 { font-size: 15px; font-weight: 600; line-height: 1.4; margin: 4px 0 0; }
  .ucard p { font-size: var(--fs-sm); color: var(--text-2); margin: 0; line-height: 1.55; }
  .u-foot { margin-top: auto; padding-top: var(--s2); display: flex; justify-content: space-between; align-items: center; gap: var(--s2); }
  .u-foot .mono { font-size: 11px; color: var(--text-3); }
  .u-foot .btn { height: 34px; font-size: var(--fs-sm); }

  .kwp { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: var(--s8); margin-top: var(--s10);
         background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 22px 24px; }
  .kchips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: var(--s4); }
  .kchip { font-family: var(--mono); font-size: 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 4px 9px; }
  .runs { margin: 0; display: flex; flex-direction: column; gap: 10px; font-size: var(--fs-sm); }
  .runs > div { display: flex; justify-content: space-between; gap: var(--s3); }
  .runs dt { color: var(--text-3); } .runs dd { margin: 0; font-family: var(--mono); font-size: 12px; text-align: right; }
  .runs .btn { justify-content: center; margin-top: 6px; }

  @media (max-width: 1000px) {
    .scope { display: none; }
    .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .row2, .kwp { grid-template-columns: minmax(0, 1fr); }
    .ucards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .fb-head { grid-template-columns: minmax(0, 1fr); } .fb-actions { align-items: flex-start; }
  }
  @media (max-width: 680px) {
    .topnav-in { padding: 0 var(--s4); gap: var(--s2); }
    .brand2 { font-size: 0; gap: 0; }
    .wpick { display: none; }
    .fb { padding: var(--s6) var(--s4) var(--s10); }
    .fb-h1 { font-size: 32px; }
    .kpis, .ucards { grid-template-columns: minmax(0, 1fr); }
    .panel, .opp, .kwp { padding: 18px; }
    .panel-h { flex-direction: column; }
    .crumbs-row { padding: 0 var(--s4); }
  }

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
    body = re.sub(r"\s*[(\[](?:\s*<a [^>]*>.*?</a>\s*,?\s*(?:and\s*)?)+[)\]]", "", body, flags=re.S)
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
          history: list[dict] | None = None, current_week: str | None = None, script: str = "",
          hide_run: bool = False) -> str:
    tabs = [("/", "This week", "brief"), ("/pain-points", "Pain points", "points"),
            ("/unresolved", "Unresolved", "unresolved"), ("/topics", "Keywords", "topics")]
    nav = "".join(f'<a href="{href}" class="{"on" if active == key else ""}">{label}</a>' for href, label, key in tabs)
    weeks = "".join(
        f'<option value="/history/{escape(h["week_start"])}"{" selected" if h["week_start"] == current_week else ""}>'
        f'Week {_week_no(h["week_start"])}{" · latest" if i == 0 else ""}</option>'
        for i, h in enumerate(history or []))
    picker = (f'<label class="wpick"><span class="sr">Choose a brief</span><select onchange="location.href=this.value">'
              f'{weeks}</select></label>' if len(history or []) > 1 else "")
    crumb_row = f'<div class="crumbs-row"><div class="crumbs">{crumbs}</div></div>' if crumbs else ""
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
{BASE_CSS}
</head><body>
<header class="topnav"><div class="topnav-in">
  <a class="brand2" href="/"><i>{_icon("pulse")}</i>DevPulse</a>
  <span class="scope">code-review · CI/CD · dev workflow</span>
  <nav class="tabs">{nav}</nav>
  <div class="nav-right">{picker}{"" if hide_run else RUN_BUTTON}</div>
</div></header>
{crumb_row}
{body}
<footer class="foot"><span>DevPulse · new brief every Friday, 8:30 AM IST</span><a href="/health">System health</a></footer>
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
    return _page("Setup needed · DevPulse", body,
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


_ACRONYMS = {"ai": "AI", "llm": "LLM", "llms": "LLMs", "ci": "CI", "cd": "CD", "pr": "PR", "prs": "PRs", "api": "API",
             "apis": "APIs", "ui": "UI", "ide": "IDE", "sdk": "SDK", "cli": "CLI", "js": "JS", "ts": "TS", "sql": "SQL",
             "aws": "AWS", "gpu": "GPU", "mcp": "MCP", "json": "JSON", "yaml": "YAML", "ssh": "SSH", "lp": "LP"}


def _caps(text: str) -> str:
    """Restore acronyms in lower-cased pain point labels: 'ai generated code' -> 'AI generated code'."""
    return re.sub(r"[a-z]+", lambda m: _ACRONYMS.get(m.group(0), m.group(0)), text)


def _nice(name: str) -> str:
    name = _caps(name)
    return name[:1].upper() + name[1:]


def _parse_ts(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _ist_label(iso: str | None) -> str:
    d = _parse_ts(iso)
    return d.astimezone(IST).strftime("%a %d %b, %I:%M %p IST").replace(" 0", " ") if d else "—"


def _next_run_label() -> str:
    now = datetime.now(IST)
    run = (now + timedelta(days=(4 - now.weekday()) % 7)).replace(hour=8, minute=30, second=0, microsecond=0)
    if run <= now:
        run += timedelta(days=7)
    return run.strftime("%a %d %b, %I:%M %p IST").replace(" 0", " ")


def _ago(iso: str | None) -> str:
    d = _parse_ts(iso)
    if not d:
        return ""
    days = (datetime.now(timezone.utc) - d).days
    return "today" if days <= 0 else f"{days} day{'s' if days != 1 else ''} ago"


def _week_no(week: str) -> int:
    return date.fromisoformat(week).isocalendar()[1]


def _chg(cur: int, prev: int | None) -> str:
    """Change badge: rust for up, blue for down."""
    if prev is None:
        return '<span class="chg flat">—</span>'
    if prev == 0:
        return '<span class="chg up">new</span>' if cur else '<span class="chg flat">0</span>'
    pct = round((cur - prev) / prev * 100)
    if pct == 0:
        return '<span class="chg flat">0%</span>'
    return f'<span class="chg {"up" if pct > 0 else "down"}">{"▲" if pct > 0 else "▼"} {abs(pct)}%</span>'


def _spark(vals: list[int]) -> str:
    w, h, pad = 88, 26, 4
    top = max(vals + [1])
    n = len(vals)
    xs = [pad + (w - 2 * pad) * (i / (n - 1) if n > 1 else 1) for i in range(n)]
    ys = [h - pad - (v / top) * (h - 2 * pad) for v in vals]
    trend = "down" if n > 1 and vals[-1] < vals[-2] else "up"
    line = (f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))}"/>' if n > 1 else "")
    return (f'<svg class="spark {trend}" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">'
            f'{line}<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3"/></svg>')


def _cov(n: int, u: int) -> str:
    if n and u >= n:
        return '<span class="cov bad">Unsolved</span>'
    if u:
        return '<span class="cov mid">Partly solved</span>'
    return '<span class="cov ok">Solved</span>'


_SRC = {"hackernews": ("Hacker News", "s-hn"), "hn": ("Hacker News", "s-hn"),
        "stackoverflow": ("Stack Overflow", "s-so"), "so": ("Stack Overflow", "s-so"),
        "github": ("GitHub", "s-gh"), "gh": ("GitHub", "s-gh")}


def _src(source: str | None) -> tuple[str, str]:
    return _SRC.get((source or "").lower(), (source or "Source", "s-gh"))


def _plain_text(text: str | None, n: int) -> str:
    text = re.sub(r"<[^>]+>|```.*?```|`|[*_#>\[\]]", " ", text or "", flags=re.S)
    return _clip(text, n)


def _thread_card(t: dict) -> str:
    label, cls = _src(t.get("source"))
    url = t.get("url") or ""
    safe = escape(url) if url.startswith(("https://", "http://")) else "#"
    desc = _plain_text(t.get("body"), 150)
    return (f'<article class="ucard"><div class="u-top"><span class="schip {cls}">{escape(label)}</span>'
            f'<span class="u-cat">{escape(t.get("category") or "")}</span></div>'
            f'<h3>{escape(t.get("title") or "Untitled thread")}</h3>'
            + (f'<p>{escape(desc)}</p>' if desc else "")
            + f'<div class="u-foot"><span class="mono">{t.get("comments") or 0} comments · ▲ {t.get("score") or 0}'
              f'{" · " + _ago(t.get("created_at")) if t.get("created_at") else ""}</span>'
              f'<a class="btn" href="{safe}" target="_blank" rel="noopener noreferrer">Open thread ↗</a></div></article>')


def _unresolved(posts: list[dict]) -> list[dict]:
    return sorted((p for p in posts if p.get("is_unresolved")),
                  key=lambda p: -((p.get("comments") or 0) + (p.get("score") or 0)))


def _line_chart(weeks: list[str], series: list[tuple[str, list[int]]]) -> str:
    """Top movers over the last weeks: up to 3 lines, one y-axis, crosshair tooltip per week."""
    w, h, left, top, bottom = 640, 230, 32, 18, 30
    plot_w, plot_h = w - left - 16, h - top - bottom
    peak = max([v for _, vals in series for v in vals] + [4])
    step = max(1, -(-peak // 4))
    y_max = step * 4
    n = len(weeks)
    x = lambda i: left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)
    y = lambda v: top + plot_h - v / y_max * plot_h
    out = [f'<line class="grid" x1="{left}" x2="{w - 16}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
           f'<text class="ax" x="{left - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>'
           for v in range(0, y_max + 1, step)]
    out += [f'<text class="ax" x="{x(i):.1f}" y="{h - 8}" text-anchor="middle">W{_week_no(wk)}</text>'
            for i, wk in enumerate(weeks)]
    for k, (_, vals) in enumerate(series):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        if n > 1:
            out.append(f'<polyline class="ln s{k}" points="{pts}"/>')
        out.append(f'<circle class="pt s{k}" cx="{x(n - 1):.1f}" cy="{y(vals[-1]):.1f}" r="4"/>')
    if series:
        lead = series[0][1][-1]
        out.append(f'<text class="dl" x="{x(n - 1) - 8:.1f}" y="{y(lead) - 10:.1f}" text-anchor="end">{lead} this week</text>')
    for i, wk in enumerate(weeks):
        tip = f"Week {_week_no(wk)}: " + " · ".join(f"{_clip(_nice(name), 28)} {vals[i]}" for name, vals in series)
        slot = plot_w / max(n - 1, 1) if n > 1 else plot_w
        out.append(f'<g data-tip="{escape(tip)}" data-x="{x(i) / w * 100:.2f}" data-y="{top / h * 100:.2f}">'
                   f'<line class="xh" x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{top}" y2="{top + plot_h}"/>'
                   f'<rect class="hit" x="{x(i) - slot / 2:.1f}" y="{top}" width="{slot:.1f}" height="{plot_h}"/></g>')
    legend = "".join(f'<span class="lg s{k}"><i></i>{escape(_clip(_nice(name), 34))}</span>' for k, (name, _) in enumerate(series))
    return (f'<div class="legend">{legend}</div><div class="chart lc"><svg viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="Mentions per week for the top pain points">{"".join(out)}</svg><div class="tip" hidden></div></div>')


def dashboard(b: dict | None, history: list[dict], flash: str | None = None) -> str:
    """The Friday Brief: headline, numbers, sprint plan, ranked pain points, trends, sources, unresolved threads."""
    if not b:
        body = f"""<main class="fb">{_flash(flash)}
  <div class="fb-eyebrow">Friday brief</div><h1 class="fb-h1">Good morning, Sumit.</h1>
  <p class="fb-sub">There's no brief yet. Click <b>Run now</b> to collect this week's posts and write the first one.</p></main>"""
        return _page("Friday brief · DevPulse", body, active="brief", history=history, script=CLEAR_RUN_JS)

    week, metrics, prev, posts = b["week"], b["metrics"], b["prev"], b["posts"]
    is_latest = _is_latest(week, history)
    total = sum(m["mention_count"] for m in metrics)
    prev_total = sum(prev.values()) if prev is not None else None
    start = date.fromisoformat(week)
    period = f"{start.strftime('%b %d').upper()} – {(start + timedelta(days=6)).strftime('%b %d, %Y').upper()}".replace(" 0", " ")

    # ---- the summary: what programmers struggled with, the biggest problems, how many are still open ----
    if metrics:
        story = "Here's what programmers struggled with this week."
        named = [f"{_caps(m['pain_point'])} ({m['mention_count']})" for m in metrics[:3]]
        biggest = ", ".join(named[:-1]) + f" and {named[-1]}" if len(named) > 1 else named[0]
        open_mentions = sum(m.get("unresolved_count") or 0 for m in metrics)
        sub = (f"Developers raised {len(metrics)} problems across {total} mentions on Hacker News, Stack Overflow "
               f"and GitHub. The biggest were {biggest}. {open_mentions} of those mentions are still unresolved.")
    else:
        story, sub = "A quiet week.", "No relevant discussions were found for your topics."
    hour = datetime.now(IST).hour
    greeting = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 17 else "Good evening"
    heading = f"{greeting}, Sumit. {story}" if is_latest else f"Week {_week_no(week)}. {story}"

    prev_week = b.get("prev_week")
    compare = (f'<a class="btn" href="/history/{escape(prev_week)}">Compare to week {_week_no(prev_week)}</a>'
               if prev_week else "")

    # ---- numbers ----
    new_count = sum(1 for m in metrics if prev is not None and not prev.get(m["pain_point"]))
    if prev is not None:
        ups = [(m, m["mention_count"] - prev.get(m["pain_point"], 0)) for m in metrics]
        up_n = sum(1 for _, d in ups if d > 0)
        fastest = max(ups, key=lambda x: x[1], default=(None, 0))
        trend_v, trend_s = (f'{up_n} <small>of {len(metrics)}</small>',
                            f"Fastest: {escape(_clip(_nice(fastest[0]['pain_point']), 34))}" if fastest[0] and fastest[1] > 0
                            else "Nothing rose this week")
        ment_s = f"vs {prev_total} in week {_week_no(prev_week)}"
        pts_s = f"{new_count} new this week"
    else:
        trend_v, trend_s = "—", "Needs two weekly briefs to compare"
        ment_s, pts_s = "First week tracked", "First week tracked"
    unresolved = _unresolved(posts)
    kpis = f"""
<section class="kpis">
  <div class="kpi"><div class="l">Pain points tracked</div><div class="v">{len(metrics)} <small>{len({m.get('category') for m in metrics})} categories</small></div><div class="s">{pts_s}</div></div>
  <div class="kpi"><div class="l">Pain-point mentions</div><div class="v">{total} {_chg(total, prev_total) if prev_total else ''}</div><div class="s">{ment_s}</div></div>
  <div class="kpi"><div class="l">Topics trending up</div><div class="v">{trend_v}</div><div class="s">{trend_s}</div></div>
  <div class="kpi dark"><div class="l">Unresolved threads</div><div class="v">{len(unresolved)} <small class="mono">opportunities</small></div><div class="s">No accepted answer or fix yet</div></div>
</section>"""

    # ---- sprint plan + biggest opportunity ----
    secs = {s["key"]: s for s in b["sections"]}
    plan_items = ""
    if "sprint-actions" in secs:
        body_html = re.sub(r"\s*[(\[](?:\s*<a [^>]*>.*?</a>\s*,?\s*(?:and\s*)?)+[)\]]", "", secs["sprint-actions"]["body"], flags=re.S)
        for i, li in enumerate(re.findall(r"<li>(.*?)</li>", body_html, flags=re.S)[:3], 1):
            m = re.match(r"\s*(?:<p>)?\s*<strong>(.*?)</strong>\s*:?(.*)", li, flags=re.S)
            lead, rest = (m.group(1), m.group(2)) if m else ("", li)
            plan_items += (f'<li><span class="n">{i}</span><span>'
                           + (f"<b>{escape(_strip_tags(lead))}.</b> " if lead else "")
                           + f"{escape(_clip(_strip_tags(rest).strip(), 170))}</span></li>")
    plan = (f'<ol class="plan">{plan_items}</ol>' if plan_items
            else '<p class="sub">No sprint actions in this brief.</p>')
    opp_html = ""
    if "opportunities" in secs:
        body_html = re.sub(r"\s*[(\[](?:\s*<a [^>]*>.*?</a>\s*,?\s*(?:and\s*)?)+[)\]]", "", secs["opportunities"]["body"], flags=re.S)
        first = (re.findall(r"<li>(.*?)</li>", body_html, flags=re.S) or [body_html])[0]
        m = re.match(r"\s*(?:<p>)?\s*<strong>(.*?)</strong>\s*:?(.*)", first, flags=re.S)
        quote, detail = (_strip_tags(m.group(1)), _strip_tags(m.group(2))) if m else ("", _strip_tags(first))
        opp_html = (f'<div class="opp-q">“{escape(quote or _clip(detail, 80))}”</div>'
                    f'<p>{escape(_clip(detail.strip(), 190)) if quote else ""}</p>')
    elif unresolved:
        opp_html = f'<div class="opp-q">“{escape(_clip(unresolved[0].get("title") or "", 90))}”</div>'
    opp = f"""<aside class="opp"><div class="fb-eyebrow">Biggest opportunity</div>
  {opp_html or '<p>No unresolved problems stood out this week.</p>'}
  <a class="opp-link" href="/unresolved?week={escape(week)}">See {len(unresolved)} unresolved threads →</a></aside>"""
    base = f"/brief/{escape(week)}"
    readmore = "".join(f'<a class="tone-{s["tone"]}" href="{base}/{s["key"]}">{escape(s["label"])}</a>' for s in b["sections"])
    plan_row = f"""
<section class="row2">
  <div class="panel"><div class="panel-h"><h2>What to take into sprint planning</h2><span class="meta">From {len(posts)} threads</span></div>
    {plan}
    <div class="readmore"><span>Full brief:</span>{readmore}</div></div>
  {opp}
</section>"""

    # ---- ranked table ----
    weeks = b["weeks"]
    rows = ""
    for i, m in enumerate(metrics[:7], 1):
        name, n = m["pain_point"], m["mention_count"]
        last = prev.get(name, 0) if prev is not None else None
        vals = [b["series"].get(name, {}).get(wk, 0) for wk in weeks]
        href = _point_href(name, week)
        rows += (f'<tr data-href="{href}" data-vol="{n}" data-grow="{n - (last or 0)}">'
                 f'<td class="idx">{i:02d}</td>'
                 f'<td class="tn"><a href="{href}"><b>{escape(_nice(name))}</b></a><small>{escape(m.get("category") or "Other")}</small></td>'
                 f'<td class="num cur">{n}</td><td class="num">{"—" if last is None else last}</td>'
                 f'<td>{_chg(n, last)}</td><td>{_spark(vals) if len(weeks) > 1 else chr(8212)}</td>'
                 f'<td>{_cov(n, m.get("unresolved_count") or 0)}</td></tr>')
    ranked = f"""
<section class="panel" style="margin-top:14px">
  <div class="panel-h"><div><h2>Pain points, ranked</h2>
    <p class="sub">Mentions this week vs the previous brief, with {f'the shape of the last {len(weeks)} weeks' if len(weeks) > 1 else 'trend lines once a second brief exists'}. Click a row for its history and threads.</p></div>
    <div class="seg" role="group" aria-label="Sort"><button class="on" data-k="vol">By volume</button><button data-k="grow">By growth</button></div></div>
  <div class="rank-wrap"><table class="rank" id="rank">
    <thead><tr><th>#</th><th>Topic · category</th><th class="num">This wk</th><th class="num">Last wk</th><th>Change</th><th>{f"{len(weeks)} wk" if len(weeks) > 1 else "Trend"}</th><th>Status</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <a class="more" href="{base}/pain-points">View all {len(metrics)} pain points →</a>
</section>"""

    # ---- trend chart + sources ----
    movers = [(m["pain_point"], [b["series"].get(m["pain_point"], {}).get(wk, 0) for wk in weeks]) for m in metrics[:3]]
    chart_note = ('<p class="sub" style="margin-top:8px">Only one weekly brief so far: the lines fill in as each Friday run adds a week.</p>'
                  if len(weeks) < 2 else "")
    by_src: dict[str, int] = {}
    for p in posts:
        by_src[_src(p.get("source"))[0]] = by_src.get(_src(p.get("source"))[0], 0) + 1
    n_posts = len(posts) or 1
    src_rows = "".join(
        f'<div class="srow"><div><span>{escape(label)}</span><span class="mono">{c} · {round(c * 100 / n_posts)}%</span></div>'
        f'<i><u class="{_SRC.get(label.lower().replace(" ", ""), ("", "s-gh"))[1]}" style="width:{c * 100 / n_posts:.0f}%"></u></i></div>'
        for label, c in sorted(by_src.items(), key=lambda x: -x[1]))
    src_note = (f'<p class="sub">{escape(max(by_src, key=by_src.get))} contributed the most threads this week.</p>' if by_src else
                '<p class="sub">No threads stored for this week.</p>')
    trends = f"""
<section class="row2">
  <div class="panel"><h2 class="ph">{f'{len(weeks)}-week trend' if len(weeks) > 1 else 'Trend'}, top pain points</h2>{_line_chart(weeks, movers) if movers else ''}{chart_note}</div>
  <div class="panel"><h2 class="ph">Where it surfaced</h2>{src_rows}{src_note}</div>
</section>"""

    # ---- unresolved threads ----
    cards = "".join(_thread_card(t) for t in unresolved[:3])
    unres = f"""
<div class="sec-h"><div><h2>Unresolved</h2>
  <p class="sub">High-engagement threads where no reply solved the problem: candidate roadmap and content bets.</p></div>
  <a class="mono more" href="/unresolved?week={escape(week)}">{len(unresolved)} unresolved this week →</a></div>
<section class="ucards">{cards or '<div class="panel"><p class="sub">Every thread this week has an answer.</p></div>'}</section>"""

    # ---- keywords ----
    chips = "".join(f'<span class="kchip">{escape(k)}</span>' for t in b["topics"] if t.get("active") for k in t.get("keywords") or [])
    kw = f"""
<section class="kwp">
  <div><h2 class="ph">Monitored keywords</h2>
    <p class="sub">Searched on Hacker News, Stack Overflow and GitHub every run. Edit them on the Keywords page, no deploy needed.</p>
    <div class="kchips">{chips or '<span class="sub">No active keywords.</span>'}</div></div>
  <dl class="runs"><div><dt>This brief</dt><dd>{escape(_ist_label(b.get("created_at")))}</dd></div>
    <div><dt>Next run</dt><dd>{escape(_next_run_label())}</dd></div>
    <div><dt>Sources</dt><dd>HN · SO · GitHub</dd></div>
    <a class="btn" href="/topics">Manage keywords</a></dl>
</section>"""

    body = f"""
<main class="fb">
  {_flash(flash)}
  <header class="fb-head">
    <div><div class="fb-eyebrow">Friday brief · Week {_week_no(week)} · {period}</div>
      <h1 class="fb-h1">{escape(heading)}</h1><p class="fb-sub">{escape(sub)}</p></div>
    <div class="fb-actions"><div class="mono gen">Generated {escape(_ist_label(b.get("created_at")))}</div>
      <div class="fb-btns">{compare}{RUN_BUTTON}</div></div>
  </header>
  {kpis}{plan_row}{ranked}{trends}{unres}{kw}
</main>"""
    return _page(f"Week {_week_no(week)} · Friday brief", body, active="brief" if is_latest else "",
                 history=history, current_week=week, script=CLEAR_RUN_JS + RANK_JS + CHART_JS, hide_run=True)


RANK_JS = """<script>
(() => {
  const t = document.getElementById('rank'); if (!t) return;
  const body = t.tBodies[0];
  body.querySelectorAll('tr').forEach(r => r.addEventListener('click', e => { if (!e.target.closest('a')) location.href = r.dataset.href; }));
  document.querySelectorAll('.seg button').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.seg button').forEach(x => x.classList.toggle('on', x === b));
    [...body.rows].sort((a, c) => c.dataset[b.dataset.k] - a.dataset[b.dataset.k]).forEach(r => body.appendChild(r));
  }));
})();
</script>"""


def unresolved_page(b: dict | None, history: list[dict]) -> str:
    """Every unresolved thread for the week, most-discussed first."""
    if not b:
        return dashboard(None, history)
    items = _unresolved(b["posts"])
    cards = "".join(_thread_card(t) for t in items)
    body = f"""
<main class="fb">
  <div class="fb-eyebrow">Week {_week_no(b["week"])} · Unresolved</div>
  <h1 class="fb-h1">Unresolved</h1>
  <p class="fb-sub">{len(items)} threads this week where no reply solved the problem, most-discussed first. These are the gaps worth building for.</p>
  <section class="ucards" style="margin-top:24px">{cards or '<div class="panel"><p class="sub">Every thread this week has an answer.</p></div>'}</section>
</main>"""
    return _page(f"Unresolved · Week {_week_no(b['week'])}", body, active="unresolved", history=history,
                 current_week=b["week"])


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
    return _page(f"{title} · DevPulse", body, active="points", crumbs=crumbs, actions=RUN_BUTTON,
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
    return _page("Topics · DevPulse", body, active="topics",
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
    return _page("Health · DevPulse", body, active="health",
                 crumbs='<a href="/">Dev Community Pulse</a><span>/</span><b>Health</b>',
                 actions=RUN_BUTTON)
