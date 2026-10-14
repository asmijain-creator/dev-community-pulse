"""Pages for the intelligence features: Emerging radar, Opportunity explorer, Data quality.

Reuses the shell and helpers from lib.views so everything keeps the DevvIT design.
"""
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

from lib.evidence import engagement
from lib.scoring import FACTORS
from lib.views import _chg, _flash, _nice, _page, _point_href, _spark, _week_no, _ago, _src
from lib.views_share import select_box, share_btn
from lib.workspace import STATUSES

MIGRATION_NOTE = ('<div class="note-box">Saving is switched off until the database update has been applied: '
                  'run <code>supabase/migrations/002_research_workspace.sql</code> once in Supabase → SQL Editor.</div>')
_KIND = {"new": ("New theme", "up"), "rising": ("Rising", "up"), "returning": ("Back again", "mid"),
         "baseline_pending": ("Needs a baseline", "flat")}
_EV = {"Strong": "ok", "Moderate": "mid", "Thin": "bad"}


def _thread_link(t: dict) -> str:
    label, cls = _src(t.get("source"))
    url = t.get("url") or ""
    href = escape(url) if url.startswith(("https://", "http://")) else "#"
    dup = f' · {t["duplicates"]} near-duplicate{"s" if t["duplicates"] != 1 else ""} merged' if t.get("duplicates") else ""
    state = '<span class="st-open">Unresolved</span>' if t.get("is_unresolved") else '<span class="st-done">Resolved</span>'
    return (f'<a class="ev" href="{href}" target="_blank" rel="noopener noreferrer"><span class="schip {cls}">{escape(label)}</span>'
            f'<b>{escape(t.get("title") or "Untitled thread")}</b>'
            f'<span class="mono">{escape((t.get("created_at") or "")[:10])} · ▲ {t.get("score") or 0} · '
            f'{t.get("comments") or 0} comments{dup}</span>{state}</a>')


def _sources(srcs: list[str]) -> str:
    return "".join(f'<span class="schip {_src(s)[1]}">{escape(_src(s)[0])}</span>' for s in srcs)


