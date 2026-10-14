"""Building Now page: what developers are publicly building, from classified public discussions.

Every number is computed from stored rows (lib.building). AI-written text (summaries, descriptive titles,
inferred technologies, suggested pain point links) is labelled as AI wherever it appears.
"""
import os
from html import escape
from urllib.parse import urlencode

from lib import build_sources as S, building as B
from lib.views import _ago, _flash, _nice, _page, _point_href, _spark, _src

MIGRATION_NOTE = ('<div class="note-box"><b>Building Now needs a one-time database update.</b> Run '
                  '<code>supabase/migrations/003_building_now.sql</code> once in Supabase → SQL Editor. It only adds '
                  'new tables; existing data is not touched. After that, the next <b>Run now</b> or Friday run collects '
                  'and classifies build discussions.</div>')
_STATUS = {"new": ("New", "up"), "growing": ("▲ Growing", "up"), "declining": ("▼ Declining", "down"),
           "stable": ("Stable", "flat"), "pending": ("Needs history", "flat")}
_PERIODS = [(7, "Last 7 days"), (30, "Last 30 days"), (90, "Last 90 days"), (0, "All stored")]
_SOURCES = [("hn", "Hacker News"), ("github", "GitHub"), ("devto", "Dev.to"), ("producthunt", "Product Hunt"),
            ("stackoverflow", "Stack Overflow")]


def _href(f: dict, **change) -> str:
    q = {**f, **change}
    out = {k: v for k, v in q.items() if k != "days" and v}
    if q.get("days", 30) != 30:
        out["days"] = q["days"]
    return "/building" + ("?" + urlencode(out) if out else "")


def _sel(name: str, options: list[tuple], current, label: str) -> str:
    opts = "".join(f'<option value="{escape(str(v))}"{" selected" if str(v) == str(current or "") else ""}>{escape(t)}</option>'
                   for v, t in options)
    return f'<label class="field"><span>{label}</span><select name="{name}">{opts}</select></label>'


def _filters(f: dict, techs: list[dict]) -> str:
    tech_opts = [("", "All technologies")] + [(t["key"], f'{t["label"]} ({t["n"]})') for t in techs]
    if f.get("tech") and f["tech"] not in {t["key"] for t in techs}:
        tech_opts.append((f["tech"], f["tech"]))
    return f"""
<form class="bfilters" method="get" action="/building" data-bfilter>
  <label class="field grow"><span>Search</span><input type="search" name="q" value="{escape(f.get('q') or '')}" placeholder="e.g. agents, Postgres, deployment"></label>
  {_sel("days", _PERIODS, f.get("days", 30), "Published")}
  {_sel("category", [("", "All categories")] + [(c, c) for c in B.CATEGORIES], f.get("category"), "Category")}
  {_sel("tech", tech_opts, f.get("tech"), "Technology")}
  {_sel("source", [("", "All sources")] + _SOURCES, f.get("source"), "Source")}
  {_sel("blocker", [("", "Any or no blocker")] + list(B.BLOCKERS.items()), f.get("blocker"), "Reported blocker")}
  {_sel("theme", [("", "All themes"), ("emerging", "Emerging"), ("recurring", "Recurring")], f.get("theme"), "Theme")}
  <div class="bf-btns"><button class="btn btn-primary" type="submit">Apply</button>
    <a class="btn" href="/building">Reset</a></div>
</form>
<div class="bloading" hidden>Loading…</div>"""


def _blist(rows: list[dict], f: dict, param: str, empty: str) -> str:
    if not rows:
        return f'<p class="sub">{empty}</p>'
    top = rows[0]["n"] or 1
    return '<div class="blist">' + "".join(
        f'<a class="brow{" on" if f.get(param) == r["key"] else ""}" href="{escape(_href(f, **{param: r["key"]}))}">'
        f'<span>{escape(r["label"])}</span><i><u style="width:{r["n"] * 100 / top:.0f}%"></u></i><b>{r["n"]}</b></a>'
        for r in rows) + "</div>"


