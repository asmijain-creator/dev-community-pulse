"""Building Now pages: what developers are publicly building, from classified public discussions.

Every number is computed from stored rows (lib.build_projects). AI-written text (summaries, descriptive
titles, inferred technologies and blockers, suggested pain point links) is labelled as AI wherever it
appears, and explicit reports are never mixed with AI inferences.
"""
from html import escape
from urllib.parse import quote, urlencode

from lib import build_config as C
from lib import build_projects as P
from lib import building as B
from lib.views import _ago, _flash, _nice, _page, _point_href, _src

MIGRATION_NOTE = ('<div class="note-box"><b>Building Now needs a one-time database update.</b> Run '
                  '<code>supabase/migrations/003_building_now.sql</code> once in Supabase → SQL Editor. It only adds '
                  'new tables; existing data is not touched. After that, the next <b>Run now</b> or Friday run collects '
                  'and classifies build discussions.</div>')
MIGRATION_005_NOTE = ('<div class="note-box"><b>One more database update unlocks project history.</b> Run '
                      '<code>supabase/migrations/005_building_projects.sql</code> in Supabase → SQL Editor to store projects, '
                      'public handles, pain point links and the project watchlist. Until then projects are grouped on the fly '
                      'and the watchlist is unavailable. It only adds tables and columns.</div>')
_SOURCES = [("hn", "Hacker News"), ("stackoverflow", "Stack Overflow"), ("github", "GitHub")]
_STATUS_CLS = {"rising": "up", "growing": "up", "new": "up", "newly_observed": "up", "declining": "down"}
DISCLAIMER = ("DevvIT only sees what developers share publicly. It can't know what anyone is privately working on, and "
              "counts are of public posts and projects, not of users, installs or real adoption.")


def _ext(url: str | None, label: str, cls: str = "") -> str:
    if not (url or "").startswith(("https://", "http://")):
        return ""
    return (f'<a class="{cls}" href="{escape(url)}" target="_blank" rel="noopener noreferrer nofollow">'
            f'{escape(label)} <span aria-hidden="true">↗</span></a>')


def _date(iso: str | None) -> str:
    return escape((iso or "")[:10]) or "—"


def project_href(p: dict) -> str:
    return (f'/building/project?id={quote(p["id"])}' if p.get("id")
            else f'/building/project?key={quote(p["project_key"], safe="")}')


def _href(f: dict, **change) -> str:
    q = {**f, **change}
    out = {k: v for k, v in q.items() if v and k not in ("days", "page")}
    if q.get("days", C.DEFAULT_PERIOD) != C.DEFAULT_PERIOD:
        out["days"] = q["days"]
    if q.get("page", 1) != 1:
        out["page"] = q["page"]
    return "/building" + ("?" + urlencode(out) if out else "")


def _sel(name: str, options: list[tuple], current, label: str) -> str:
    opts = "".join(f'<option value="{escape(str(v))}"{" selected" if str(v) == str(current or "") else ""}>{escape(t)}</option>'
                   for v, t in options)
    return f'<label class="field"><span>{label}</span><select name="{name}">{opts}</select></label>'


def _trend(t: dict) -> str:
    sym, label = P.TRENDS[t["status"]]
    tip = (f'{t["cur"]} public observations in the last {C.TREND_WINDOW_DAYS} days vs {t["prev"]} in the {C.TREND_WINDOW_DAYS} '
           f'days before' if t["status"] != "insufficient" else
           f'Needs at least {C.TREND_MIN_OBS} observations including some in the previous {C.TREND_WINDOW_DAYS} days')
    return f'<span class="chg {_STATUS_CLS.get(t["status"], "flat")}" title="{escape(tip)}">{sym} {label}</span>'


def _fresh(state: str) -> str:
    return f'<span class="pstat {state}">{escape(P.FRESHNESS[state])}</span>'


def _stage(p: dict) -> str:
    st = p.get("build_stage") or "unknown"
    tip = f' title="Stated in the post: “{escape(p["stage_quote"])}”"' if p.get("stage_quote") else ' title="No post states the stage"'
    return f'<span class="cov {"mid" if st != "unknown" else "ok"}"{tip}>{C.STAGES[st]}</span>'


def _tech_chips(techs: list[dict], f: dict | None = None, limit: int = 6) -> str:
    out = []
    for t in techs[:limit]:
        tip = "Named in the post" if t["explicit"] else "AI inference: not named in any post"
        body = f'{escape(t["name"])}{"" if t["explicit"] else " · inferred"}'
        cls = "tchip" if t["explicit"] else "tchip inf"
        out.append(f'<a class="{cls}" href="{escape(_href(f or {}, tech=t["key"], page=1))}" title="{tip}. Click to filter by it">{body}</a>'
                   if f is not None else f'<span class="{cls}" title="{tip}">{body}</span>')
    more = f'<span class="small">+{len(techs) - limit}</span>' if len(techs) > limit else ""
    return f'<div class="tchips">{"".join(out)}{more}</div>' if out else '<span class="zero">—</span>'