# ======================= Emerging radar =======================
def radar_page(res: dict, categories: dict, history: list[dict], saving: bool, flash: str | None,
               show_dismissed: bool) -> str:
    latest = res.get("latest")
    findings = res["findings"]
    hidden = [f for f in findings if f["status"] == "dismissed"]
    shown = findings if show_dismissed else [f for f in findings if f["status"] != "dismissed"]
    base_n = len(res["baseline_weeks"])
    compare = (f"Each theme is compared with its own average over the previous {base_n} week{'s' if base_n != 1 else ''} with a brief."
               if base_n else "Once there are two or more weekly briefs, each theme is compared with its own average over earlier weeks.")
    method = (f"{compare} Similar labels are merged into one theme and near-duplicate threads are counted once. "
              f"These are rules of thumb that point at things worth reading, not statistical tests.")
    pending = ("" if res["history_ok"] else
               '<div class="note-box">There is only one weekly brief so far, so nothing can be called <b>rising</b> yet. '
               'The themes below are listed with their evidence; comparisons start after the next Friday brief.</div>')

    cards = ""
    for f in shown:
        kind, kcls = _KIND[f["kind"]]
        cat = categories.get(f["label"], "")
        status = ({"relevant": '<span class="cov mid">Marked relevant</span>',
                   "monitored": '<span class="cov bad">Monitored</span>',
                   "dismissed": '<span class="cov ok">Dismissed</span>'}.get(f["status"], ""))
        base = "—" if f["baseline"] is None else f"{f['baseline']:.1f}/wk"
        merged = (f'<p class="sub">Merged labels: {escape(", ".join(f["members"]))}</p>' if len(f["members"]) > 1 else "")
        actions = ""
        if saving:
            hidden_in = (f'<input type="hidden" name="key" value="{escape(f["key"])}">'
                         f'<input type="hidden" name="label" value="{escape(f["label"])}">'
                         f'<input type="hidden" name="first_seen" value="{escape(f["first_seen"])}">'
                         f'<input type="hidden" name="category" value="{escape(cat)}">')
            btn = lambda action, text, cls="btn": (f'<form method="post" action="/radar/action" class="inline">{hidden_in}'
                                                   f'<input type="hidden" name="action" value="{action}">'
                                                   f'<button class="{cls}" type="submit">{text}</button></form>')
            actions = ('<div class="r-actions">'
                       + (btn("new", "Restore") if f["status"] == "dismissed" else
                          btn("relevant", "Mark relevant") + btn("monitored", "Add to monitored topics") + btn("dismissed", "Dismiss"))
                       + '</div>')
        cards += f"""
<article class="rcard">
  <div class="r-top"><span class="chg {kcls}">{kind}</span>{status}
    <a class="r-title" href="{_point_href(f['label'], latest)}">{escape(_nice(f['label']))}</a>
    <span class="r-cat">{escape(cat)}</span></div>
  <div class="r-grid">
    <div><span>First observed</span><b>{escape(f['first_seen'])}</b></div>
    <div><span>This week</span><b>{f['current']}</b></div>
    <div><span>Baseline</span><b>{base}</b></div>
    <div><span>Trend</span>{_spark(f['series']) if len(f['series']) > 1 else '<b>—</b>'}</div>
    <div><span>Independent threads</span><b>{f['unique_threads']}</b>{f'<small>+{f["duplicates_merged"]} duplicates merged</small>' if f['duplicates_merged'] else ''}</div>
    <div><span>Evidence</span><b><span class="cov {_EV[f['evidence']['level']]}">{f['evidence']['level']}</span></b><small>{escape(f['evidence']['why'])}</small></div>
  </div>
  <p class="r-why"><b>Why it was flagged.</b> {escape(f['reason'])}</p>
  <p class="r-why"><b>Suggested next step.</b> {escape(f['next_step'])}</p>
  <div class="r-src"><span class="sub">Sources</span>{_sources(f['sources'])}</div>
  {merged}
  <div class="evs">{''.join(_thread_link(t) for t in f['threads'][:3])}</div>
  {actions}
</article>"""
    if not cards:
        cards = ('<div class="panel"><h2>No emerging signals this week</h2><p class="sub">Nothing has at least '
                 f'{2} independent threads and an unusual change against its baseline.</p></div>')
    toggle = (f'<a class="more" href="/radar{"" if show_dismissed else "?dismissed=1"}">'
              f'{"Hide" if show_dismissed else "Show"} {len(hidden)} dismissed</a>' if hidden else "")
    body = f"""
<main class="fb">
  {_flash(flash)}
  <div class="fb-eyebrow">Emerging radar{f" · Week {_week_no(latest)}" if latest else ""}</div>
  <h1 class="fb-h1">What's starting to move</h1>
  <p class="fb-sub">{escape(method)} For new and growing technologies and project categories among what developers
     are building, see <a href="/building?theme=emerging">Building Now → Emerging</a>.</p>
  {pending}{'' if saving else MIGRATION_NOTE}
  <div class="sec-h"><div><h2>{len(shown)} signal{'s' if len(shown) != 1 else ''}</h2></div>{toggle}</div>
  <section class="rcards">{cards}</section>
</main>"""
    return _page("Emerging radar", body, active="radar", history=history, current_week=latest)


# ======================= Opportunity explorer =======================
def _bar(v: float | None) -> str:
    if v is None:
        return '<span class="fbar na" title="Not available yet: needs an earlier brief">—</span>'
    return f'<span class="fbar" title="{v:.2f}"><i><u style="width:{v * 100:.0f}%"></u></i><em>{v:.2f}</em></span>'