def _trend_table(t: dict, f: dict, param: str, title: str) -> str:
    rows = t["rows"][:12]
    if not rows:
        return f'<p class="sub">No {title.lower()} with enough discussions in the last {len(t["weeks"])} complete weeks yet.</p>'
    head = "".join(f'<th class="n">{escape(w[5:])}</th>' for w in t["weeks"])
    body = ""
    for r in rows:
        label, cls = _STATUS[r["status"]]
        cells = "".join(f'<td class="n">{c}</td>' for c in r["counts"])
        body += (f'<tr><td><a href="{escape(_href(f, **{param: r["key"]}))}">{escape(r["label"])}</a></td>{cells}'
                 f'<td>{_spark(r["counts"])}</td><td><span class="chg {cls}">{label}</span></td></tr>')
    totals = "".join(f'<td class="n">{n}</td>' for n in t["totals"])
    return (f'<div class="tbl"><table class="ttab"><thead><tr><th>{title}</th>{head}<th>Trend</th><th>Status</th></tr></thead>'
            f'<tbody>{body}<tr class="tot"><td>All project discussions</td>{totals}<td></td><td></td></tr></tbody></table></div>')


def _tech_chips(it: dict) -> str:
    chips = "".join(
        f'<span class="tchip{"" if t["explicit"] else " inf"}" title="{"Named in the post" if t["explicit"] else "AI inference: not named in the post"}">'
        f'{escape(t["name"])}{"" if t["explicit"] else " · inferred"}</span>'
        for t in sorted(it.get("techs", []), key=lambda t: not t["explicit"]))
    return f'<div class="tchips">{chips}</div>' if chips else ""


def card(it: dict) -> str:
    label, cls = _src(it.get("source"))
    url = it.get("discussion_url") or ""
    href = escape(url) if url.startswith(("https://", "http://")) else "#"
    proj = it.get("project_url") or ""
    proj_link = (f' · <a href="{escape(proj)}" target="_blank" rel="noopener noreferrer nofollow">Project link</a>'
                 if proj.startswith(("https://", "http://")) else "")
    ai_title = '<span class="ai-tag" title="The post doesn\'t name the project; this title was written by AI">AI-generated title</span>' if it.get("title_is_ai") else ""
    stage = (f'<span class="cov mid" title="{escape(it.get("stage_quote") or "")}">{escape(B.STAGES.get(it["stage"], it["stage"]))}</span>'
             if it.get("stage") else "")
    blockers = "".join(
        f'<li><b>{escape(B.BLOCKERS.get(b["kind"], b["kind"]))}:</b> {escape(b["detail"])}'
        + ("" if b["explicit"] else ' <span class="ai-tag">AI inference</span>') + "</li>" for b in it.get("blockers", []))
    pp = (f'<p class="sub">Same thread is tagged with pain point <a href="{_point_href(it["pain_point"], None)}">{escape(_nice(it["pain_point"]))}</a></p>'
          if it.get("pain_point") else "")
    excerpt = (f'<blockquote class="bquote">“{escape(it["excerpt"])}”<small>From the post</small></blockquote>'
               if it.get("excerpt") else '<p class="sub">No verbatim excerpt could be confirmed for this post.</p>')
    conf = f'{it["confidence"]:.2f}' if isinstance(it.get("confidence"), (int, float)) else "—"
    return f"""
<article class="bcard">
  <div class="b-top"><span class="pill">{escape(it.get("category") or "Other")}</span>
    <span class="small">{escape(B.ACTIVITY.get(it.get("activity_type") or "other", "Other"))}</span>{stage}</div>
  <h3 class="b-title"><a href="{href}" target="_blank" rel="noopener noreferrer">{escape(it.get("project_title") or it.get("title_raw") or "Untitled")}</a>{ai_title}</h3>
  {f'<p class="b-sum">{escape(it["summary"])} <span class="ai-tag">AI summary</span></p>' if it.get("summary") else ""}
  {_tech_chips(it)}
  {f'<ul class="b-block">{blockers}</ul>' if blockers else ""}
  {excerpt}
  {pp}
  <div class="b-foot"><span class="schip {cls}">{escape(label)}</span>
    <span class="mono">{escape((it.get("posted_at") or "")[:10])} · ▲ {it.get("score") or 0} · {it.get("comments") or 0} comments</span>
    <span class="mono" title="Gemini's own estimate that this is build activity">AI confidence {conf}</span>
    <span class="b-links"><a href="{href}" target="_blank" rel="noopener noreferrer">Open discussion ↗</a>{proj_link}</span></div>
</article>"""