# ---------- page parts ----------
def _filters(f: dict, tech_options: list[dict], admin_ok: bool) -> str:
    tech_opts = [("", "All technologies")] + [(t["key"], f'{t["label"]} ({t["n"]})') for t in tech_options]
    if f.get("tech") and f["tech"] not in {t["key"] for t in tech_options}:
        tech_opts.append((f["tech"], f["tech"]))
    watch = (f'<label class="field chk"><span>Watchlist</span><span><input type="checkbox" name="watch" value="1"'
             f'{" checked" if f.get("watch") else ""}> Saved projects only</span></label>' if admin_ok else "")
    return f"""
<form class="bfilters" method="get" action="/building" data-bfilter role="search" aria-label="Filter projects">
  <label class="field grow"><span>Search</span><input type="search" name="q" value="{escape(f.get('q') or '')}"
     placeholder="Project, description, technology or public handle"></label>
  {_sel("days", C.PERIODS, f.get("days", C.DEFAULT_PERIOD), "Date range (posted)")}
  {_sel("category", [("", "All categories")] + [(c, c) for c in B.CATEGORIES], f.get("category"), "Category")}
  {_sel("tech", tech_opts, f.get("tech"), "Technology")}
  {_sel("source", [("", "All sources")] + _SOURCES, f.get("source"), "Source")}
  {_sel("stage", [("", "Any stage")] + list(C.STAGES.items()), f.get("stage"), "Build stage")}
  {_sel("fresh", [("", "Any activity")] + list(P.FRESHNESS.items()), f.get("fresh"), "Freshness")}
  {_sel("blockers", [("", "Any"), ("yes", "Has reported blockers"), ("no", "No reported blockers")], f.get("blockers"), "Blockers")}
  <label class="field"><span>First seen from</span><input type="date" name="seen_from" value="{escape(f.get('seen_from') or '')}"></label>
  <label class="field"><span>First seen to</span><input type="date" name="seen_to" value="{escape(f.get('seen_to') or '')}"></label>
  {_sel("sort", list(P.SORTS.items()), f.get("sort") or "recent", "Sort by")}
  {watch}
  <div class="bf-btns"><button class="btn btn-primary" type="submit">Apply</button><a class="btn" href="/building">Reset</a></div>
</form>
<div class="bloading" hidden>Loading…</div>"""


def _metric(label: str, value, sub: str, how: str, dark: bool = False) -> str:
    v = "—" if value is None else value
    return (f'<div class="kpi{" dark" if dark else ""}"><div class="l">{label}</div><div class="v">{v}</div>'
            f'<div class="s">{sub}</div><details class="how"><summary>How it’s calculated</summary><p>{how}</p></details></div>')


def _metrics(m: dict, f: dict, period: str, stack: dict) -> str:
    cur, prev = stack["cur_weeks"], stack["prev_weeks"]
    trend_how = (f"Technologies explicitly named by at least {C.STACK_MIN_PROJECTS} distinct projects that are new, newly observed "
                 f"or growing in Show HN posts from {cur[0]} to the end of the latest complete week, compared with the same number "
                 f"of weeks before ({prev[0]} onwards).")
    if m["trending"] is None:
        trend_how = "Not enough earlier data yet to compare two equal periods. " + trend_how
    return f"""
<div class="kpis">
  {_metric("Projects discovered", m["projects"], f"{escape(period)} · distinct projects",
           "Distinct projects with at least one public post in the selected date range that matches the filters. Several posts "
           "about the same project (same repository, website, or name posted by the same handle) count once.", dark=True)}
  {_metric("Active public builders", m["builders"], f"posted in the last {m['active_days']} days",
           f"Distinct public handles (per platform) that posted about a project in the last {m['active_days']} days. An older post "
           f"never makes someone active; the window is the shorter of the date range and {C.ACTIVE_BUILDER_DAYS} days. Posts without "
           "a known handle aren't counted.")}
  {_metric("Trending technologies", m["trending"], "new or growing · complete weeks", trend_how)}
  {_metric("Reported blockers", m["blockers"], f"{escape(period)} · quoted by builders",
           "Distinct problems builders reported in their own words (the quote is checked against the post). The same "
           "problem repeated for one project counts once. AI-inferred challenges are not counted.")}
</div>"""