def _weights_form(weights: dict) -> str:
    rows = "".join(
        f'<label class="wt"><span>{k.capitalize()}</span>'
        f'<input type="range" name="w_{k}" min="0" max="3" step="0.5" value="{weights[k]:g}" '
        f'oninput="this.nextElementSibling.textContent=this.value"><output>{weights[k]:g}</output>'
        f'<small>{escape(desc)}</small></label>' for k, desc in FACTORS.items())
    return (f'<details class="panel weights"><summary><b>Score weights</b> <span class="sub">'
            f'{" · ".join(f"{k} ×{weights[k]:g}" for k in FACTORS)}</span></summary>'
            f'<form method="get" action="/opportunities" class="wt-form">{rows}'
            f'<div class="fb-btns"><button class="btn btn-primary" type="submit">Apply weights</button>'
            f'<a class="btn" href="/opportunities">Reset</a></div></form></details>')


def opportunities_page(rows: list[dict], weights: dict, latest: str | None, history: list[dict], saving: bool,
                       has_baseline: bool) -> str:
    qs = "".join(f"&w_{k}={weights[k]:g}" for k in FACTORS)
    body_rows = ""
    for i, r in enumerate(rows, 1):
        f = r["factors"]
        st = r.get("status")
        href = f"/opportunity?name={quote(r['name'])}{escape(qs)}"
        score_txt = "—" if r["score"] is None else format(r["score"], ".0f")
        status_html = f'<span class="cov mid">{escape(st)}</span>' if st else '<span class="sub">—</span>'
        body_rows += (
            f'<tr data-href="{href}"><td class="sel">{select_box("opportunity", r["name"])}</td><td class="idx">{i:02d}</td>'
            f'<td class="tn"><a href="{href}"><b>{escape(_nice(r["name"]))}</b></a><small>{escape(r["category"])}</small></td>'
            f'<td class="num"><span class="score">{score_txt}</span></td>'
            + "".join(f"<td>{_bar(f[k])}</td>" for k in FACTORS)
            + f'<td class="mono small">{f["_threads"]} thr · {len(f["_sources"])} src</td>'
            + f'<td>{status_html}</td><td>{share_btn("opportunity", r["name"])}</td></tr>')
    table = (f"""<div class="panel" style="margin-top:14px"><div class="rank-wrap"><table class="rank" id="rank">
  <thead><tr><th><span class="sr">Select</span></th><th>#</th><th>Pain point</th><th class="num">Score</th>{''.join(f'<th title="{escape(d)}">{k}</th>' for k, d in FACTORS.items())}
  <th>Evidence</th><th>Status</th><th></th></tr></thead><tbody>{body_rows}</tbody></table></div></div>"""
             if rows else '<div class="panel"><p class="sub">No pain points in the latest brief yet.</p></div>')
    body = f"""
<main class="fb">
  <div class="fb-eyebrow">Opportunity explorer{f" · Week {_week_no(latest)}" if latest else ""}</div>
  <h1 class="fb-h1">Where to look next</h1>
  <p class="fb-sub">Every pain point from the latest brief, scored on five factors you can see and re-weight.
     Open one for its evidence, an AI analysis grounded in its threads, and to track its status. Tick several to share them in one report.</p>
  <div class="note-box">Scores rank where to look first. Discussion volume is <b>not</b> evidence of willingness to pay or market size.
    {'' if has_baseline else ' Growth is left out until a second weekly brief exists.'}</div>
  {'' if saving else MIGRATION_NOTE}
  {_weights_form(weights)}
  {table}
</main>"""
    return _page("Opportunity explorer", body, active="opps", history=history, current_week=latest, script=ROW_LINK_JS)


ROW_LINK_JS = """<script>
document.querySelectorAll('tr[data-href]').forEach(r => r.addEventListener('click', e => {
  if (!e.target.closest('a,button,form,input,label')) location.href = r.dataset.href;
}));
</script>"""