BRIEF_CSS = """<style>
  .brief { margin-bottom: 14px; }
  .brief-lede { font-size: var(--fs-lg); line-height: 1.55; color: var(--text); margin: 12px 0 0; max-width: 80ch; }
  .brief-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; margin-top: 18px; }
  .brief-col { border-top: 2px solid var(--tone); padding-top: 10px; min-width: 0; }
  .brief-col h3 { margin: 0; font-size: var(--fs-md); display: flex; align-items: baseline; gap: 8px; }
  .brief-col h3 small { font-family: var(--mono); font-size: var(--fs-xs); color: var(--text-3); font-weight: 400; }
  .brief-col ul { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
  .brief-col li { font-size: var(--fs-sm); line-height: 1.45; }
  .brief-col li > a { font-weight: 600; color: var(--text); }
  .brief-col li > a:hover { color: var(--link); text-decoration: underline; }
  .brief-col li small { display: block; color: var(--text-3); font-size: var(--fs-xs); margin-top: 2px; }
  .brief-col li small a { color: var(--link); }
  .brief-col .chips-row { margin-top: 8px; }
  @media (max-width: 1000px) { .brief-grid { grid-template-columns: minmax(0, 1fr); } }
</style>"""


def _names(rows: list[dict]) -> str:
    """'A (3), B (2) and C (1)'."""
    parts = [f'{escape(r["label"])} ({r["n"]})' for r in rows]
    return ", ".join(parts[:-1]) + f" and {parts[-1]}" if len(parts) > 1 else "".join(parts)


def _link(it: dict, text: str) -> str:
    url = it.get("discussion_url") or ""
    href = escape(url) if url.startswith(("https://", "http://")) else "#"
    return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{escape(text)}</a>'


def _brief_example(it: dict) -> str:
    meta = " · ".join(x for x in (it.get("category") or "Other", B.STAGES.get(it.get("stage") or "", "")) if x)
    summ = (f' · {escape(B._clip(it["summary"], 120))} <span class="ai-tag">AI summary</span>' if it.get("summary") else "")
    return f'<li>{_link(it, it.get("project_title") or it.get("title_raw") or "Untitled")}<small>{escape(meta)}{summ}</small></li>'


def _brief_column(title: str, tone: str, g: dict, note: str, empty: str) -> str:
    lines = [f"Mostly {_names(g['categories'])}." if g["categories"] else "",
             f"Technologies named most: {_names(g['techs'])}." if g["techs"] else ""]
    examples = "".join(_brief_example(it) for it in g["examples"])
    return (f'<div class="brief-col" style="--tone:{tone}"><h3>{title}<small>{g["n"]} discussion{"s" if g["n"] != 1 else ""}</small></h3>'
            f'<p class="sub">{note} {" ".join(x for x in lines if x)}</p>'
            + (f'<ul>{examples}</ul>' if examples else f'<p class="sub">{empty}</p>') + "</div>")