def _table(rows: list[dict], f: dict, page: int, pages: int, total: int, can_watch: bool) -> str:
    if not rows:
        return ('<div class="panel empty-state"><b>No projects match these filters.</b><p class="sub">Try a longer date range, '
                f'clear a filter, or <a href="/building">reset everything</a>.</p></div>')
    body = []
    for p in rows:
        href = project_href(p)
        handle = (f'{_ext(p.get("builder_profile_url"), p["builder_username"])}' if p.get("builder_profile_url")
                  else escape(p.get("builder_username") or "") or '<span class="zero">Unknown</span>')
        explicit_blockers = [b for b in p["blockers"] if b["explicit"]]
        focus = (f'{escape(B._clip(p["current_focus"], 90))}<small>{_date(p.get("focus_observed_at"))}</small>'
                 if p.get("current_focus") else '<span class="zero">Not stated</span>')
        src_label, src_cls = _src(p.get("source"))
        watch = (f'<form method="post" action="/building/watch" class="inline"><input type="hidden" name="project_id" value="{escape(p["id"])}">'
                 f'<input type="hidden" name="on" value="{0 if p.get("watched") else 1}"><input type="hidden" name="back" value="{escape(_href(f))}">'
                 f'<button class="lnk" type="submit">{"★ Saved" if p.get("watched") else "☆ Save"}</button></form>'
                 if p.get("id") and can_watch else "")
        body.append(f"""<tr>
  <th scope="row" class="pname"><a href="{escape(href)}">{escape(p["project_name"])}</a>{'<span class="ai-tag" title="The post doesn’t name the project; this title was written by AI">AI title</span>' if p.get("name_is_ai") else ""}{'<span class="flag" title="Flagged for review">⚑</span>' if p.get("review_status") == "flagged" else ""}</th>
  <td class="pdesc">{escape(B._clip(p.get("description"), 140)) or '<span class="zero">—</span>'}{'<span class="ai-tag">AI</span>' if p.get("description") else ""}</td>
  <td>{handle}</td>
  <td>{f'<span class="pill">{escape(p["category"])}</span>' if p.get("category") else '<span class="zero">—</span>'}</td>
  <td class="ptech">{_tech_chips(p["techs"], f, 4)}</td>
  <td>{_stage(p)}</td>
  <td class="pfocus">{focus}</td>
  <td class="n">{f'<a href="{escape(href)}#blockers">{len(explicit_blockers)}</a>' if explicit_blockers else '<span class="zero">0</span>'}</td>
  <td>{_trend(p["trend"])}<div>{_fresh(p["freshness"])}</div></td>
  <td class="mono" title="First collected by DevvIT (original post: {_date(p.get('first_published_at'))})">{_date(p.get("first_seen_at"))}</td>
  <td class="mono" title="Latest observation collected by DevvIT (latest post: {_date(p.get('last_published_at'))})">{_date(p.get("last_observed_at"))}</td>
  <td>{_ext(p.get("source_url"), src_label, "schip " + src_cls)}</td>
  <td class="acts"><a class="lnk" href="{escape(href)}">Details</a>{watch}
    <button class="lnk" type="button" data-copy="{escape(href)}" title="Copy a link to this project">Share</button>
    <a class="lnk" href="{escape(href)}#related">Pain points</a></td>
</tr>""")
    pager = ""
    if pages > 1:
        prev = f'<a class="btn" href="{escape(_href(f, page=page - 1))}" rel="prev">← Previous</a>' if page > 1 else ""
        nxt = f'<a class="btn" href="{escape(_href(f, page=page + 1))}" rel="next">Next →</a>' if page < pages else ""
        pager = f'<nav class="tpager" aria-label="Pages">{prev}<span class="mono">Page {page} of {pages}</span>{nxt}</nav>'
    return f"""
<div class="tbl"><table class="ptab">
  <caption class="sr">Projects shared publicly, {total} matching</caption>
  <thead><tr><th scope="col">Project</th><th scope="col">Description</th><th scope="col">Public builder / team</th>
    <th scope="col">Category</th><th scope="col">Technology stack</th><th scope="col">Build stage</th><th scope="col">Current focus</th>
    <th scope="col" class="n">Blockers</th><th scope="col">Activity trend</th><th scope="col">First seen</th>
    <th scope="col">Last observed</th><th scope="col">Source</th><th scope="col">Actions</th></tr></thead>
  <tbody>{"".join(body)}</tbody></table>
  <div class="tfoot">Showing {len(rows)} of {total} projects. First seen and last observed are when DevvIT collected the posts;
    hover them for the original post dates.</div></div>
{pager}"""


def _stack(s: dict, f: dict, days: int) -> str:
    groups = "".join(f'<a class="chip{" on" if f.get("group") == k else ""}" href="{escape(_href(f, group=k if f.get("group") != k else "", page=1))}#stack">{escape(v)}</a>'
                     for k, v in C.TECH_GROUPS.items() if k != "other")
    cur, prev = s["cur_weeks"], s["prev_weeks"]
    span = f'{len(cur)} complete week{"s" if len(cur) != 1 else ""}'
    note = (f'Distinct projects naming each technology in Show HN posts during the latest {span} (from {cur[0]}) compared with the '
            f'{span} before (from {prev[0]}). Only Show HN posts count here because they are sampled the same way every week. '
            'More mentions don’t mean a better or more widely adopted technology.')
    if not s["covered"]:
        note = (f'<b>Needs earlier data:</b> DevvIT’s stored Show HN posts start {_date(str(s["first_week"])) if s["first_week"] else "—"}, '
                f'so the previous {span} can’t be compared yet. Counts below are real; the trend labels wait for more history. ' + note)
    rows = s["rows"][:25]
    if not rows:
        table = f'<p class="sub">No technology was named by at least {C.STACK_MIN_PROJECTS} projects in either period.</p>'
    else:
        body = ""
        for r in rows:
            sym, label = P.STACK_STATUS[r["status"]]
            pct = (f'{r["pct"]:+d}%' if r["pct"] is not None else
                   '<span class="small" title="No projects in the previous period, so a percentage would be misleading">new baseline</span>')
            ex = ", ".join(f'<a href="{escape(project_href(p))}">{escape(B._clip(p["project_name"], 40))}</a>' for p in r["examples"][:3])
            body += (f'<tr><th scope="row"><a href="{escape(_href(f, tech=r["key"], page=1))}">{escape(r["name"])}</a></th>'
                     f'<td class="small">{escape(C.TECH_GROUPS[r["group"]])}</td><td class="n">{r["cur"]}</td><td class="n">{r["prev"]}</td>'
                     f'<td class="n">{r["obs"]}</td><td class="n">{pct}</td>'
                     f'<td><span class="chg {_STATUS_CLS.get(r["status"], "flat")}">{sym} {label}</span></td><td class="small">{ex or "—"}</td></tr>')
        table = (f'<div class="tbl"><table class="ttab"><thead><tr><th>Technology</th><th>Category</th><th class="n">Projects now</th>'
                 f'<th class="n">Projects before</th><th class="n">Posts now</th><th class="n">Change</th><th>Trend</th>'
                 f'<th>Supporting projects</th></tr></thead><tbody>{body}</tbody></table></div>')
    return f"""
<section class="panel" id="stack" style="margin-top:14px"><h2 class="ph">Trending Stack</h2>
  <p class="sub">{note}</p><div class="chips-row" role="group" aria-label="Technology categories">{groups}</div>{table}</section>"""


