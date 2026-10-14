"""Building Now projects table: frontend prototype on illustrative sample data.

The page is rendered once with the records from lib.building_data.load_projects() embedded as JSON; search,
filters, sorting, pagination, the watchlist, the blocker popover, the detail drawer and the share dialog all
run in the browser. No database or Gemini call is made, and the page says so wherever data is shown.
Prototype states for review: ?state=loading, ?state=empty, ?state=error.
"""
import json
from html import escape

from lib.views import _icon, _page

CSS = """<style>
  [hidden] { display: none !important; }   /* the drawer, dialog, chips and footer set display: flex */
  .bt { max-width: 1320px; margin: 0 auto; padding: var(--s8) var(--s6) var(--s12); }
  .bt-sample { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; padding: 10px 14px; border-radius: 10px;
               background: var(--warn-bg); color: var(--text); font-size: var(--fs-sm); border: 1px solid var(--border); }
  .bt-sample b { color: var(--warn-text); }
  .bt-sample nav { margin-left: auto; display: flex; gap: 10px; font-size: var(--fs-xs); }
  .bt-sample nav a { color: var(--text-2); text-decoration: underline; }
  .bt-sample nav a[aria-current] { font-weight: 600; text-decoration: none; }
  .bt-head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px; margin-top: var(--s6); }
  .bt-head > div:first-child { flex: 1 1 360px; min-width: 0; }
  .bt-head h1 { font-size: 26px; font-weight: 600; margin: 4px 0 4px; letter-spacing: -.01em; }
  .bt-head p { margin: 0; color: var(--text-3); }
  .bt-ctl { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  .bt-upd { font-family: var(--mono); font-size: 11px; color: var(--text-3); white-space: nowrap; }
  .bt select, .bt-search input { font: inherit; font-size: var(--fs-sm); color: var(--text); background: var(--surface);
               border: 1px solid var(--border); border-radius: 8px; height: 34px; padding: 0 10px; }
  .bt select:focus-visible, .bt button:focus-visible, .bt a:focus-visible, .bt-search input:focus-visible,
  .bt-drawer :focus-visible, .bt-modal :focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  .bt .btn { height: 34px; font-size: var(--fs-sm); padding: 0 12px; }
  .bt .seg button { padding: 5px 12px; }
  .bt-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: var(--s5); }
  .bt-m { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; min-width: 0; }
  .bt-m .l { font-size: var(--fs-xs); color: var(--text-3); font-weight: 500; }
  .bt-m .v { font-family: var(--display); font-size: 24px; font-weight: 600; margin-top: 2px; font-variant-numeric: tabular-nums; }
  .bt-m .d { font-size: var(--fs-xs); color: var(--text-3); line-height: 1.45; }
  .bt-panel { margin-top: var(--s4); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; min-width: 0; }
  .bt-tools { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 12px; border-bottom: 1px solid var(--border-soft); }
  .bt-search { position: relative; flex: 1 1 260px; min-width: 0; display: flex; }
  .bt-search svg.i { position: absolute; left: 10px; top: 9px; color: var(--text-4); }
  .bt-search input { width: 100%; padding: 0 30px 0 32px; }
  .bt-x { position: absolute; right: 4px; top: 4px; width: 26px; height: 26px; border: 0; background: none; color: var(--text-3);
          border-radius: 6px; cursor: pointer; font-size: 16px; }
  .bt-x:hover { background: var(--hover); color: var(--text); }
  .bt-more { display: contents; }
  .bt-ftoggle { display: none; }
  .bt-chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--border-soft); }
  .bt-chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--border); background: var(--chip);
             border-radius: 99px; padding: 2px 4px 2px 10px; font: inherit; font-size: var(--fs-xs); color: var(--text-2); cursor: pointer; }
  .bt-chip span { font-size: 14px; line-height: 1; padding: 0 4px; }
  .bt-link { border: 0; background: none; font: inherit; font-size: var(--fs-xs); color: var(--link); cursor: pointer; padding: 2px 4px; }
  .bt-link:hover { text-decoration: underline; }
  .bt-scroll { overflow: auto; max-height: 68vh; }
  table.bt-t { width: 100%; min-width: 1180px; border-collapse: separate; border-spacing: 0; font-size: var(--fs-sm); }
  .bt-t th { position: sticky; top: 0; z-index: 1; background: var(--panel); text-align: left; font-weight: 500;
             font-size: var(--fs-xs); color: var(--text-3); padding: 0; border-bottom: 1px solid var(--border); white-space: nowrap; }
  .bt-t th > span, .bt-t th > button { display: flex; align-items: center; gap: 4px; padding: 9px 10px; }
  .bt-t th > button { width: 100%; border: 0; background: none; font: inherit; color: inherit; cursor: pointer; text-align: left; }
  .bt-t th > button:hover { color: var(--text); }
  .bt-t th[aria-sort] > button { color: var(--text); }
  .bt-t th .ar { font-size: 10px; opacity: .8; }
  .bt-t td { padding: 9px 10px; border-bottom: 1px solid var(--border-soft); vertical-align: top; }
  .bt-t tbody tr:hover td { background: var(--hover); }
  .bt-t tbody tr:last-child td { border-bottom: 0; }
  .c-proj { width: 250px; } .c-builder { width: 120px; } .c-cat { width: 120px; } .c-tech { width: 200px; }
  .c-stage { width: 96px; } .c-focus { width: 220px; } .c-blk { width: 74px; } .c-act { width: 130px; }
  .c-obs { width: 104px; } .c-acts { width: 116px; }
  .bt-proj { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 10px; }
  .bt-av { width: 28px; height: 28px; border-radius: 7px; background: var(--accent-soft); color: var(--accent);
           display: grid; place-items: center; font-weight: 600; font-size: 12px; }
  .bt-name { border: 0; background: none; padding: 0; font: inherit; font-weight: 600; color: var(--text); text-align: left;
             cursor: pointer; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .bt-name:hover { color: var(--link); text-decoration: underline; }
  .bt-desc { color: var(--text-3); font-size: var(--fs-xs); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bt-trunc { display: block; max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  a.bt-trunc { color: var(--link); } a.bt-trunc:hover { text-decoration: underline; }
  .bt-none { color: var(--text-4); }
  .bt-badge { display: inline-block; max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; vertical-align: top;
              font-size: 11.5px; padding: 1px 8px; border-radius: 6px; background: var(--chip); color: var(--text-2); }
  .bt-tags { display: flex; flex-wrap: wrap; gap: 4px; }
  .bt-tag { border: 1px solid var(--border); background: var(--surface); color: var(--text-2); border-radius: 5px;
            font: inherit; font-family: var(--mono); font-size: 11px; padding: 0 6px; height: 21px; cursor: pointer; white-space: nowrap; }
  .bt-tag:hover, .bt-tag.on { border-color: var(--accent); color: var(--accent); }
  .bt-tag.more { font-family: inherit; }
  .bt-stage { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; font-weight: 500; padding: 1px 8px;
              border-radius: 6px; border: 1px solid var(--border); white-space: nowrap; }
  .bt-stage::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }
  .bt-stage.unknown { border-style: dashed; color: var(--text-3); }
  .bt-stage.unknown::before { background: transparent; border: 1px solid var(--text-4); }
  .bt-focus { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; color: var(--text-2); }
  .bt-count { border: 1px solid var(--border); background: var(--surface); border-radius: 6px; font: inherit;
              font-family: var(--mono); font-size: 12px; min-width: 30px; height: 24px; cursor: pointer; color: var(--text); }
  .bt-count:hover { border-color: var(--accent); }
  .bt-trend { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 500; white-space: nowrap; }
  .bt-trend i { font-style: normal; font-size: 10px; width: 16px; height: 16px; border-radius: 4px; display: grid; place-items: center; }
  .t-rising { color: var(--green); } .t-rising i { background: var(--ok-bg); }
  .t-stable { color: var(--text-2); } .t-stable i { background: var(--chip); }
  .t-declining { color: var(--red); } .t-declining i { background: var(--crit-bg); }
  .t-insufficient { color: var(--text-3); } .t-insufficient i { background: transparent; border: 1px dashed var(--text-4); }
  .bt-obs { white-space: nowrap; color: var(--text-2); font-variant-numeric: tabular-nums; }
  .bt-acts { display: flex; gap: 4px; }
  .bt-ib { width: 30px; height: 28px; border: 1px solid var(--border); background: var(--surface); border-radius: 7px; cursor: pointer;
           display: grid; place-items: center; color: var(--text-2); }
  .bt-ib:hover { border-color: var(--accent); color: var(--accent); }
  .bt-ib svg { width: 15px; height: 15px; stroke: currentColor; fill: none; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  .bt-ib[aria-pressed="true"] { color: var(--amber); border-color: var(--amber); }
  .bt-ib[aria-pressed="true"] svg { fill: currentColor; }
  .bt-foot { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 10px 12px; border-top: 1px solid var(--border-soft);
             font-size: var(--fs-xs); color: var(--text-3); }
  .bt-foot .sp { flex: 1; }
  .bt-foot select { height: 28px; font-size: var(--fs-xs); }
  .bt-foot .btn { height: 28px; font-size: var(--fs-xs); }
  .bt-state { padding: 40px 20px; text-align: center; color: var(--text-3); }
  .bt-state b { display: block; color: var(--text); font-size: var(--fs-lg); margin-bottom: 4px; }
  .bt-state .btn { margin-top: 12px; }
  .bt-state.err b { color: var(--red); }
  .sk { display: block; height: 12px; border-radius: 4px; background: var(--chip); animation: bt-pulse 1.2s ease-in-out infinite; }
  @keyframes bt-pulse { 50% { opacity: .45; } }
  @media (prefers-reduced-motion: reduce) { .sk { animation: none; } .bt-drawer { transition: none; } }
  .bt-pop { position: absolute; z-index: 30; width: min(340px, calc(100vw - 32px)); background: var(--surface); border: 1px solid var(--border);
            border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,.14); padding: 12px; font-size: var(--fs-sm); }
  .bt-pop h3 { margin: 0 0 8px; font-size: var(--fs-sm); }
  .bt-bl { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
  .bt-bl li { border-top: 1px solid var(--border-soft); padding-top: 8px; }
  .bt-bl li:first-child { border-top: 0; padding-top: 0; }
  .bt-bl small { display: block; color: var(--text-3); font-size: var(--fs-xs); }
  .bt-ev { display: inline-block; font-size: 10.5px; font-weight: 600; border-radius: 4px; padding: 0 6px; margin-left: 4px; }
  .bt-ev.explicit { background: var(--ok-bg); color: var(--green); }
  .bt-ev.inferred { background: var(--warn-bg); color: var(--warn-text); }
  .bt-ov { position: fixed; inset: 0; z-index: 40; background: rgba(0,0,0,.4); }
  .bt-drawer { position: fixed; z-index: 41; top: 0; right: 0; bottom: 0; width: min(560px, 100vw); background: var(--surface);
               border-left: 1px solid var(--border); overflow-y: auto; padding: 20px 22px 32px; display: flex; flex-direction: column; gap: 16px; }
  .bt-dh { display: flex; gap: 12px; align-items: flex-start; }
  .bt-dh h2 { margin: 0; font-size: 19px; line-height: 1.3; flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .bt-dl { display: grid; grid-template-columns: 130px minmax(0, 1fr); gap: 6px 12px; margin: 0; font-size: var(--fs-sm); }
  .bt-dl dt { color: var(--text-3); } .bt-dl dd { margin: 0; overflow-wrap: anywhere; }
  .bt-sec h3 { margin: 0 0 8px; font-size: var(--fs-md); }
  .bt-tl { list-style: none; margin: 0; padding: 0; border-left: 2px solid var(--border); }
  .bt-tl li { position: relative; padding: 0 0 12px 16px; font-size: var(--fs-sm); }
  .bt-tl li::before { content: ""; position: absolute; left: -6px; top: 5px; width: 10px; height: 10px; border-radius: 50%;
                      background: var(--surface); border: 2px solid var(--accent); }
  .bt-tl small { display: block; color: var(--text-3); font-size: var(--fs-xs); }
  .bt-tl q { display: block; color: var(--text-2); font-size: var(--fs-xs); margin-top: 2px; }
  .bt-modal { position: fixed; z-index: 41; left: 50%; top: 50%; transform: translate(-50%, -50%); width: min(480px, calc(100vw - 32px));
              background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px;
              display: flex; flex-direction: column; gap: 10px; max-height: calc(100vh - 32px); overflow-y: auto; }
  .bt-modal h2 { margin: 0; font-size: 17px; }
  .bt-modal textarea { font: inherit; font-size: var(--fs-sm); width: 100%; min-height: 130px; resize: vertical; padding: 8px 10px;
                       border: 1px solid var(--border); border-radius: 8px; background: var(--panel); color: var(--text); }
  .bt-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .bt-fb { font-size: var(--fs-xs); } .bt-fb.ok { color: var(--green); } .bt-fb.bad { color: var(--red); }
  @media (max-width: 1000px) { .bt-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @media (max-width: 760px) {
    .bt { padding: var(--s5) var(--s4) var(--s10); }
    .bt-ftoggle { display: inline-flex; }
    .bt-more { display: none; }
    .bt-more.open { display: flex; flex-wrap: wrap; gap: 8px; width: 100%; }
    .bt-more.open select { flex: 1 1 140px; }
    .bt-scroll { max-height: none; overflow: visible; }
    table.bt-t { min-width: 0; }
    .bt-t thead { display: none; }
    .bt-t tbody, .bt-t tr { display: block; }
    .bt-t tr { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px 10px; padding: 12px; border-bottom: 1px solid var(--border-soft); }
    .bt-t tbody tr:hover td { background: none; }
    .bt-t td { display: block; padding: 0; border: 0; }
    .bt-t td.c-proj { grid-column: 1 / -1; }
    .bt-t td.hm { display: none; }
    .bt-t td.c-acts { grid-column: 2; grid-row: 2 / span 2; align-self: center; }
    .bt-t td[data-label]::before { content: attr(data-label) " · "; color: var(--text-4); font-size: var(--fs-xs); }
    .bt-desc { white-space: normal; }
  }
  @media (max-width: 460px) { .bt-metrics { grid-template-columns: minmax(0, 1fr); } .bt-dl { grid-template-columns: minmax(0, 1fr); } }
</style>"""