def _claims(items: list[dict]) -> str:
    if not items:
        return '<p class="sub">Not enough evidence in the threads.</p>'
    out = ""
    for it in items:
        links = " ".join(f'<a href="{escape(e["url"]) if e["url"].startswith(("https://", "http://")) else "#"}" '
                         f'target="_blank" rel="noopener noreferrer" title="{escape(e["title"])}">[{j}]</a>'
                         for j, e in enumerate(it["evidence"], 1))
        out += f"<li>{escape(it['text'])} <span class='cite'>{links}</span></li>"
    return f"<ul class='claims'>{out}</ul>"


def opportunity_page(name: str, category: str, latest: str, weeks: list[str], series: list[int], f: dict,
                     score: float | None, weights: dict, status_row: dict | None, log: list[dict],
                     insight: dict | None, threads: list[dict], mix: dict, saving: bool, flash: str | None,
                     history: list[dict], extra: str = "") -> str:
    factor_rows = "".join(
        f'<div class="frow"><span>{k.capitalize()} <small>×{weights[k]:g}</small></span>{_bar(f[k])}'
        f'<small>{escape(d)}</small></div>' for k, d in FACTORS.items())
    cur, prev = (series[-1] if series else 0), (series[-2] if len(series) > 1 else None)
    neg = mix["negative"]
    n = f["_threads"]
    eng = sorted(engagement(t) for t in threads)
    facts = f"""
<div class="kpis">
  <div class="kpi"><div class="l">Mentions this week</div><div class="v">{cur} {_chg(cur, prev)}</div><div class="s">{len(weeks)}-week trend below</div></div>
  <div class="kpi"><div class="l">Independent threads</div><div class="v">{n}</div><div class="s">{len(f['_sources'])} source{'s' if len(f['_sources']) != 1 else ''}, near-duplicates merged</div></div>
  <div class="kpi"><div class="l">Negative threads</div><div class="v">{neg} <small>of {n}</small></div><div class="s">{'Developers disagree: mixed opinions' if mix['mixed'] else 'Sentiment from the tagger'}</div></div>
  <div class="kpi"><div class="l">Median engagement</div><div class="v">{eng[len(eng) // 2] if eng else 0}</div><div class="s">votes + comments per thread</div></div>
</div>"""
    st = (status_row or {}).get("status", "")
    options = "".join(f'<option{" selected" if s == (st or "New") else ""}>{s}</option>' for s in STATUSES)
    log_html = "".join(f'<li><span class="mono">{escape((e.get("created_at") or "")[:16].replace("T", " "))}</span> '
                       f'{escape(e.get("status") and "Status → " + e["status"] or e.get("note") or "")}</li>' for e in log)
    track = (f"""<form method="post" action="/opportunity/save" class="track">
  <input type="hidden" name="name" value="{escape(name)}">
  <label class="field"><span>Status</span><select name="status">{options}</select></label>
  <label class="field" style="flex:1"><span>Private notes</span><textarea name="notes" rows="3" placeholder="What you've learned, who to talk to…">{escape((status_row or {}).get("notes", ""))}</textarea></label>
  <button class="btn btn-primary" type="submit">{"Save" if status_row else "Save to opportunities"}</button>
</form><p class="sub">Notes are not included in shared reports.</p>
{f"<ul class='log'>{log_html}</ul>" if log_html else ""}""" if saving else MIGRATION_NOTE)

    if insight:
        ai = f"""
<p class="ai-label">AI analysis · Gemini · grounded in {insight.get('threads_used', 0)} threads · generated {escape(str(insight.get('_created_at', ''))[:10])}.
  Every finding below links the threads it came from; findings without a source were removed.</p>
<h3>Problem statement</h3><p>{escape(insight.get('problem_statement') or '—')}</p>
<div class="ai-grid">
  <div><h3>Who is affected</h3>{_claims(insight.get('segment', []))}</div>
  <div><h3>What developers use today</h3>{_claims(insight.get('existing_solutions', []))}</div>
  <div><h3>Where those fall short</h3>{_claims(insight.get('limitations', []))}</div>
  <div><h3>Unmet needs</h3>{_claims(insight.get('unmet_needs', []))}</div>
</div>
<p class="ai-label">AI suggestions (ideas to test, not evidence)</p>
<div class="ai-grid">
  <div><h3>Experiments to try</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in insight.get('experiments', [])) or '<li>—</li>'}</ul></div>
  <div><h3>Questions for interviews</h3><ul>{''.join(f'<li>{escape(x)}</li>' for x in insight.get('interview_questions', [])) or '<li>—</li>'}</ul></div>
</div>"""
    else:
        ai = '<p class="sub">No analysis yet. It reads this pain point\'s threads with Gemini and is saved, so it is only generated once per week.</p>'
    gen = (f"""<form method="post" action="/opportunity/analyze" data-run-ai><input type="hidden" name="name" value="{escape(name)}">
  <button class="btn" type="submit">{'Regenerate analysis' if insight else 'Generate analysis'}</button>
  <span class="sub">Uses Gemini · about 10 seconds</span></form>""" if saving else "")
    body = f"""
<main class="fb">
  {_flash(flash)}
  <a class="back" href="/opportunities">← Opportunity explorer</a>
  <div class="pp-head"><h1 class="fb-h1">{escape(_nice(name))}</h1>{share_btn("opportunity", name)}
    <div class="score-big"><span>Score</span><b>{'—' if score is None else f'{score:.0f}'}</b></div></div>
  <p class="fb-sub"><span class="u-cat">{escape(category)}</span>{' · <b>' + escape(st) + '</b>' if st else ''} ·
     <a class="more" style="margin:0" href="{_point_href(name, latest)}">Pain point history &amp; threads →</a></p>
  <h2 class="sec-h2">Evidence</h2>
  {facts}
  <div class="row2">
    <div class="panel"><h2 class="ph">Score breakdown</h2><p class="sub">Weighted average of the factors (0-1). Change weights on the explorer page.</p>{factor_rows}</div>
    <div class="panel"><h2 class="ph">Mentions per week</h2>{_spark(series) if len(series) > 1 else '<p class="sub">One week of data so far.</p>'}
      <p class="sub">{' · '.join(f'W{_week_no(w)}: {v}' for w, v in zip(weeks, series))}</p></div>
  </div>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Track this opportunity</h2>{track}</section>
  <section class="panel" style="margin-top:14px"><div class="panel-h"><h2>AI analysis</h2>{gen}</div>{ai}</section>
  <h2 class="sec-h2">Threads behind it <small>{n}</small></h2>
  <div class="evs">{''.join(_thread_link(t) for t in threads[:20]) or '<p class="sub">No threads stored.</p>'}</div>
  {extra}
</main>"""
    return _page(_nice(name), body, active="opps", history=history, current_week=latest, script=AI_BUSY_JS)