def _link_html(b: dict, admin_ok: bool, back: str = "/building#challenges") -> str:
    """The pain point a blocker is linked to, with why, and whether it's AI-suggested or confirmed."""
    pp, method, status = b.get("pain_point"), b.get("link_method"), b.get("link_status")
    if method == "none" or (method and not pp):
        return '<span class="small">No matching DevvIT pain point: candidate for future discovery</span>'
    if not pp or status == "rejected":
        return ('<span class="small">Not yet compared with pain points</span>' if not method else
                '<span class="small">Suggested link rejected: candidate for future discovery</span>')
    tag = {"confirmed": '<span class="cov ok">Confirmed</span>',
           "suggested": '<span class="ai-tag" title="Suggested by Gemini, not yet confirmed">AI-suggested link</span>'}.get(status, "")
    if method == "same_thread":
        tag = '<span class="cov ok" title="The pain point pipeline tagged this same discussion">Same thread</span>'
    review = ""
    if admin_ok and method == "ai_match" and b.get("id") is not None and status == "suggested":
        review = (f'<form method="post" action="/building/link" class="inline"><input type="hidden" name="blocker_id" value="{b["id"]}">'
                  f'<input type="hidden" name="back" value="{escape(back)}">'
                  f'<button class="lnk" name="status" value="confirmed">Confirm</button><button class="lnk" name="status" value="rejected">Reject</button></form>')
    return (f'<span>Related pain point: <a href="{_point_href(pp, None)}">{escape(_nice(pp))}</a> {tag}</span>'
            + (f'<small class="why">Why: {escape(b.get("link_basis") or "")}</small>' if b.get("link_basis") else "") + review)


def _blocker_row(b: dict, admin_ok: bool, with_project: bool = True, back: str = "/building#challenges") -> str:
    it = b["item"]
    proj = b.get("project")
    ev = ('<span class="cov ok">Explicitly reported</span>' if b["explicit"] else '<span class="ai-tag">AI-inferred</span>')
    quote_html = (f'<blockquote class="bquote">“{escape(b["quote"])}”<small>From the post</small></blockquote>'
                  if b.get("quote") and b["explicit"] else "")
    return f"""<li class="blk">
  <div class="blk-h"><b>{escape(b["detail"])}</b>{ev}<span class="pill">{escape(C.BLOCKER_CATEGORIES.get(b["category"], "Other"))}</span></div>
  {quote_html}
  <div class="blk-m">{f'<a href="{escape(project_href(proj))}">{escape(proj["project_name"])}</a> · ' if with_project and proj else ""}
    {_ext(it.get("discussion_url"), "Original post")} · posted {_date(it.get("posted_at"))}</div>
  <div class="blk-l">{_link_html(b, admin_ok, back)}</div>
</li>"""


def _challenges(ch: dict, admin_ok: bool, period: str) -> str:
    if not ch["groups"] and not ch["inferred"]:
        return (f'<section class="panel" id="challenges" style="margin-top:14px"><h2 class="ph">Builder Challenges</h2>'
                f'<p class="sub">No builder in this selection ({escape(period)}) reported a problem in their own post.</p></section>')
    groups = "".join(
        f'<details class="bgroup"{" open" if i == 0 else ""}><summary><b>{escape(g["label"])}</b><span class="mono">{len(g["rows"])} '
        f'distinct blocker{"s" if len(g["rows"]) != 1 else ""}</span></summary><ul class="blks">'
        + "".join(_blocker_row(r, admin_ok) for r in g["rows"][:12]) + "</ul></details>"
        for i, g in enumerate(ch["groups"]))
    inferred = ""
    if ch["inferred"]:
        inferred = (f'<details class="bgroup inf"><summary><b>AI-inferred challenges</b><span class="mono">{len(ch["inferred"])} · not counted</span></summary>'
                    '<p class="sub">Gemini suggested these from context; the builder didn’t state them in words DevvIT could find in the post. '
                    'Treat them as leads to check, not evidence.</p><ul class="blks">'
                    + "".join(_blocker_row(r, admin_ok) for r in ch["inferred"][:15]) + "</ul></details>")
    disc = (f'<p class="sub"><b>{ch["unmatched"]}</b> explicit blocker{"s" if ch["unmatched"] != 1 else ""} have no matching DevvIT pain point '
            'yet: possible unmet needs worth a look.</p>' if ch["unmatched"] else "")
    return f"""
<section class="panel" id="challenges" style="margin-top:14px"><h2 class="ph">Builder Challenges</h2>
  <p class="sub">Problems developers reported while building, grouped by category ({escape(period)}). Each is quoted from the
    original post and linked to an existing DevvIT pain point only when the same thread is tagged with it or Gemini judged them
    to be the same problem (shown with its reason, and confirmable).</p>{disc}{groups}{inferred}</section>"""