def _brief(b: dict, f: dict, period: str) -> str:
    """Build brief: what developers are building, ideating and thinking about in this selection."""
    if not b["total"]:
        return ""
    bld, ide = b["building"], b["ideating"]
    filtered = any(f.get(k) for k in ("category", "tech", "source", "blocker", "theme", "q"))
    lede = (f'In the {escape(period)}{" (with the current filters)" if filtered else ""}, developers shared '
            f'<b>{b["total"]}</b> project discussion{"s" if b["total"] != 1 else ""}: <b>{bld["n"]}</b> about something they are '
            f'building ({bld["shipping"]} launched, in beta or maintained) and <b>{ide["n"]}</b> at the idea or experiment stage.')
    if b["categories"]:
        lede += f' Most activity was in {_names(b["categories"])}.'
    if b["blockers"]:
        top = b["blockers"][0]
        lede += f' The blocker reported most often was {escape(top["label"].lower())} ({top["n"]}).'

    thinking = ""
    for g in b["blockers"]:
        ex = g["examples"][0]
        said = f'“{escape(B._clip(ex["quote"], 140))}”' if ex.get("quote") else escape(B._clip(ex["detail"], 140))
        thinking += (f'<li><b>{escape(g["label"])}</b> · {g["n"]} report{"s" if g["n"] != 1 else ""}'
                     f'<small>{said} · {_link(ex["item"], ex["item"].get("project_title") or ex["item"].get("title_raw") or "discussion")}</small></li>')
    emerging = "".join(
        f'<a class="chip" href="{escape(_href(f, **({"category": r["key"]} if r["kind"] == "category" else {"tech": r["key"]})))}">'
        f'{escape(r["label"])} <small>{_STATUS[r["status"]][0]}</small></a>' for r in b["emerging"])
    think_col = (f'<div class="brief-col" style="--tone:var(--down)"><h3>Thinking about</h3>'
                 f'<p class="sub">Problems builders quoted in their own posts, and what is new or growing in the latest complete week.</p>'
                 + (f'<ul>{thinking}</ul>' if thinking else '<p class="sub">No blockers were quoted in this selection.</p>')
                 + (f'<div class="chips-row">{emerging}</div>' if emerging else "") + "</div>")
    return f"""{BRIEF_CSS}
<section class="panel brief"><div class="panel-h"><div><h2>Build brief</h2>
  <p class="sub">Computed from the stored discussions in this selection, not written by AI. Counts are discussions, not people or adoption.</p></div></div>
  <p class="brief-lede">{lede}</p>
  <div class="brief-grid">
    {_brief_column("Building", "var(--accent)", bld, "Prototypes, products, tools and open-source work.", "Nothing being built in this selection.")}
    {_brief_column("Ideating", "var(--amber)", ide, "Ideas and experiments, not yet a working project.", "No ideas or experiments in this selection.")}
    {think_col}
  </div>
</section>"""


def _blockers(groups: list[dict], labels: list[str]) -> str:
    if not groups:
        return '<p class="sub">No builder in this selection quoted a blocker in their post.</p>'
    out = ""
    for g in groups:
        ex = ""
        for e in g["examples"][:4]:
            it = e["item"]
            url = it.get("discussion_url") or "#"
            m = B.match_pain_point(e, labels)
            link = (f'<span class="sub"> · <span class="ai-tag" title="Suggested by word overlap, not confirmed">Suggested pain point</span> '
                    f'<a href="{_point_href(m[0], None)}">{escape(_nice(m[0]))}</a> (shares: {escape(", ".join(m[1]))})</span>' if m else "")
            ex += (f'<li>“{escape(e.get("quote") or e["detail"])}” — <a href="{escape(url)}" target="_blank" rel="noopener noreferrer">'
                   f'{escape(it.get("project_title") or it.get("title_raw") or "discussion")}</a>{link}</li>')
        out += (f'<details class="bgroup"><summary><b>{escape(g["label"])}</b><span class="mono">{g["n"]} report{"s" if g["n"] != 1 else ""}</span></summary>'
                f'<ul class="plain">{ex}</ul></details>')
    return out


def _related(rel: dict | None) -> str:
    if not rel:
        return ""
    rows = "".join(
        f'<li><a href="{_point_href(r["pain_point"], None)}">{escape(_nice(r["pain_point"]))}</a> '
        f'<span class="sub">· {len(r["threads"])} thread{"s" if len(r["threads"]) != 1 else ""} {escape(r["basis"])}</span></li>'
        for r in rel["rows"]) or f'<li class="sub">No stored pain point thread supports a connection to {escape(rel["name"])}.</li>'
    return (f'<section class="panel" style="margin-top:14px"><h2 class="ph">Related pain points: {escape(rel["name"])}</h2>'
            f'<p class="sub">{escape(rel["how"])} Open a pain point to see its threads; its page lists related build activity.</p>'
            f'<ul class="plain">{rows}</ul></section>')