AI_BUSY_JS = """<script>
document.querySelectorAll('form[data-run-ai]').forEach(f => f.addEventListener('submit', () => {
  const b = f.querySelector('button'); b.disabled = true; b.textContent = 'Analysing threads…';
}));
</script>"""


# ======================= Data quality =======================
def evidence_page(d: dict, history: list[dict]) -> str:
    def row(ok, label, detail):
        cls = {True: "on", False: "bad", None: ""}[ok]
        word = {True: "OK", False: "Check", None: "Info"}[ok]
        return (f'<tr><td><span class="status {cls}">{word}</span></td><td><b>{escape(label)}</b></td>'
                f'<td class="sub">{detail}</td></tr>')

    fresh = d["freshness_days"]
    runs = "".join(
        f'<tr><td class="mono">{escape((r.get("started_at") or "")[:16].replace("T", " "))}</td><td>{escape(r.get("trigger") or "")}</td>'
        f'<td><span class="cov {"ok" if r.get("status") == "success" else "bad" if r.get("status") == "failed" else "mid"}">{escape(r.get("status") or "")}</span></td>'
        f'<td class="sub">{escape(_run_summary(r))}</td></tr>' for r in d["runs"])
    cov = "".join(row(c["posts"] > 0 and not c["failed"], c["label"],
                      f'{c["posts"]} threads this week' + (f' · {c["failed"]} of {c["queries"]} searches failed in the last run' if c.get("queries") else ""))
                  for c in d["coverage"])
    dup = "".join(f'<li><b>{escape(_nice(p))}</b>: {m} near-duplicate{"s" if m != 1 else ""} merged</li>' for p, m in d["dupes"]) \
        or "<li>No near-duplicates found this week.</li>"
    thin = ", ".join(escape(_nice(p)) for p in d["thin"][:30]) or "None"
    mixed = "".join(f'<li><a href="{_point_href(p, d["latest"])}">{escape(_nice(p))}</a>: {m["positive"]} positive, {m["negative"]} negative</li>'
                    for p, m in d["mixed"]) or "<li>No pain point has clearly conflicting opinions.</li>"
    body = f"""
<main class="fb">
  <div class="fb-eyebrow">Data quality{f" · Week {_week_no(d['latest'])}" if d['latest'] else ""}</div>
  <h1 class="fb-h1">Can you trust this week's numbers?</h1>
  <p class="fb-sub">Checks on the data behind every metric: how fresh it is, which sources delivered, what was merged as
     duplicate, and which conclusions rest on too little evidence. Counts on DevvIT are of threads; comments inside a
     thread are never counted as separate confirmation.</p>
  <section class="panel" style="margin-top:24px"><h2 class="ph">Freshness and coverage</h2>
    <table class="qtab"><tbody>
      {row(fresh is not None and fresh <= 8, "Latest brief", "No brief yet" if fresh is None else f"{d['latest']} · generated {fresh} day{'s' if fresh != 1 else ''} ago" + (" · older than a week: the Friday run may have failed" if fresh > 8 else ""))}
      {cov}
      {row(None, "Classification", f"{d['other']} of {d['total']} threads this week were tagged 'Other' (the tagger couldn't match a category). The tagger doesn't give a confidence score, so uncertainty beyond that can't be shown.")}
    </tbody></table></section>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Run log</h2>
    {f'<table class="qtab"><tbody>{runs}</tbody></table>' if runs else '<p class="sub">No runs logged yet. Runs are logged once the database update (migration 002) is applied; the next run will appear here.</p>'}</section>
  <div class="row2">
    <section class="panel"><h2 class="ph">Near-duplicates merged</h2><p class="sub">Reposts and threads with nearly identical titles count once.</p><ul class="plain">{dup}</ul></section>
    <section class="panel"><h2 class="ph">Conflicting opinions</h2><p class="sub">Pain points with both positive and negative threads.</p><ul class="plain">{mixed}</ul></section>
  </div>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Low-evidence pain points <small class="sub">{len(d['thin'])}</small></h2>
    <p class="sub">Only one independent thread this week: treat these as leads, not findings.</p><p>{thin}</p></section>
</main>"""
    return _page("Data quality", body, active="quality", history=history, current_week=d["latest"])


def _run_summary(r: dict) -> str:
    s = r.get("stats") or {}
    if r.get("error"):
        return f"Error: {r['error'][:140]}"
    parts = []
    if "collected" in s:
        parts.append(f"{s['collected']} collected")
    if "tagged" in s:
        parts.append(f"{s['tagged']} tagged")
    if "pain_points" in s:
        parts.append(f"{s['pain_points']} pain points")
    src = s.get("sources") or {}
    failed = sum(v.get("failed", 0) for v in src.values())
    if failed:
        parts.append(f"{failed} source searches failed")
    if r.get("finished_at") and r.get("started_at"):
        try:
            a = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
            b = datetime.fromisoformat(r["finished_at"].replace("Z", "+00:00"))
            parts.append(f"{int((b - a).total_seconds())}s")
        except ValueError:
            pass
    return " · ".join(parts) or "—"