def _related(rel: dict | None) -> str:
    if not rel:
        return ""
    rows = "".join(
        f'<li><a href="{_point_href(r["pain_point"], None)}">{escape(_nice(r["pain_point"]))}</a> '
        f'<span class="sub">· {len(r["threads"])} thread{"s" if len(r["threads"]) != 1 else ""} {escape(r["basis"])}</span></li>'
        for r in rel["rows"]) or f'<li class="sub">No stored pain point thread supports a connection to {escape(rel["name"])}.</li>'
    return (f'<section class="panel" style="margin-top:14px"><h2 class="ph">Related pain points: {escape(rel["name"])}</h2>'
            f'<p class="sub">{escape(rel["how"])}</p><ul class="plain">{rows}</ul></section>')


def _coverage(d: dict) -> str:
    fr = d["fresh"]
    last = (fr.get("last") or {}).get("stats") or {}
    excl = ", ".join(f'{v} {k.replace("_", " ")}' for k, v in sorted(d["excluded"].items(), key=lambda x: -x[1])) or "none"
    issues = []
    if (last.get("show_hn") or {}).get("failed"):
        issues.append(f'{last["show_hn"]["failed"]} Show HN week(s) failed to load')
    if last.get("failed_batches"):
        issues.append(f'{last["failed_batches"]} AI batch(es) failed')
    if last.get("rate_limited"):
        issues.append("Gemini rate limit reached")
    if last.get("pending"):
        issues.append(f'{last["pending"]} discussions left for the next update')
    for k in ("author_lookup_error", "sync_error", "releases_error", "error"):
        if last.get(k):
            issues.append(f'{k.replace("_", " ")}: {str(last[k])[:100]}')
    return f"""
<section class="panel" id="coverage" style="margin-top:14px"><h2 class="ph">Data freshness and coverage</h2>
  <table class="qtab"><tbody>
    <tr><td><b>Refresh cadence</b></td><td class="sub">Periodic, not real time: every Friday at 8:30 AM IST with the weekly brief, and whenever
      someone clicks Update below. Each update only classifies posts DevvIT hasn’t seen.</td></tr>
    <tr><td><b>Last update</b></td><td class="sub">{escape(_ago(fr["last_update"]) or "never")}{" · <b>stale</b>: older than 8 days, the last run may have failed. Previously collected data is still shown." if fr["stale"] else ""}</td></tr>
    <tr><td><b>Newest project post</b></td><td class="sub">{_date(fr["newest_post"])}</td></tr>
    <tr><td><b>Classified</b></td><td class="sub">{d["classified"]} public discussions in the last 12 months; {len(d["items"])} were build activity. Excluded: {escape(excl)}.</td></tr>
    <tr><td><b>Last update issues</b></td><td class="sub">{escape(" · ".join(issues)) or "None"}</td></tr>
    <tr><td><b>Update now</b></td><td>{REFRESH_FORM}</td></tr>
    <tr><td><b>Sources</b></td><td class="sub">Up to {40} of each week’s most upvoted Hacker News “Show HN” posts (public Algolia API),
      DevvIT threads from Hacker News, Stack Overflow and GitHub whose text says the author built something, and public GitHub
      releases of projects that link a public repository (GitHub REST API). Names, stages, quotes and technologies are checked
      against the post text; public handles come from the platform, never from guessing.</td></tr>
  </tbody></table></section>"""


FILTER_JS = """<script>
(() => {
  const f = document.querySelector('form[data-bfilter]');
  if (f) {
    const busy = () => { document.querySelector('.bloading').hidden = false; document.querySelector('.bresults')?.setAttribute('aria-busy', 'true'); };
    f.addEventListener('submit', busy);
    f.querySelectorAll('select, input[type=checkbox], input[type=date]').forEach(s => s.addEventListener('change', () => { busy(); f.submit(); }));
  }
  document.querySelectorAll('form[data-brefresh]').forEach(r => r.addEventListener('submit', () => {
    const b = r.querySelector('button'); b.disabled = true; b.textContent = 'Updating… keep this tab open';
  }));
  document.addEventListener('click', async e => {
    const b = e.target.closest('[data-copy]'); if (!b) return;
    const url = new URL(b.dataset.copy, location.origin).href;
    try {
      if (navigator.share && matchMedia('(pointer: coarse)').matches) await navigator.share({ url });
      else { await navigator.clipboard.writeText(url); const t = b.textContent; b.textContent = 'Link copied'; setTimeout(() => b.textContent = t, 1500); }
    } catch (err) { prompt('Copy this link', url); }
  });
})();
</script>"""