def _coverage(d: dict, items: list[dict]) -> str:
    fr = d["fresh"]
    last = (fr.get("last") or {}).get("stats") or {}
    per_src = {s: sum(1 for it in items if it.get("source") == s) for s, _ in _SOURCES}
    src = " · ".join(f'{n}: <b>{per_src[s]}</b>' for s, n in _SOURCES)
    excl = ", ".join(f'{v} {k.replace("_", " ")}' for k, v in sorted(d["excluded"].items(), key=lambda x: -x[1])) or "none"
    issues = []
    for origin, label in S.ORIGINS.items():
        st = last.get(origin) or {}
        if st.get("failed"):
            issues.append(f'{label}: {st["failed"]} of {st.get("requests", st["failed"])} requests failed')
    if (last.get("producthunt") or {}).get("skipped"):
        issues.append("Product Hunt skipped: PRODUCT_HUNT_TOKEN is not set")
    if last.get("first_error"):
        issues.append("first AI error: " + str(last["first_error"])[:200])
    if last.get("failed_batches"):
        issues.append(f'{last["failed_batches"]} AI batch{"es" if last["failed_batches"] != 1 else ""} failed')
    if last.get("rate_limited"):
        issues.append("Gemini rate limit reached")
    if last.get("pending"):
        issues.append(f'{last["pending"]} discussions left for the next update')
    if last.get("error"):
        issues.append("update error: " + str(last["error"])[:120])
    return f"""
<section class="panel" style="margin-top:14px"><h2 class="ph">Data freshness and coverage</h2>
  <table class="qtab"><tbody>
    <tr><td><b>Last update</b></td><td class="sub">{escape(_ago(fr["last_update"]) or "never")}{" · <b>stale</b>: older than 8 days, the last run may have failed" if fr["stale"] else ""}</td></tr>
    <tr><td><b>Newest project post</b></td><td class="sub">{escape((fr["newest_post"] or "—")[:10])}</td></tr>
    <tr><td><b>Project discussions by source</b></td><td class="sub">{src} (in this selection)</td></tr>
    <tr><td><b>Classified</b></td><td class="sub">{d["classified"]} discussions in the last 100 days, {len(d["items"])} were build activity. Excluded: {escape(excl)}.</td></tr>
    <tr><td><b>Last update issues</b></td><td class="sub">{escape(" · ".join(issues)) or "None"}</td></tr>
    <tr><td><b>Update now</b></td><td>{REFRESH_FORM}</td></tr>
    <tr><td><b>How it's collected</b></td><td class="sub">Each week, the most upvoted or starred posts from: Hacker News “Show HN” (up to
      {S.PER_WEEK["show_hn"]}) and “Launch HN” ({S.PER_WEEK["launch_hn"]}); new GitHub repositories with {S.GH_MIN_STARS}+ stars
      ({S.PER_WEEK["gh_repo"]}); Dev.to #showdev and #buildinpublic ({S.PER_WEEK["devto"]}); Product Hunt launches
      ({S.PER_WEEK["producthunt"]}, {"on" if os.getenv("PRODUCT_HUNT_TOKEN") else "off until PRODUCT_HUNT_TOKEN is set"}).
      Plus up to {S.WAWO_PER_THREAD} replies per “Ask HN: What are you working on?” thread, and DevvIT threads (Hacker News,
      Stack Overflow, GitHub) whose text says the author built or is building something. Reddit isn't collected: its API
      needs an app login. Each discussion is classified once by Gemini; names, stages, quotes and technologies are checked
      against the post text. Star and vote counts are what each site showed when collected.</td></tr>
  </tbody></table></section>"""


FILTER_JS = """<script>
(() => {
  const f = document.querySelector('form[data-bfilter]'); if (!f) return;
  const busy = () => { document.querySelector('.bloading').hidden = false; document.querySelector('.bresults')?.setAttribute('aria-busy', 'true'); };
  f.addEventListener('submit', busy);
  f.querySelectorAll('select').forEach(s => s.addEventListener('change', () => { busy(); f.submit(); }));
})();
document.querySelectorAll('form[data-brefresh]').forEach(r => r.addEventListener('submit', () => {
  const b = r.querySelector('button'); b.disabled = true; b.textContent = 'Updating… keep this tab open';
}));
</script>"""