JS = r"""<script>
(() => {
  const root = document.getElementById('bt'); if (!root) return;
  const RAW = JSON.parse(document.getElementById('bt-data').textContent);
  const MODE = root.dataset.state || '';
  const DATA = MODE === 'empty' ? { ...RAW, projects: [] } : RAW;
  const AS_OF = new Date(DATA.asOf + 'T23:59:59Z');
  const STAGES = { idea: 'Idea', prototype: 'Prototype', mvp: 'MVP', beta: 'Beta', launched: 'Launched', unknown: 'Unknown' };
  const STAGE_ORDER = ['idea', 'prototype', 'mvp', 'beta', 'launched', 'unknown'];
  const ACT = { rising: ['Rising', '▲'], stable: ['Stable', '■'], declining: ['Declining', '▼'], insufficient: ['Insufficient data', '?'] };
  const ACT_ORDER = ['rising', 'stable', 'declining', 'insufficient'];
  const EVENTS = { project_announcement: 'Project announcement', product_launch: 'Product launch', feature_update: 'Feature update',
                   public_demo: 'Public demo', repository_update: 'Repository update', technical_question: 'Technical question',
                   reported_blocker: 'Reported blocker' };
  const BLK = { yes: 'Has blockers', none: 'None reported', unknown: 'No blocker data' };
  const SVG = {
    eye: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><circle cx="8" cy="8" r="2"/></svg>',
    star: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6z"/></svg>',
    share: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="12" cy="3.5" r="1.8"/><circle cx="4" cy="8" r="1.8"/><circle cx="12" cy="12.5" r="1.8"/><path d="M5.6 7.1l4.8-2.7M5.6 8.9l4.8 2.7"/></svg>',
  };

  const st = { q: '', category: '', tech: '', stage: '', activity: '', blockers: '', days: 30, view: 'all',
               sort: 'lastObserved', dir: 'desc', page: 1, size: 10, loadedAt: new Date(),
               watched: new Set(DATA.projects.filter(p => p.isWatched).map(p => p.id)) };
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = iso => iso ? new Date(iso + (iso.length === 10 ? 'T00:00:00Z' : '')).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }) : '—';
  const daysAgo = iso => Math.floor((AS_OF - new Date(iso + 'T00:00:00Z')) / 86400000);
  const ago = iso => { const d = daysAgo(iso); return d <= 0 ? 'Today' : d === 1 ? 'Yesterday' : d < 30 ? `${d} days ago` : fmt(iso); };
  const bcount = p => p.blockers == null ? null : p.blockers.length;
  const byId = id => DATA.projects.find(p => p.id === id);

  // ---------- filtering, sorting, metrics ----------
  const inRange = p => st.days === 0 || daysAgo(p.lastObservedAt) < st.days;
  const matches = p => {
    if (!inRange(p) || (st.view === 'watch' && !st.watched.has(p.id))) return false;
    if (st.category && p.category !== st.category) return false;
    if (st.tech && !p.techStack.includes(st.tech)) return false;
    if (st.stage && p.buildStage !== st.stage) return false;
    if (st.activity && p.activityTrend !== st.activity) return false;
    const b = bcount(p);
    if (st.blockers === 'yes' && !(b > 0)) return false;
    if (st.blockers === 'none' && b !== 0) return false;
    if (st.blockers === 'unknown' && b !== null) return false;
    if (st.q) {
      const hay = [p.name, p.description, p.builderName, p.builderUsername, ...p.techStack].join(' ').toLowerCase();
      if (!st.q.toLowerCase().split(/\s+/).filter(Boolean).every(w => hay.includes(w))) return false;
    }
    return true;
  };
  const KEYS = { name: p => p.name.toLowerCase(), category: p => p.category.toLowerCase(),
                 stage: p => p.buildStage === 'unknown' ? null : STAGE_ORDER.indexOf(p.buildStage),
                 lastObserved: p => p.lastObservedAt, blockers: bcount, activity: p => ACT_ORDER.indexOf(p.activityTrend) };
  const sorted = rows => {
    const key = KEYS[st.sort], d = st.dir === 'asc' ? 1 : -1;
    return rows.slice().sort((a, b) => {
      const x = key(a), y = key(b);
      if (x == null || y == null) return x == null && y == null ? a.name.localeCompare(b.name) : x == null ? 1 : -1;  // missing last
      return (x < y ? -1 : x > y ? 1 : 0) * d || a.name.localeCompare(b.name);
    });
  };
  const period = () => st.days === 0 ? 'all sample data' : `last ${st.days} days`;
  const metrics = () => {
    const rows = DATA.projects.filter(inRange);
    const builders = new Set(rows.map(p => p.builderUsername).filter(Boolean));
    const rising = {};
    rows.filter(p => p.activityTrend === 'rising').forEach(p => p.techStack.forEach(t => rising[t] = (rising[t] || 0) + 1));
    const trending = Object.keys(rising).filter(t => rising[t] >= 2).sort();
    const known = rows.filter(p => p.blockers != null);
    const blockers = known.reduce((n, p) => n + p.blockers.length, 0);
    return [
      ['Projects discovered', rows.length, `Distinct projects with evidence in the ${period()}.`],
      ['Public builders', builders.size, `Distinct public handles. ${rows.length - rows.filter(p => p.builderUsername).length} project(s) show no handle.`],
      ['Trending technologies', trending.length, trending.length ? `Used by 2+ rising projects: ${trending.join(', ')}.` : 'No technology is used by 2+ rising projects.'],
      ['Reported blockers', blockers, `Across ${known.length} project(s) with blocker data; ${rows.length - known.length} have none recorded.`],
    ];
  };

  // ---------- rendering ----------
  const trend = t => `<span class="bt-trend t-${t}"><i aria-hidden="true">${ACT[t][1]}</i>${ACT[t][0]}</span>`;
  const stage = s => `<span class="bt-stage ${s}"${s === 'unknown' ? ' title="The source doesn’t state a build stage"' : ''}>${STAGES[s]}</span>`;
  const tags = p => {
    const shown = p.techStack.slice(0, 3), rest = p.techStack.slice(3);
    if (!p.techStack.length) return '<span class="bt-none">—</span>';
    return '<div class="bt-tags">' + shown.map(t => `<button type="button" class="bt-tag${st.tech === t ? ' on' : ''}" data-tech="${esc(t)}" title="Filter by ${esc(t)}">${esc(t)}</button>`).join('')
      + (rest.length ? `<button type="button" class="bt-tag more" data-more="${esc(p.id)}" title="${esc(rest.join(', '))}" aria-label="Show ${rest.length} more: ${esc(rest.join(', '))}">+${rest.length}</button>` : '') + '</div>';
  };
  const builder = p => {
    const label = p.builderUsername ? '@' + p.builderUsername : p.builderName;
    if (!label) return '<span class="bt-none" title="The source doesn’t show a builder">—</span>';
    const title = esc([p.builderName, p.builderUsername && '@' + p.builderUsername].filter(Boolean).join(' · '));
    return p.builderProfileUrl ? `<a class="bt-trunc" href="${esc(p.builderProfileUrl)}" target="_blank" rel="noopener noreferrer" title="${title}">${esc(label)}</a>`
                               : `<span class="bt-trunc" title="${title}">${esc(label)}</span>`;
  };
  const row = p => {
    const b = bcount(p), saved = st.watched.has(p.id);
    return `<tr>
      <td class="c-proj"><div class="bt-proj"><span class="bt-av" aria-hidden="true">${esc(p.name.trim()[0] || '?').toUpperCase()}</span>
        <div style="min-width:0"><button type="button" class="bt-name" data-open="${esc(p.id)}">${esc(p.name)}</button>
        <div class="bt-desc" title="${esc(p.description)}">${esc(p.description)}</div></div></div></td>
      <td class="c-builder hm">${builder(p)}</td>
      <td class="c-cat" data-label="Category"><span class="bt-badge" title="${esc(p.category)}">${esc(p.category)}</span></td>
      <td class="c-tech hm">${tags(p)}</td>
      <td class="c-stage hm">${stage(p.buildStage)}</td>
      <td class="c-focus hm">${p.currentFocus ? `<span class="bt-focus" title="${esc(p.currentFocus)}">${esc(p.currentFocus)}</span>` : '<span class="bt-none" title="No focus stated in the source">—</span>'}</td>
      <td class="c-blk hm">${b == null ? '<span class="bt-none" title="No blocker information in the source">—</span>'
        : `<button type="button" class="bt-count" data-blockers="${esc(p.id)}" aria-label="${b} reported blocker${b === 1 ? '' : 's'}: show details">${b}</button>`}</td>
      <td class="c-act" data-label="Activity">${trend(p.activityTrend)}</td>
      <td class="c-obs" data-label="Last observed"><time class="bt-obs" datetime="${esc(p.lastObservedAt)}" title="Evidence last observed ${fmt(p.lastObservedAt)}">${ago(p.lastObservedAt)}</time></td>
      <td class="c-acts"><div class="bt-acts">
        <button type="button" class="bt-ib" data-open="${esc(p.id)}" aria-label="View details for ${esc(p.name)}" title="View details">${SVG.eye}</button>
        <button type="button" class="bt-ib" data-watch="${esc(p.id)}" aria-pressed="${saved}" aria-label="${saved ? 'Remove from' : 'Add to'} watchlist: ${esc(p.name)}" title="${saved ? 'Remove from watchlist' : 'Add to watchlist'}">${SVG.star}</button>
        <button type="button" class="bt-ib" data-share="${esc(p.id)}" aria-label="Share ${esc(p.name)}" title="Share">${SVG.share}</button></div></td>
    </tr>`;
  };
  const skeletonRows = n => Array.from({ length: n }, () => '<tr>' + Array.from({ length: 10 }, (_, i) =>
    `<td${i === 0 ? ' class="c-proj"' : ''}><span class="sk" style="width:${[80, 60, 70, 75, 55, 85, 30, 60, 55, 70][i]}%"></span></td>`).join('') + '</tr>').join('');

  const renderMetrics = () => {
    $('#bt-metrics').innerHTML = (MODE === 'loading' ? [0, 1, 2, 3].map(() =>
      '<div class="bt-m"><span class="sk" style="width:50%"></span><span class="sk" style="width:30%;height:22px;margin:8px 0"></span><span class="sk" style="width:80%"></span></div>')
      : metrics().map(([l, v, d]) => `<div class="bt-m"><div class="l">${l}</div><div class="v">${v}</div><div class="d">${esc(d)}</div></div>`)).join('');
  };
  const chips = () => {
    const c = [];
    if (st.q) c.push(['q', `Search: “${st.q}”`]);
    if (st.category) c.push(['category', st.category]);
    if (st.tech) c.push(['tech', st.tech]);
    if (st.stage) c.push(['stage', 'Stage: ' + STAGES[st.stage]]);
    if (st.activity) c.push(['activity', ACT[st.activity][0]]);
    if (st.blockers) c.push(['blockers', BLK[st.blockers]]);
    if (st.view === 'watch') c.push(['view', 'My watchlist']);
    const box = $('#bt-chips');
    box.hidden = !c.length;
    box.innerHTML = c.map(([k, l]) => `<button type="button" class="bt-chip" data-clear="${k}" aria-label="Remove filter ${esc(l)}">${esc(l)}<span aria-hidden="true">×</span></button>`).join('')
      + (c.length ? '<button type="button" class="bt-link" data-clear="all">Clear filters</button>' : '');
  };
  const render = () => {
    renderMetrics();
    chips();
    $('#bt-wcount').textContent = st.watched.size;
    $('#bt-upd').textContent = MODE === 'loading' ? 'Loading…' : `Sample data as of ${fmt(DATA.asOf)} · loaded ${st.loadedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    document.querySelectorAll('.bt-t th[data-sort]').forEach(th => {
      const on = th.dataset.sort === st.sort;
      if (on) th.setAttribute('aria-sort', st.dir === 'asc' ? 'ascending' : 'descending'); else th.removeAttribute('aria-sort');
      th.querySelector('.ar').textContent = on ? (st.dir === 'asc' ? '↑' : '↓') : '';
    });
    const body = $('#bt-body'), state = $('#bt-state'), foot = $('#bt-foot');
    if (MODE === 'loading') { body.innerHTML = skeletonRows(6); state.hidden = true; foot.hidden = true; return; }
    if (MODE === 'error') {
      body.innerHTML = ''; foot.hidden = true; state.hidden = false; state.className = 'bt-state err';
      state.innerHTML = '<b>Projects couldn’t load</b>The data source didn’t respond. Previously loaded data is kept when this happens in the live version.<br><a class="btn" href="?">Try again</a>';
      return;
    }
    if (!DATA.projects.length) {
      body.innerHTML = ''; foot.hidden = true; state.hidden = false; state.className = 'bt-state';
      state.innerHTML = '<b>No projects yet</b>Projects appear here once public build discussions have been collected and classified.';
      return;
    }
    const rows = sorted(DATA.projects.filter(matches));
    const pages = Math.max(1, Math.ceil(rows.length / st.size));
    st.page = Math.min(st.page, pages);
    const start = (st.page - 1) * st.size, slice = rows.slice(start, start + st.size);
    body.innerHTML = slice.map(row).join('');
    state.hidden = !!rows.length; state.className = 'bt-state';
    if (!rows.length) state.innerHTML = `<b>No projects match</b>Nothing in the ${period()} matches these filters.<br><button type="button" class="btn" data-clear="all">Clear filters</button>`;
    foot.hidden = !rows.length;
    $('#bt-range').textContent = rows.length ? `Showing ${start + 1}–${start + slice.length} of ${rows.length} matching project${rows.length === 1 ? '' : 's'}` : '';
    $('#bt-pageno').textContent = `Page ${st.page} of ${pages}`;
    $('#bt-prev').disabled = st.page <= 1; $('#bt-next').disabled = st.page >= pages;
  };

  // ---------- popover, drawer, share dialog ----------
  const pop = $('#bt-pop');
  let popFor = null, lastFocus = null;
  const closePop = () => { pop.hidden = true; popFor = null; };
  const openPop = btn => {
    const p = byId(btn.dataset.blockers);
    if (popFor === btn) return closePop();
    popFor = btn;
    pop.innerHTML = `<h3>Reported blockers · ${esc(p.name)}</h3><ul class="bt-bl">` + p.blockers.map(b =>
      `<li><b>${esc(b.title)}</b><span class="bt-ev ${b.evidenceType}">${b.evidenceType === 'explicit' ? 'Explicitly reported' : 'AI-inferred'}</span>
        <small>${esc(b.category)}${b.excerpt ? ` · “${esc(b.excerpt)}”` : ''}</small></li>`).join('') + '</ul>'
      + (p.blockers.length ? '' : '<p class="sub">The source was checked and no blockers were reported.</p>');
    pop.hidden = false;
    const r = btn.getBoundingClientRect(), w = pop.offsetWidth;
    pop.style.top = (r.bottom + window.scrollY + 6) + 'px';
    pop.style.left = Math.max(16, Math.min(r.left + window.scrollX - w + r.width, document.documentElement.clientWidth - w - 16)) + 'px';
  };
  const ov = $('#bt-ov'), drawer = $('#bt-drawer'), modal = $('#bt-modal');
  const closeAll = () => {
    ov.hidden = true; drawer.hidden = true; modal.hidden = true;
    document.body.style.overflow = '';
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
  };
  const openLayer = el => { if (ov.hidden) lastFocus = document.activeElement; closePop(); ov.hidden = false; el.hidden = false; document.body.style.overflow = 'hidden';
    (el.querySelector('[data-close]') || el).focus(); };
  const link = (url, label) => url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" class="bt-trunc" style="color:var(--link)">${esc(label)} ↗</a>` : '<span class="bt-none">Not available</span>';
  const openDrawer = id => {
    const p = byId(id), saved = st.watched.has(p.id);
    drawer.innerHTML = `
      <div class="bt-dh"><span class="bt-av" aria-hidden="true">${esc(p.name.trim()[0] || '?').toUpperCase()}</span><h2 id="bt-dt">${esc(p.name)}</h2>
        <button type="button" class="bt-x" style="position:static" data-close aria-label="Close details">×</button></div>
      <p style="margin:0;color:var(--text-2)">${esc(p.description)}</p>
      <div class="bt-row"><button type="button" class="btn${saved ? '' : ' btn-primary'}" data-watch="${esc(p.id)}" aria-pressed="${saved}">${saved ? 'Remove from watchlist' : 'Add to watchlist'}</button>
        <button type="button" class="btn" data-share="${esc(p.id)}">Share</button>
        ${p.sourceUrl ? `<a class="btn" href="${esc(p.sourceUrl)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>` : '<button type="button" class="btn" disabled title="No source link recorded">Open source</button>'}</div>
      <dl class="bt-dl">
        <dt>Builder</dt><dd>${builder(p)}</dd>
        <dt>Category</dt><dd>${esc(p.category)}</dd>
        <dt>Build stage</dt><dd>${stage(p.buildStage)}</dd>
        <dt>Activity</dt><dd>${trend(p.activityTrend)}${p.activityTrend === 'insufficient' ? ' <small class="bt-none">Not enough comparable observations yet.</small>' : ''}</dd>
        <dt>Current focus</dt><dd>${p.currentFocus ? esc(p.currentFocus) : '<span class="bt-none">Not stated in the source</span>'}</dd>
        <dt>First seen</dt><dd>${fmt(p.firstSeenAt)} <small class="bt-none">(first collected)</small></dd>
        <dt>Last observed</dt><dd>${fmt(p.lastObservedAt)} <small class="bt-none">(latest public evidence, not when work happened)</small></dd>
        <dt>Project site</dt><dd>${link(p.projectUrl, 'Project site')}</dd>
        <dt>Repository</dt><dd>${link(p.repositoryUrl, 'Repository')}</dd>
        <dt>Source</dt><dd>${link(p.sourceUrl, p.sourcePlatform || 'Source')}</dd>
      </dl>
      <section class="bt-sec"><h3>Tech stack</h3>${p.techStack.length ? '<div class="bt-tags">' + p.techStack.map(t => `<span class="bt-tag" style="cursor:default">${esc(t)}</span>`).join('') + '</div>' : '<span class="bt-none">No technologies recorded</span>'}</section>
      <section class="bt-sec"><h3>Reported blockers</h3>${p.blockers == null ? '<span class="bt-none">No blocker information in the source.</span>'
        : p.blockers.length ? '<ul class="bt-bl">' + p.blockers.map(b => `<li><b>${esc(b.title)}</b><span class="bt-ev ${b.evidenceType}">${b.evidenceType === 'explicit' ? 'Explicitly reported' : 'AI-inferred'}</span><small>${esc(b.category)}${b.excerpt ? ` · “${esc(b.excerpt)}”` : ''}</small></li>`).join('') + '</ul>'
        : '<span class="bt-none">Checked: none reported.</span>'}</section>
      <section class="bt-sec"><h3>Activity timeline</h3><ol class="bt-tl">${p.timeline.map(e => `<li><b>${esc(EVENTS[e.type] || 'Observation')}</b> · ${esc(e.title)}
        <small>${e.publishedAt ? 'Posted ' + fmt(e.publishedAt) + ' · ' : 'Post date unknown · '}collected ${fmt(e.collectedAt)}${e.sourceUrl ? ` · <a href="${esc(e.sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:var(--link)">source ↗</a>` : ''}</small>
        ${e.excerpt ? `<q>${esc(e.excerpt)}</q>` : ''}</li>`).join('')}</ol></section>
      <p class="sub">Sample data. Links point to example.com placeholders, not real public posts.</p>`;
    openLayer(drawer);
  };
  const copy = async (text, out) => {
    try { await navigator.clipboard.writeText(text); out.textContent = 'Copied to clipboard.'; out.className = 'bt-fb ok'; }
    catch (e) { out.textContent = 'Couldn’t copy. Select the text above and copy it manually.'; out.className = 'bt-fb bad'; }
  };
  const openShare = id => {
    const p = byId(id);
    const summary = [`${p.name}: ${p.description}`, `Category: ${p.category} · Stage: ${STAGES[p.buildStage]} · Activity: ${ACT[p.activityTrend][0]}`,
      p.currentFocus && `Current focus: ${p.currentFocus}`, p.techStack.length && `Tech: ${p.techStack.join(', ')}`,
      p.sourceUrl ? `Source: ${p.sourceUrl}` : 'Source: not available', '(Sample data from the DevvIT Building Now prototype)'].filter(Boolean).join('\n');
    modal.innerHTML = `<div class="bt-dh"><h2 id="bt-mt">Share ${esc(p.name)}</h2><button type="button" class="bt-x" style="position:static" data-close aria-label="Close">×</button></div>
      <label class="sub" for="bt-sum">Summary</label><textarea id="bt-sum" readonly>${esc(summary)}</textarea>
      <div class="bt-row"><button type="button" class="btn btn-primary" id="bt-copy-sum">Copy summary</button>
        <button type="button" class="btn" disabled title="Share links aren’t available for sample data">Copy link</button></div>
      <p class="bt-fb" id="bt-copy-fb" role="status"></p>
      <p class="sub">No share link exists for this project: the prototype doesn’t publish anything. Copy the summary instead.</p>`;
    openLayer(modal);
    $('#bt-copy-sum').addEventListener('click', () => copy(summary, $('#bt-copy-fb')));
  };
  const toggleWatch = id => {
    st.watched.has(id) ? st.watched.delete(id) : st.watched.add(id);
    render();
    if (!drawer.hidden) openDrawer(id);
  };

  // ---------- events ----------
  const reset = () => { st.page = 1; render(); };
  const setFilter = (k, v) => { st[k] = v; const el = document.getElementById('bt-f-' + k); if (el) el.value = v; reset(); };
  let typing;
  $('#bt-q').addEventListener('input', e => {
    $('#bt-qx').hidden = !e.target.value;
    clearTimeout(typing); typing = setTimeout(() => { st.q = e.target.value.trim(); reset(); }, 150);
  });
  $('#bt-qx').addEventListener('click', () => { $('#bt-q').value = ''; $('#bt-qx').hidden = true; st.q = ''; reset(); $('#bt-q').focus(); });
  ['category', 'tech', 'stage', 'activity', 'blockers'].forEach(k => document.getElementById('bt-f-' + k).addEventListener('change', e => setFilter(k, e.target.value)));
  $('#bt-days').addEventListener('change', e => { st.days = +e.target.value; reset(); });
  $('#bt-size').addEventListener('change', e => { st.size = +e.target.value; reset(); });
  $('#bt-prev').addEventListener('click', () => { st.page--; render(); });
  $('#bt-next').addEventListener('click', () => { st.page++; render(); });
  $('#bt-view').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    st.view = b.dataset.view;
    document.querySelectorAll('#bt-view button').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b); });
    reset();
  });
  $('#bt-refresh').addEventListener('click', () => { st.loadedAt = new Date(); render(); });
  $('#bt-ftoggle').addEventListener('click', e => {
    const open = $('#bt-more').classList.toggle('open'); e.currentTarget.setAttribute('aria-expanded', open);
  });
  document.querySelectorAll('.bt-t th[data-sort] button').forEach(b => b.addEventListener('click', () => {
    const k = b.parentElement.dataset.sort;
    st.dir = st.sort === k ? (st.dir === 'asc' ? 'desc' : 'asc') : (k === 'lastObserved' || k === 'blockers' ? 'desc' : 'asc');
    st.sort = k; reset();
  }));
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-open],[data-watch],[data-share],[data-blockers],[data-tech],[data-more],[data-clear],[data-close]');
    if (!t) { if (!pop.hidden && !e.target.closest('#bt-pop')) closePop(); if (e.target === ov) closeAll(); return; }
    if (!t.dataset.blockers) closePop();
    if (t.dataset.open) openDrawer(t.dataset.open);
    else if (t.dataset.watch) toggleWatch(t.dataset.watch);
    else if (t.dataset.share) { closeAll(); openShare(t.dataset.share); }
    else if (t.dataset.blockers) openPop(t);
    else if (t.dataset.tech) setFilter('tech', st.tech === t.dataset.tech ? '' : t.dataset.tech);
    else if (t.dataset.more) {
      const p = byId(t.dataset.more);
      t.parentElement.innerHTML = p.techStack.map(x => `<button type="button" class="bt-tag${st.tech === x ? ' on' : ''}" data-tech="${esc(x)}" title="Filter by ${esc(x)}">${esc(x)}</button>`).join('');
    }
    else if (t.dataset.clear) {
      const k = t.dataset.clear;
      if (k === 'all' || k === 'q') { st.q = ''; $('#bt-q').value = ''; $('#bt-qx').hidden = true; }
      if (k === 'view' || k === 'all') { st.view = 'all'; document.querySelectorAll('#bt-view button').forEach(x => { x.classList.toggle('on', x.dataset.view === 'all'); x.setAttribute('aria-pressed', x.dataset.view === 'all'); }); }
      ['category', 'tech', 'stage', 'activity', 'blockers'].forEach(f => { if (k === 'all' || k === f) { st[f] = ''; document.getElementById('bt-f-' + f).value = ''; } });
      reset();
    }
    else if (t.hasAttribute('data-close')) closeAll();
  });
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (!pop.hidden) { const b = popFor; closePop(); b && b.focus(); } else if (!ov.hidden) closeAll();
  });
  window.addEventListener('resize', closePop);
  render();
})();
</script>"""