REFRESH_FORM = ('<form method="post" action="/building/refresh" class="inline" data-brefresh>'
                '<button class="btn" type="submit">Update build activity</button> '
                '<span class="sub">Collects new posts and releases and classifies only what DevvIT hasn’t seen. '
                'No brief or email. Can take a few minutes the first time.</span></form>')


def _intro(fresh: dict | None) -> str:
    status = ""
    if fresh:
        status = (f'<p class="rstatus mono">Last updated {escape(_ago(fresh["last_update"]) or "never")} · refreshed weekly and on demand'
                  f'{" · <b>stale</b>" if fresh["stale"] else ""} · <a href="#coverage">coverage</a>'
                  f' · <a href="/building?watch=1&amp;days=0" title="Projects saved to the watchlist (admin password)">★ Saved projects</a></p>')
    return f"""
  <div class="fb-eyebrow">Building Now</div>
  <h1 class="fb-h1">Building Now</h1>
  <p class="fb-sub">Track publicly shared developer projects, technologies, build activity, and technical challenges.</p>
  <p class="sub" style="max-width:720px">{DISCLAIMER}</p>{status}"""


def building_page(d: dict | None, f: dict, history: list[dict], *, state: str = "ok", error: str | None = None,
                  admin_ok: bool = False) -> str:
    if state != "ok":
        msg = {"migrate": MIGRATION_NOTE,
               "error": f'<div class="note-box err"><b>Building Now couldn\'t load.</b> {escape(error or "The database didn’t respond.")} '
                        'Previously collected data is safe; try again in a minute. If it keeps happening check System health.</div>'}[state]
        return _page("Building Now", f'<main class="fb">{_intro(None)}{msg}</main>', active="building", history=history)

    if not d["items"]:
        empty = ('<div class="note-box"><b>No build activity stored yet.</b> Nothing is shown until real public posts have been '
                 'collected and classified: DevvIT never fills this page with sample data. Click <b>Update build activity</b> (or wait '
                 f'for the Friday run); the first update fills the last few weeks.<p style="margin:10px 0 0">{REFRESH_FORM}</p></div>')
        return _page("Building Now", f'<main class="fb">{_flash(d.get("flash"))}{_intro(d["fresh"])}{empty}{_coverage(d)}</main>',
                     active="building", history=history, script=FILTER_JS)

    period = next((t for v, t in C.PERIODS if v == f.get("days", C.DEFAULT_PERIOD)), "Selected period").lower()
    stale = ('<div class="note-box"><b>This data may be out of date:</b> the last update was '
             f'{escape(_ago(d["fresh"]["last_update"]))}. Showing what was collected before.</div>' if d["fresh"]["stale"] else "")
    v2 = "" if d.get("v2") else MIGRATION_005_NOTE
    watch_note = ('<p class="sub">Showing <b>saved projects</b> only. <a href="' + escape(_href(f, watch="", page=1)) + '">Show all</a></p>'
                  if f.get("watch") else "")
    body = f"""
<main class="fb">
  {_flash(d.get("flash"))}
  {_intro(d["fresh"])}
  {stale}{v2}
  {_filters(f, d["tech_options"], admin_ok and d.get("v2"))}
  <div class="bresults">
  {_metrics(d["metrics"], f, period, d["stack"])}
  <nav class="secnav" aria-label="Sections"><a href="#projects">Projects</a><a href="#stack">Trending Stack</a>
    <a href="#challenges">Builder Challenges</a><a href="#coverage">Coverage</a></nav>
  <h2 class="sec-h2" id="projects">Projects <small class="sub">{d["total"]} matching · {escape(period)}</small></h2>
  {watch_note}
  {_table(d["page_rows"], f, d["page"], d["pages"], d["total"], bool(d.get("v2")))}
  {_related(d.get("related"))}
  {_stack(d["stack"], f, f.get("days", C.DEFAULT_PERIOD))}
  {_challenges(d["challenges"], admin_ok, period)}
  {_coverage(d)}
  </div>
</main>"""
    return _page("Building Now", body, active="building", history=history, script=FILTER_JS)


# ---------- project detail ----------
def _timeline(items: list[dict]) -> str:
    rows = []
    for it in items:
        label, cls = _src(it.get("source"))
        ev = it.get("event_type")
        ev_html = (f'<span class="cov mid" title="{escape("Supported by: “" + it["event_quote"] + "”") if it.get("event_quote") else ""}">'
                   f'{escape(C.EVENTS.get(ev, ev))}</span>' if ev and ev != "unclear" else
                   '<span class="cov ok" title="The post doesn’t clearly show what kind of update it is">Not classified</span>')
        excerpt = (f'<blockquote class="bquote">“{escape(it["excerpt"])}”<small>From the post</small></blockquote>' if it.get("excerpt")
                   else '<p class="sub">No verbatim excerpt could be confirmed for this post.</p>')
        rows.append(f"""<li class="tl-i">
  <div class="tl-h"><span class="schip {cls}">{escape(label)}</span>{ev_html}
    <span class="mono">Posted {_date(it.get("posted_at"))} · collected {_date(it.get("classified_at"))}</span></div>
  <b class="tl-t">{escape(it.get("title_raw") or "Untitled")}</b>
  {excerpt}
  <div class="tl-l">{_ext(it.get("discussion_url"), "Open source")}{f' · ▲ {it["score"]} · {it.get("comments") or 0} comments' if it.get("origin") != "repo_release" else ""}</div>
</li>""")
    return f'<ol class="tl">{"".join(rows)}</ol>' if rows else '<p class="sub">No observations stored.</p>'