REFRESH_FORM = ('<form method="post" action="/building/refresh" class="inline" data-brefresh>'
                '<button class="btn" type="submit">Update build activity</button> '
                '<span class="sub">Collects new posts from Hacker News, GitHub, Dev.to and Product Hunt (when connected) '
                'and classifies only discussions not seen before. No brief or email. Can take a few minutes; '
                'anything left over is picked up by the next update.</span></form>')


def building_page(d: dict | None, f: dict, history: list[dict], *, state: str = "ok", error: str | None = None) -> str:
    intro = """
  <div class="fb-eyebrow">Building Now</div>
  <h1 class="fb-h1">What developers are building in public</h1>
  <p class="fb-sub">Side projects, products, prototypes, open-source work and experiments that developers shared on
     Hacker News, Stack Overflow and GitHub, classified by Gemini. Counts are of public discussions: they show what
     people talk about building, not how widely a technology is actually used.</p>"""
    if state != "ok":
        msg = {"migrate": MIGRATION_NOTE,
               "error": f'<div class="note-box err"><b>Building Now couldn\'t load.</b> {escape(error or "The database didn’t respond.")} '
                        'Try again in a minute; if it keeps happening check System health.</div>'}[state]
        return _page("Building Now", f'<main class="fb">{intro}{msg}</main>', active="building", history=history)

    items, shown = d["items"], d["shown"]
    if not items:
        empty = ('<div class="note-box"><b>No build activity stored yet.</b> Click <b>Run now</b> (or wait for the Friday run): '
                 'DevvIT will collect recent Show HN posts and classify them. The first update fills the last four weeks.'
                 f'<p style="margin:10px 0 0">{REFRESH_FORM}</p></div>')
        return _page("Building Now", f'<main class="fb">{_flash(d.get("flash"))}{intro}{empty}{_coverage(d, [])}</main>',
                     active="building", history=history, script=FILTER_JS)

    stale = ('<div class="note-box"><b>This data may be out of date:</b> the last update was '
             f'{escape(_ago(d["fresh"]["last_update"]))}. Click Run now to refresh.</div>' if d["fresh"]["stale"] else "")
    period = next((t for v, t in _PERIODS if v == f.get("days", 30)), "Selected period").lower()
    techs_n = len({t["key"] for it in shown for t in it["techs"] if t["explicit"]})
    with_blockers = sum(1 for it in shown if any(b["explicit"] for b in it["blockers"]))
    kpis = f"""
<div class="kpis">
  <div class="kpi dark"><div class="l">Project discussions</div><div class="v">{len(shown)}</div><div class="s">{escape(period)} · this selection</div></div>
  <div class="kpi"><div class="l">Categories</div><div class="v">{len({it.get("category") for it in shown})}</div><div class="s">top: {escape(d["cats"][0]["label"]) if d["cats"] else "—"}</div></div>
  <div class="kpi"><div class="l">Technologies named</div><div class="v">{techs_n}</div><div class="s">named in posts, not inferred</div></div>
  <div class="kpi"><div class="l">Builders reporting blockers</div><div class="v">{with_blockers}</div><div class="s">quoted in their own post</div></div>
</div>"""
    tt, tc = d["trend_tech"], d["trend_cat"]
    brief_html = _brief(B.brief(shown, tt, tc), f, period)
    trend_note = ("Each week is a complete Friday-to-Thursday week; the current week isn't compared until it ends. "
                  "Growing, declining and new are rules of thumb on discussion counts, not statistical tests, and say nothing "
                  "about real adoption.")
    if not tt["history_ok"]:
        trend_note = ("Trends need at least two complete weeks of stored data. Until then every row shows "
                      "<b>Needs history</b>. " + trend_note)
    emerging = [r for r in tc["rows"] + tt["rows"] if r["status"] in {"new", "growing"}][:8]
    emerging_html = ("".join(f'<a class="chip" href="{escape(_href(f, **({"category": r["key"]} if r in tc["rows"] else {"tech": r["key"]})))}">'
                             f'{escape(r["label"])} <small>{_STATUS[r["status"]][0]}</small></a>' for r in emerging)
                     or '<span class="sub">Nothing is new or growing in the latest complete week.</span>')
    cards = "".join(card(it) for it in d["recent"]) or '<p class="sub">No project discussions match these filters. Try a longer period or clear a filter.</p>'
    body = f"""
<main class="fb">
  {_flash(d.get("flash"))}
  {intro}
  {stale}
  {_filters(f, d["tech_options"])}
  <div class="bresults">
  {brief_html}
  {kpis}
  <div class="row2 even">
    <section class="panel"><h2 class="ph">Most common project categories</h2><p class="sub">Discussions per category in this selection. Click to filter.</p>
      {_blist(d["cats"], f, "category", "No categories in this selection.")}</section>
    <section class="panel"><h2 class="ph">Frequently mentioned technologies</h2><p class="sub">Only technologies named in the post are counted.</p>
      {_blist(d["techs"], f, "tech", "No technologies named in this selection.")}</section>
  </div>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Industry view: what new GitHub repositories are about</h2>
    <p class="sub">Topics and languages listed on new GitHub repositories classified as build activity. Counts are repositories, not
      adoption. Click to filter.</p>
    <div class="row2 even" style="margin-top:6px">
      <div><h3 class="sub-h">Repository topics</h3>{_blist(d.get("topics") or [], f, "tech", "No GitHub repositories in this selection yet.")}</div>
      <div><h3 class="sub-h">Languages</h3>{_blist(d.get("langs") or [], f, "tech", "No languages in this selection.")}</div>
    </div>
    <h3 class="sub-h">Topic trends</h3>{_trend_table(d.get("trend_topic") or {"rows": [], "weeks": [], "totals": []}, f, "tech", "Topic")}</section>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Emerging build categories and technologies</h2>
    <p class="sub">New or growing in the latest complete week compared with the weeks before.</p><div class="chips-row">{emerging_html}</div></section>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Technology and build-trend radar</h2>
    <p class="sub">{trend_note} Week columns show the Friday each week starts; the last row is how many project discussions were stored that week.</p>
    <h3 class="sub-h">Technologies</h3>{_trend_table(tt, f, "tech", "Technology")}
    <h3 class="sub-h">Categories</h3>{_trend_table(tc, f, "category", "Category")}</section>
  {_related(d.get("related"))}
  <section class="panel" style="margin-top:14px"><h2 class="ph">Builder blockers</h2>
    <p class="sub">Problems builders reported in their own words, grouped by type. Each links to the original discussion; a
      <span class="ai-tag">Suggested pain point</span> is a DevvIT pain point sharing at least two words with the blocker.</p>
    {_blockers(d["blockers"], d["labels"])}</section>
  <h2 class="sec-h2">Recently shared projects <small class="sub">showing {len(d["recent"])} of {len(shown)}</small></h2>
  <div class="bcards">{cards}</div>
  {_coverage(d, shown)}
  </div>
</main>"""
    return _page("Building Now", body, active="building", history=history, script=FILTER_JS)


def build_panel(rows: list[dict], label: str) -> str:
    """'Related build activity' section for a pain point or opportunity page."""
    if rows is None:
        return ""
    items = "".join(
        f'<li><a href="{escape(r["item"].get("discussion_url") or "#")}" target="_blank" rel="noopener noreferrer">'
        f'{escape(r["item"].get("project_title") or r["item"].get("title_raw") or "discussion")}</a> '
        f'<span class="sub">· {escape((r["item"].get("posted_at") or "")[:10])} · {escape(r["basis"])}</span>'
        + (' <span class="ai-tag">Suggested link</span>' if r["suggested"] else "") + "</li>" for r in rows[:10])
    body = (f'<ul class="plain">{items}</ul>' if items else
            '<p class="sub">No stored build discussion is connected to this pain point.</p>')
    return (f'<section class="panel" style="margin-top:14px"><h2 class="ph">Related build activity <small class="sub">{len(rows)}</small></h2>'
            f'<p class="sub">Developers sharing what they build who ran into this. <a href="/building">Building Now →</a></p>{body}</section>')