def _options(values: list[tuple[str, str]], label: str) -> str:
    return f'<option value="">{escape(label)}</option>' + "".join(
        f'<option value="{escape(v)}">{escape(t)}</option>' for v, t in values)


def table_page(data: dict, state: str = "") -> str:
    projects = data["projects"]
    cats = sorted({p["category"] for p in projects})
    techs = sorted({t for p in projects for t in p["techStack"]}, key=str.lower)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    states = "".join(f'<a href="{href}"{" aria-current=page" if state == key else ""}>{label}</a>'
                     for key, href, label in (("", "?", "Normal"), ("loading", "?state=loading", "Loading"),
                                              ("empty", "?state=empty", "Empty"), ("error", "?state=error", "Error")))

    def th(key: str, label: str, cls: str) -> str:
        if not key:
            return f'<th scope="col" class="{cls}"><span>{label}</span></th>'
        return f'<th scope="col" class="{cls}" data-sort="{key}"><button type="button">{label}<span class="ar" aria-hidden="true"></span></button></th>'

    body = f"""
<main class="bt" id="bt" data-state="{escape(state)}">
  <div class="bt-sample" role="note"><span><b>Prototype · sample data.</b> These projects, builders and numbers are illustrative,
    not live DevvIT data. Links go to example.com placeholders.</span>
    <nav aria-label="Prototype states">{states}</nav></div>
  <header class="bt-head">
    <div><div class="fb-eyebrow">Building Now</div><h1>Building Now</h1>
      <p>Track publicly shared developer projects, technologies, and build activity.</p></div>
    <div class="bt-ctl">
      <span class="bt-upd" id="bt-upd" role="status"></span>
      <label class="sr" for="bt-days">Date range</label>
      <select id="bt-days"><option value="7">Last 7 days</option><option value="30" selected>Last 30 days</option>
        <option value="90">Last 90 days</option><option value="0">All sample data</option></select>
      <div class="seg" id="bt-view" role="group" aria-label="View">
        <button type="button" class="on" data-view="all" aria-pressed="true">All projects</button>
        <button type="button" data-view="watch" aria-pressed="false">My watchlist (<span id="bt-wcount">0</span>)</button></div>
      <button type="button" class="btn" id="bt-refresh" title="Reloads the sample data">Refresh</button>
    </div>
  </header>
  <section class="bt-metrics" id="bt-metrics" aria-label="Summary"></section>
  <section class="bt-panel" aria-label="Projects">
    <div class="bt-tools">
      <div class="bt-search">{_icon("search")}
        <label class="sr" for="bt-q">Search projects</label>
        <input id="bt-q" type="search" placeholder="Search projects, technologies or builders..." autocomplete="off">
        <button type="button" class="bt-x" id="bt-qx" hidden aria-label="Clear search">×</button></div>
      <label class="sr" for="bt-f-category">Category</label>
      <select id="bt-f-category">{_options([(c, c) for c in cats], "All categories")}</select>
      <label class="sr" for="bt-f-tech">Technology</label>
      <select id="bt-f-tech">{_options([(t, t) for t in techs], "All technologies")}</select>
      <button type="button" class="btn bt-ftoggle" id="bt-ftoggle" aria-expanded="false" aria-controls="bt-more">More filters</button>
      <div class="bt-more" id="bt-more">
        <label class="sr" for="bt-f-stage">Build stage</label>
        <select id="bt-f-stage">{_options([("idea", "Idea"), ("prototype", "Prototype"), ("mvp", "MVP"), ("beta", "Beta"),
                                            ("launched", "Launched"), ("unknown", "Unknown")], "All stages")}</select>
        <label class="sr" for="bt-f-activity">Activity</label>
        <select id="bt-f-activity">{_options([("rising", "Rising"), ("stable", "Stable"), ("declining", "Declining"),
                                               ("insufficient", "Insufficient data")], "All activity")}</select>
        <label class="sr" for="bt-f-blockers">Blockers</label>
        <select id="bt-f-blockers">{_options([("yes", "Has blockers"), ("none", "None reported"),
                                              ("unknown", "No blocker data")], "Any blockers")}</select>
      </div>
    </div>
    <div class="bt-chips" id="bt-chips" hidden></div>
    <div class="bt-scroll"><table class="bt-t">
      <caption class="sr">Publicly shared developer projects (sample data)</caption>
      <thead><tr>{th("name", "Project", "c-proj")}{th("", "Builder", "c-builder")}{th("category", "Category", "c-cat")}
        {th("", "Tech stack", "c-tech")}{th("stage", "Build stage", "c-stage")}{th("", "Current focus", "c-focus")}
        {th("blockers", "Blockers", "c-blk")}{th("activity", "Activity", "c-act")}{th("lastObserved", "Last observed", "c-obs")}
        {th("", "Actions", "c-acts")}</tr></thead>
      <tbody id="bt-body"></tbody></table>
      <div class="bt-state" id="bt-state" hidden></div></div>
    <div class="bt-foot" id="bt-foot"><span id="bt-range"></span><span class="sp"></span>
      <label for="bt-size">Rows per page</label>
      <select id="bt-size"><option>10</option><option>25</option><option>50</option></select>
      <button type="button" class="btn" id="bt-prev">Previous</button><span id="bt-pageno"></span>
      <button type="button" class="btn" id="bt-next">Next</button></div>
  </section>
  <p class="sub" style="margin-top:12px">“Last observed” is when public evidence was last seen, not when development happened.
    Activity compares observations over time; “Insufficient data” means there aren't enough comparable observations yet.</p>
</main>
<div class="bt-pop" id="bt-pop" role="dialog" aria-label="Reported blockers" hidden></div>
<div class="bt-ov" id="bt-ov" hidden></div>
<aside class="bt-drawer" id="bt-drawer" role="dialog" aria-modal="true" aria-labelledby="bt-dt" tabindex="-1" hidden></aside>
<div class="bt-modal" id="bt-modal" role="dialog" aria-modal="true" aria-labelledby="bt-mt" tabindex="-1" hidden></div>
<script type="application/json" id="bt-data">{payload}</script>"""
    return _page("Building Now · projects table (prototype)", CSS + body, active="building", script=JS)