_NAMED = '<span class="cov ok">Named by the builder</span>'
_INFERRED = '<span class="ai-tag">AI-inferred</span>'


def _stack_table(techs: list[dict]) -> str:
    if not techs:
        return '<p class="sub">No technologies were named in this project’s posts.</p>'
    body = "".join(
        f'<tr><th scope="row">{escape(t["name"])}</th><td class="small">{escape(C.TECH_GROUPS[t["group"]])}</td>'
        f'<td>{_NAMED if t["explicit"] else _INFERRED}</td>'
        f'<td class="mono">{_date(t["first"])}</td><td class="mono">{_date(t["last"])}</td>'
        f'<td>{_ext((t["evidence"] or {}).get("discussion_url"), "Source")}</td></tr>' for t in techs)
    return (f'<div class="tbl"><table class="ttab"><thead><tr><th>Technology</th><th>Category</th><th>Evidence</th><th>First observed</th>'
            f'<th>Most recent</th><th>Supporting source</th></tr></thead><tbody>{body}</tbody></table></div>')


def project_page(p: dict, history: list[dict], *, admin_ok: bool, watch: dict | None, v2: bool,
                 related: list[dict], flash: str | None = None) -> str:
    href = project_href(p)
    handle = (_ext(p.get("builder_profile_url"), p["builder_username"]) if p.get("builder_profile_url")
              else escape(p.get("builder_username") or "") or '<span class="zero">Not available from the source</span>')
    focus = (f'{escape(p["current_focus"])} <span class="small">· reported {_date(p.get("focus_observed_at"))}</span>'
             + (f'<blockquote class="bquote">“{escape(p["focus_quote"])}”<small>From the post</small></blockquote>' if p.get("focus_quote") else "")
             if p.get("current_focus") else '<span class="zero">No post states a current focus</span>')
    t = p["trend"]
    rows = [
        ("Description", (f'{escape(p["description"])} <span class="ai-tag">AI summary of the latest post</span>' if p.get("description")
                         else '<span class="zero">—</span>')),
        ("Website", _ext(p.get("project_url"), p.get("project_url") or "") or '<span class="zero">None shared</span>'),
        ("Public repository", _ext(p.get("repository_url"), (p.get("repository_url") or "").removeprefix("https://")) or '<span class="zero">None shared</span>'),
        ("Public builder", f'{handle} <span class="small">public handle as shown on {escape(_src(p.get("builder_platform"))[0]) if p.get("builder_platform") else "the source"}</span>'),
        ("Category", f'<span class="pill">{escape(p["category"])}</span>' if p.get("category") else '<span class="zero">—</span>'),
        ("Technology stack", _tech_chips(p["techs"], None, 20)),
        ("Build stage", _stage(p) + (f' <span class="small">“{escape(p["stage_quote"])}”</span>' if p.get("stage_quote") else "")),
        ("Current reported focus", focus),
        ("First observed", f'{_date(p.get("first_seen_at"))} <span class="small">collected · original post {_date(p.get("first_published_at"))}</span>'),
        ("Last observed", f'{_date(p.get("last_observed_at"))} <span class="small">collected · latest post {_date(p.get("last_published_at"))}</span>'),
        ("Activity", f'{_fresh(p["freshness"])} {_trend(t)} <span class="small">{t["cur"]} post(s) in the last {C.TREND_WINDOW_DAYS} days, '
                     f'{t["prev"]} in the {C.TREND_WINDOW_DAYS} before</span>'),
    ]
    overview = "".join(f'<tr><th scope="row">{k}</th><td>{v}</td></tr>' for k, v in rows)

    actions = [f'<button class="btn" type="button" data-copy="{escape(href)}">Share project</button>',
               _ext(p.get("source_url"), "Open original source", "btn"),
               '<a class="btn" href="#related">Related pain points</a>']
    if p.get("id") and v2:
        on = bool(watch)
        note = (f'<label class="field" style="min-width:260px"><span>Private note (only visible to the admin)</span>'
                f'<textarea name="note" rows="2">{escape((watch or {}).get("note") or "")}</textarea></label>' if admin_ok else "")
        actions.insert(0, f'<form method="post" action="/building/watch" class="wform"><input type="hidden" name="project_id" value="{escape(p["id"])}">'
                          f'<input type="hidden" name="on" value="{0 if on and admin_ok else 1}"><input type="hidden" name="back" value="{escape(href)}">'
                          f'{note}<button class="btn btn-primary" type="submit">{"★ Remove from watchlist" if on and admin_ok else "☆ Add to watchlist"}</button>'
                          + (f'<button class="btn" type="submit" name="on" value="1">Save note</button>' if on and admin_ok else "") + "</form>")
        flagged = p.get("review_status") == "flagged"
        actions.append(f'<details class="flagbox"><summary class="btn">{"⚑ Flagged for review" if flagged else "Report an issue"}</summary>'
                       f'<form method="post" action="/building/flag"><input type="hidden" name="project_id" value="{escape(p["id"])}">'
                       f'<input type="hidden" name="flagged" value="{0 if flagged else 1}">'
                       + ("" if flagged else '<label class="field"><span>What looks wrong?</span><textarea name="note" rows="2" required></textarea></label>')
                       + f'<button class="btn" type="submit">{"Clear flag" if flagged else "Flag for review"}</button></form></details>')
    elif not p.get("id"):
        actions.append('<span class="small">Watchlist and review become available once the next update stores this project.</span>')

    flag_note = (f'<div class="note-box"><b>Flagged for review:</b> {escape(p.get("review_note") or "")}</div>'
                 if p.get("review_status") == "flagged" else "")
    explicit = [b for b in p["blockers"] if b["explicit"]]
    inferred = [b for b in p["blockers"] if not b["explicit"]]
    blockers = ('<ul class="blks">' + "".join(_blocker_row(b, admin_ok, False, href + "#blockers") for b in explicit) + "</ul>" if explicit
                else '<p class="sub">This builder hasn’t reported a blocker in their posts.</p>')
    if inferred:
        blockers += ('<details class="bgroup inf"><summary><b>AI-inferred challenges</b><span class="mono">'
                     f'{len(inferred)} · not counted</span></summary><ul class="blks">'
                     + "".join(_blocker_row(b, admin_ok, with_project=False) for b in inferred) + "</ul></details>")
    rel = "".join(
        f'<li><a href="{_point_href(r["pain_point"], None)}">{escape(_nice(r["pain_point"]))}</a> '
        f'{r["tag"]}<small class="why">{escape(r["basis"])}</small></li>' for r in related)
    rel_html = (f'<ul class="plain rel">{rel}</ul>' if rel else
                '<p class="sub">No existing DevvIT pain point is connected to this project by stored evidence. Shared keywords alone are '
                'never treated as a connection.</p>')
    body = f"""
<main class="fb pdetail">
  {_flash(flash)}
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/building">Building Now</a> › <span>Project</span></nav>
  <div class="fb-eyebrow">Project</div>
  <h1 class="fb-h1">{escape(p["project_name"])}{'<span class="ai-tag" title="The post doesn’t name the project; this title was written by AI">AI title</span>' if p.get("name_is_ai") else ""}</h1>
  <p class="sub">{DISCLAIMER}</p>
  {flag_note}
  <div class="pactions">{"".join(a for a in actions if a)}</div>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Project overview</h2>
    <table class="qtab ov"><tbody>{overview}</tbody></table></section>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Activity timeline <small class="sub">{len(p["items"])} public observation{"s" if len(p["items"]) != 1 else ""}</small></h2>
    <p class="sub">Newest first. Each entry is one public post or release; nothing is merged or overwritten, and an old
      announcement is shown with its own date, not as a current update.</p>{_timeline(p["items"])}</section>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Technology stack</h2>
    <p class="sub">“Named by the builder” means the name appears in the post text; AI-inferred technologies are suggestions.</p>
    {_stack_table(p["techs"])}</section>
  <section class="panel" id="blockers" style="margin-top:14px"><h2 class="ph">Reported blockers</h2>{blockers}</section>
  <section class="panel" id="related" style="margin-top:14px"><h2 class="ph">Related DevvIT intelligence</h2>
    <p class="sub">Existing pain points connected through this project’s own posts: the same discussion is tagged with the pain point,
      or one of its quoted blockers was matched to it (with the reason). No numeric confidence is shown because the matching isn’t calibrated.</p>
    {rel_html}</section>
</main>"""
    return _page(f'{p["project_name"]} · Building Now', body, active="building", history=history, script=FILTER_JS)


def build_panel(rows: list[dict], label: str) -> str:
    """'Related build activity' section for a pain point or opportunity page."""
    if rows is None:
        return ""
    items = "".join(
        f'<li><a href="{escape(r["item"].get("discussion_url") or "#")}" target="_blank" rel="noopener noreferrer">'
        f'{escape(r["item"].get("project_title") or r["item"].get("title_raw") or "discussion")}</a> '
        f'<span class="sub">· {escape((r["item"].get("posted_at") or "")[:10])} · {escape(r["basis"])}</span>'
        + (' <span class="ai-tag">AI-suggested link</span>' if r["suggested"] else "") + "</li>" for r in rows[:10])
    body = (f'<ul class="plain">{items}</ul>' if items else
            '<p class="sub">No stored build discussion is connected to this pain point.</p>')
    return (f'<section class="panel" style="margin-top:14px"><h2 class="ph">Related build activity <small class="sub">{len(rows)}</small></h2>'
            f'<p class="sub">Developers sharing what they build who ran into this. <a href="/building">Building Now →</a></p>{body}</section>')
