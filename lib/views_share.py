"""Share feature pages: the Share dialog, the public read-only report, the report builder and link management.

The public report page (/r/<token>) is rendered only from the stored snapshot, has no navigation, no Ask
DevvIT, no Run now and no forms, and is marked noindex.
"""
import re
from html import escape
from urllib.parse import quote

import markdown as md

from lib.sharing import KINDS, VISIBILITY
from lib.views import BASE_CSS, FAVICON, _flash, _ist_label, _page

# ---------- Share dialog (on every DevvIT page) ----------
def share_btn(kind: str, name: str, label: str = "Share") -> str:
    return (f'<button type="button" class="sharebtn" data-share-kind="{kind}" data-share-name="{escape(name)}" '
            f'title="Share">{label}</button>')


def select_box(kind: str, name: str) -> str:
    return (f'<label class="selbox" title="Add to a combined report"><input type="checkbox" data-sel-kind="{kind}" '
            f'data-sel-name="{escape(name)}"><span class="sr">Select for report</span></label>')


SHARE_WIDGET = """
<div class="shbox" id="shbox" hidden>
  <div class="sh-card" role="dialog" aria-modal="true" aria-labelledby="sh-t">
    <div class="sh-h"><div><span class="fb-eyebrow" id="sh-kind">Share</span><h2 id="sh-t">Share</h2></div>
      <button type="button" class="sh-x" data-sh-close aria-label="Close">×</button></div>
    <div class="sh-opt">
      <button type="button" class="btn" id="sh-copy">Copy summary</button>
      <p>A short text summary with source links, ready for Slack, WhatsApp, email or a planning doc.</p>
    </div>
    <form class="sh-opt" method="post" action="/share/create" id="sh-form">
      <input type="hidden" name="kind"><input type="hidden" name="name"><input type="hidden" name="w">
      <button type="submit" class="btn btn-primary">Create shareable link</button>
      <p>A read-only snapshot of this page as it is now. It won't change when DevvIT's data changes. Needs the admin password.</p>
      <div class="sh-row">
        <label><input type="radio" name="visibility" value="unlisted" checked> Unlisted link</label>
        <label><input type="radio" name="visibility" value="private"> Private</label>
        <label class="sh-exp">Expires <select name="expires"><option value="never">Never</option><option value="1">In 1 day</option>
          <option value="7">In 7 days</option><option value="30" selected>In 30 days</option><option value="90">In 90 days</option></select></label>
      </div>
      <p class="sh-note" data-vis-note>Anyone with an unlisted link can open it, and recipients can forward it. Private reports open only with the admin password.</p>
    </form>
    <div class="sh-opt">
      <a class="btn" id="sh-print" target="_blank" rel="noopener">Export / print</a>
      <p>Opens a print-friendly page. Use your browser's Print → Save as PDF.</p>
    </div>
    <div class="sh-opt">
      <button type="button" class="btn" id="sh-add">Add to combined report</button>
      <p id="sh-add-note">Collect several pain points and opportunities, then create one report.</p>
    </div>
    <div class="sh-foot"><button type="button" class="btn" data-sh-close>Cancel</button><span class="sh-msg" id="sh-msg" role="status"></span></div>
  </div>
</div>
<div class="selbar" id="selbar" hidden><span id="selbar-n"></span>
  <a class="btn btn-primary" id="selbar-go" href="/reports/new">Create report</a>
  <button type="button" class="btn" id="selbar-clear">Clear</button></div>
<script>
(() => {
  const KEY = 'devvit-report-sel';
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; } };
  const store = l => { try { localStorage.setItem(KEY, JSON.stringify(l)); } catch (e) {} };
  const has = (l, k, n) => l.some(x => x.kind === k && x.name === n);
  const bar = document.getElementById('selbar');
  const sync = () => {
    const l = load();
    document.querySelectorAll('[data-sel-kind]').forEach(c => { c.checked = has(l, c.dataset.selKind, c.dataset.selName); });
    bar.hidden = !l.length || location.pathname.startsWith('/reports/new');
    const p = l.filter(x => x.kind === 'pain_point').length, o = l.length - p;
    document.getElementById('selbar-n').textContent = 'Report: ' + [p && p + ' pain point' + (p > 1 ? 's' : ''), o && o + ' opportunit' + (o > 1 ? 'ies' : 'y')].filter(Boolean).join(', ');
    document.getElementById('selbar-go').href = '/reports/new?' + l.map(x => (x.kind === 'pain_point' ? 'pp=' : 'op=') + encodeURIComponent(x.name)).join('&');
  };
  const toggle = (k, n) => { let l = load(); l = has(l, k, n) ? l.filter(x => !(x.kind === k && x.name === n)) : [...l, { kind: k, name: n }]; store(l); sync(); };
  document.addEventListener('change', e => { const c = e.target.closest('[data-sel-kind]'); if (c) toggle(c.dataset.selKind, c.dataset.selName); });
  document.addEventListener('click', e => { if (e.target.closest('.selbox')) e.stopPropagation(); }, true);
  document.getElementById('selbar-clear').addEventListener('click', () => { store([]); sync(); });
  window.devvitClearSelection = () => { store([]); sync(); };

  const box = document.getElementById('shbox'), msg = document.getElementById('sh-msg'), form = document.getElementById('sh-form');
  let cur = null;
  const say = (t, bad) => { msg.textContent = t; msg.className = 'sh-msg' + (bad ? ' bad' : ' ok'); };
  const open = (k, n) => {
    cur = { k, n }; msg.textContent = '';
    document.getElementById('sh-kind').textContent = { pain_point: 'Share pain point', opportunity: 'Share opportunity', weekly: 'Share weekly report' }[k] || 'Share';
    document.getElementById('sh-t').textContent = k === 'weekly' ? 'Developer intelligence report, week of ' + n : n.charAt(0).toUpperCase() + n.slice(1);
    form.kind.value = k; form.name.value = n; form.w.value = k === 'opportunity' ? location.search : '';
    document.getElementById('sh-print').href = '/share/print?kind=' + k + '&name=' + encodeURIComponent(n) + (k === 'opportunity' ? '&w=' + encodeURIComponent(location.search) : '');
    const add = document.getElementById('sh-add');
    add.parentElement.hidden = k === 'weekly';
    add.textContent = has(load(), k, n) ? 'Remove from combined report' : 'Add to combined report';
    box.hidden = false; document.getElementById('sh-copy').focus();
  };
  const close = () => { box.hidden = true; cur = null; };
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-share-kind]');
    if (b) { e.preventDefault(); e.stopPropagation(); open(b.dataset.shareKind, b.dataset.shareName); return; }
    if (e.target.closest('[data-sh-close]') || e.target === box) close();
  }, true);
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !box.hidden) close(); });
  form.addEventListener('change', () => {
    form.querySelector('[data-vis-note]').textContent = form.visibility.value === 'private'
      ? 'Private: the link opens only with the admin password. Nobody else can view it.'
      : 'Anyone with an unlisted link can open it, and recipients can forward it. Private reports open only with the admin password.';
  });
  document.getElementById('sh-add').addEventListener('click', () => {
    toggle(cur.k, cur.n);
    const on = has(load(), cur.k, cur.n);
    document.getElementById('sh-add').textContent = on ? 'Remove from combined report' : 'Add to combined report';
    say(on ? 'Added. Use “Create report” at the bottom of the page when you are ready.' : 'Removed from the report.');
  });
  document.getElementById('sh-copy').addEventListener('click', async () => {
    say('Preparing summary…');
    try {
      const r = await fetch('/api/share/summary?kind=' + cur.k + '&name=' + encodeURIComponent(cur.n) + (cur.k === 'opportunity' ? '&w=' + encodeURIComponent(location.search) : ''));
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || 'The summary could not be built.');
      await navigator.clipboard.writeText(j.text);
      say('Summary copied to the clipboard.');
    } catch (err) { say((err && err.message && !/denied|NotAllowed/i.test(err.name + err.message) ? err.message : 'Couldn’t copy: your browser blocked clipboard access.'), true); }
  });
  window.devvitCopy = async (text, el) => {
    try { await navigator.clipboard.writeText(text); el.textContent = 'Copied'; el.classList.add('ok'); }
    catch (e) { el.textContent = 'Couldn’t copy: select the link and copy it manually'; el.classList.add('bad'); }
  };
  sync();
})();
</script>"""

SHARE_CSS = """
  /* ---------- share ---------- */
  .sharebtn { border: 1px solid var(--border); background: var(--surface); color: var(--text-2); border-radius: 999px; padding: 4px 11px;
              font: inherit; font-size: 12px; cursor: pointer; white-space: nowrap; }
  .sharebtn:hover { color: var(--text); background: var(--hover); }
  .selbox { display: inline-flex; align-items: center; cursor: pointer; padding: 4px; }
  .selbox input { width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer; }
  .shbox { position: fixed; inset: 0; z-index: 80; background: rgba(15, 15, 18, .45); display: grid; place-items: center; padding: 16px; }
  .shbox[hidden] { display: none; }
  .sh-card { width: min(560px, 100%); max-height: calc(100vh - 32px); overflow: auto; background: var(--surface); border-radius: 16px;
             border: 1px solid var(--border); box-shadow: 0 24px 64px rgba(0,0,0,.25); padding: 22px 24px; }
  .sh-h { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
  .sh-h h2 { margin: 4px 0 12px; font-size: 20px; font-weight: 600; line-height: 1.3; }
  .sh-x { border: 0; background: transparent; font-size: 24px; line-height: 1; cursor: pointer; color: var(--text-3); }
  .sh-opt { padding: 12px 0; border-top: 1px solid var(--border-soft); }
  .sh-opt p { margin: 6px 0 0; font-size: var(--fs-sm); color: var(--text-3); line-height: 1.5; }
  .sh-row { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; margin-top: 10px; font-size: var(--fs-sm); }
  .sh-row select { font: inherit; font-size: var(--fs-sm); padding: 4px 8px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text); }
  .sh-note { font-size: 12px !important; }
  .sh-foot { display: flex; gap: 12px; align-items: center; padding-top: 12px; border-top: 1px solid var(--border-soft); }
  .sh-msg { font-size: var(--fs-sm); } .sh-msg.ok { color: var(--green); } .sh-msg.bad { color: var(--red); }
  .selbar { position: fixed; left: 50%; transform: translateX(-50%); bottom: 20px; z-index: 60; display: flex; gap: 10px; align-items: center;
            background: var(--ink); color: var(--bg); padding: 10px 12px 10px 18px; border-radius: 999px; box-shadow: 0 12px 32px rgba(0,0,0,.25);
            font-size: var(--fs-sm); max-width: calc(100vw - 32px); }
  .selbar[hidden] { display: none; }
  .selbar .btn { padding: 6px 12px; }
  .rep-items { list-style: none; padding: 0; margin: 12px 0 0; display: grid; gap: 10px; }
  .rep-item { border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; background: var(--surface); }
  .rep-item-h { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .rep-item-h b { flex: 1; min-width: 160px; }
  .rep-item details { margin-top: 8px; font-size: var(--fs-sm); }
  .rep-form .field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-3); margin-top: 12px; }
  .rep-form input[type=text], .rep-form textarea, .rep-form select, .rep-form input[type=date] { font: inherit; font-size: var(--fs-md); padding: 9px 11px;
       border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text); }
  .rep-form textarea { min-height: 110px; line-height: 1.5; }
  .linkbox { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 10px; }
  .linkbox input { flex: 1; min-width: 220px; font-family: var(--mono); font-size: 12px; padding: 9px 11px; border: 1px solid var(--border);
                   border-radius: 8px; background: var(--bg); color: var(--text); }
  .copied.ok { color: var(--green); } .copied.bad { color: var(--red); } .copied { font-size: var(--fs-sm); }
  .reptab { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
  .reptab th { text-align: left; font-weight: 500; font-size: 11px; color: var(--text-3); font-family: var(--mono); padding: 8px; border-bottom: 1px solid var(--border); }
  .reptab td { padding: 10px 8px; border-bottom: 1px solid var(--border-soft); vertical-align: top; }
  .reptab form { display: inline; }
  @media (max-width: 680px) { .reptab thead { display: none; } .reptab td { display: block; padding: 4px 8px; border: 0; }
                              .reptab tr { display: block; border-bottom: 1px solid var(--border); padding: 8px 0; } }
"""


# ---------- rendering a snapshot ----------
def _ext(url: str, text: str) -> str:
    return f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer nofollow">{escape(text)}</a>'


def _threads(threads: list[dict]) -> str:
    if not threads:
        return '<p class="r-muted">No source links are stored for this item.</p>'
    return "<ol class=\"r-threads\">" + "".join(
        f'<li>{_ext(t["url"], t["title"])}<span>{escape(t["source"])} · {escape(t["date"] or "date unavailable")} · '
        f'▲ {t["score"]} · {t["comments"]} comments{" · unresolved" if t.get("unresolved") else ""}</span></li>'
        for t in threads) + "</ol>"


def _claims(items: list[dict]) -> str:
    return "<ul>" + "".join(
        f'<li>{escape(c["text"])} ' + " ".join(f'<a class="r-cite" href="{escape(e["url"])}" target="_blank" rel="noopener noreferrer nofollow" '
                                             f'title="{escape(e["title"])}">[{i}]</a>' for i, e in enumerate(c["evidence"], 1)) + "</li>"
        for c in items) + "</ul>"


def _fact(label: str, value: str, note: str = "") -> str:
    return f'<div class="r-fact"><span>{escape(label)}</span><b>{value}</b>{f"<small>{escape(note)}</small>" if note else ""}</div>'


def _bars(series: list[dict]) -> str:
    if len(series) < 2:
        return ""
    top = max(s["mentions"] for s in series) or 1
    return ('<div class="r-bars" aria-label="Mentions per week">' + "".join(
        f'<div title="Week of {escape(s["week"])}: {s["mentions"]}"><i style="height:{max(4, s["mentions"] * 100 / top):.0f}%"></i>'
        f'<b>{s["mentions"]}</b><span>{escape(s["week"][5:])}</span></div>' for s in series) + "</div>")


def _pain_point(s: dict, solo: bool) -> str:
    trend = {"up": "▲ Up", "down": "▼ Down", "flat": "No change", None: "First week"}[s["trend"]]
    observed = (f'{escape(s["first_observed"])} to {escape(s["last_observed"])}' if s.get("first_observed") else "Unavailable")
    ai = ""
    if s.get("ai_problem") or s.get("ai_segment"):
        ai = (f'<div class="r-ai"><div class="r-ai-l">AI analysis · Gemini{" · generated " + escape(s["ai_generated_at"]) if s.get("ai_generated_at") else ""}'
              ' · an interpretation of the threads, not a measured fact</div>'
              + (f'<p>{escape(s["ai_problem"])}</p>' if s.get("ai_problem") else "")
              + (f'<h4>Who is affected</h4>{_claims(s["ai_segment"])}' if s.get("ai_segment") else "") + "</div>")
    who = ("" if s.get("ai_segment") else
           '<p class="r-muted"><b>Who is affected:</b> not measured. DevvIT doesn\'t record who posts each thread.</p>')
    return f"""
<section class="r-sec">
  <div class="r-kicker">Pain point · {escape(s["category"])} · week of {escape(s["week"])}</div>
  <{"h2" if solo else "h3"} class="r-h">{escape(s["title"])}</{"h2" if solo else "h3"}>
  <p class="r-lead">{escape(s["explanation"])}{(" " + escape(s["why"])) if s.get("why") else ""}</p>
  <div class="r-facts">
    {_fact("Mentions that week", str(s["mentions"]), trend)}
    {_fact("Unresolved", f'{s["unresolved"]} of {s["mentions"]}', "threads without a working fix")}
    {_fact("Independent threads", str(s["independent_threads"]), f'{s["evidence_level"]} evidence · near-duplicates merged')}
    {_fact("Sources", str(len(s["sources"])), ", ".join(s["sources"]) or "none")}
    {_fact("Observed", observed, f'first in a brief: week of {s["first_week"]}')}
    {_fact("Negative threads", str(s["negative"]), "mixed opinions" if s["mixed_opinions"] else "tone from DevvIT's tagger")}
  </div>
  <p class="r-muted">Trend: {escape(s["trend_text"])} Severity isn't scored as a single number; unresolved threads and negative tone are shown instead.</p>
  {_bars(s["series"])}
  {who}
  {ai}
  <h4>Evidence: source threads</h4>
  <p class="r-muted">Thread titles exactly as posted. DevvIT doesn't quote thread bodies.</p>
  {_threads(s["threads"])}
</section>"""


def _opportunity(s: dict, solo: bool) -> str:
    factors = "".join(
        f'<tr><td><b>{escape(f["label"])}</b><small>{escape(f["about"])}</small></td>'
        f'<td class="n">{"not used" if f["value"] is None else format(f["value"], ".2f")}</td><td class="n">×{f["weight"]:g}</td></tr>'
        for f in s["factors"])
    ai_parts = []
    if s.get("ai_problem"):
        ai_parts.append(f'<h4>Problem it addresses</h4><p>{escape(s["ai_problem"])}</p>')
    if s.get("ai_segment"):
        ai_parts.append(f'<h4>Target developer segment</h4>{_claims(s["ai_segment"])}')
    if s.get("ai_existing"):
        ai_parts.append(f'<h4>What developers use today</h4>{_claims(s["ai_existing"])}')
    if s.get("ai_unmet_needs"):
        ai_parts.append(f'<h4>Unmet needs</h4>{_claims(s["ai_unmet_needs"])}')
    if s.get("ai_experiments"):
        ai_parts.append('<h4>Possible product directions to test</h4><ul>' + "".join(f"<li>{escape(x)}</li>" for x in s["ai_experiments"]) + "</ul>")
    ai = (f'<div class="r-ai"><div class="r-ai-l">AI-generated hypotheses · Gemini{" · " + escape(s["ai_generated_at"]) if s.get("ai_generated_at") else ""}'
          ' · ideas to test, not validated findings. Numbered links show the threads each point came from.</div>' + "".join(ai_parts) + "</div>"
          if ai_parts else
          '<p class="r-muted"><b>Problem framing, target segment and proposed direction:</b> unavailable. No AI analysis was generated '
          'for this opportunity, and DevvIT doesn\'t measure these directly.</p>')
    questions = ("<ul>" + "".join(f"<li>{escape(q)}</li>" for q in s["ai_questions"]) + "</ul>" if s.get("ai_questions")
                 else '<p class="r-muted">None recorded.</p>')
    score = "—" if s.get("score") is None else f'{s["score"]:.0f}'
    support = "".join(f'<li><b>{escape(p["title"])}</b>: {p["mentions"]} mentions, {p["unresolved"]} unresolved (week of {escape(s["week"])})</li>'
                      for p in s["supporting"])
    return f"""
<section class="r-sec">
  <div class="r-kicker">Product opportunity · {escape(s["category"])} · week of {escape(s["week"])}</div>
  <div class="r-oh"><{"h2" if solo else "h3"} class="r-h">{escape(s["title"])}</{"h2" if solo else "h3"}>
    <div class="r-score"><span>Priority score</span><b>{score}</b><small>of 100</small></div></div>
  <p class="r-lead">{escape(s["explanation"])}</p>
  <div class="r-warn">The priority score ranks where to look first, from public discussion. It is not validated demand,
    willingness to pay or market size.</div>
  <h4>Observed evidence</h4>
  <p>{escape(s["evidence_text"])}</p>
  <ul>{support}</ul>
  <h4>How the score is calculated</h4>
  <p class="r-muted">A weighted average of five factors, each from 0 to 1, scaled to 100. Factors without data are left out.</p>
  <div class="r-tbl"><table><thead><tr><th>Factor</th><th class="n">Value</th><th class="n">Weight</th></tr></thead><tbody>{factors}</tbody></table></div>
  {ai}
  <h4>Risks and assumptions</h4>
  <ul>{"".join(f"<li>{escape(r)}</li>" for r in s["risks"])}</ul>
  <h4>Unanswered questions{' <span class="r-tag">AI suggestions</span>' if s.get("ai_questions") else ""}</h4>
  {questions}
  <h4>Evidence: source threads</h4>
  {_threads(s["threads"])}
</section>"""


def _trends(s: dict) -> str:
    kind = {"new": "New theme", "rising": "Rising", "returning": "Back again", "baseline_pending": "Needs a baseline"}
    if not s["items"]:
        return '<section class="r-sec"><h3 class="r-h">Emerging trends</h3><p class="r-muted">No emerging themes were flagged.</p></section>'
    rows = "".join(f'<li><b>{escape(t["label"])}</b> <span class="r-tag">{escape(kind.get(t["kind"], t["kind"]))}</span><br>'
                   f'<span class="r-muted">{escape(t["reason"])} {escape(t["evidence_level"])} evidence.</span></li>' for t in s["items"])
    note = "" if s["history_ok"] else '<p class="r-muted">Only one weekly brief existed, so nothing could be compared with a baseline.</p>'
    return (f'<section class="r-sec"><h3 class="r-h">Emerging trends</h3><p class="r-muted">From DevvIT\'s radar: rules of thumb on '
            f'mention counts, not statistical tests.</p>{note}<ul class="r-list">{rows}</ul></section>')


def _brief_html(markdown_text: str) -> str:
    html = md.markdown(escape(markdown_text or "", quote=False))
    html = re.sub(r'<a href="(?!https?://)[^"]*"', '<a href="#"', html)
    return html.replace("<a href=", '<a target="_blank" rel="noopener noreferrer nofollow" href=')


def _brief(s: dict) -> str:
    rows = "".join(f'<tr><td>{escape(p["title"])}<small>{escape(p["category"])}</small></td><td class="n">{p["mentions"]}</td>'
                   f'<td class="n">{"—" if p["previous"] is None else p["previous"]}</td><td class="n">{p["unresolved"]}</td></tr>'
                   for p in s["top"])
    src = ", ".join(f"{k}: {v}" for k, v in s["sources"].items()) or "none"
    return f"""
<section class="r-sec">
  <div class="r-kicker">Weekly brief · week of {escape(s["week"])}</div>
  <h3 class="r-h">Top pain points</h3>
  <p class="r-muted">{s["threads"]} tagged threads that week ({escape(src)}).</p>
  <div class="r-tbl"><table><thead><tr><th>Pain point</th><th class="n">This week</th><th class="n">Previous</th><th class="n">Unresolved</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <h3 class="r-h">The brief</h3>
  <div class="r-md">{_brief_html(s["markdown"]) or '<p class="r-muted">The written brief is unavailable.</p>'}</div>
</section>"""


def render_sections(snap: dict) -> str:
    secs = snap.get("sections", [])
    solo = len([s for s in secs if s["type"] in ("pain_point", "opportunity")]) == 1 and snap["kind"] != "combined"
    out = ""
    pps = [s for s in secs if s["type"] == "pain_point"]
    ops = [s for s in secs if s["type"] == "opportunity"]
    if snap["kind"] == "combined":
        for s in secs:
            if s["type"] == "pain_point" and s is pps[0]:
                out += '<h2 class="r-group">Key pain points</h2>'
            if s["type"] == "opportunity" and s is ops[0]:
                out += '<h2 class="r-group">Product opportunities</h2>'
            out += _render_one(s, False)
        return out
    return "".join(_render_one(s, solo) for s in secs)


def _render_one(s: dict, solo: bool) -> str:
    return {"pain_point": lambda: _pain_point(s, solo), "opportunity": lambda: _opportunity(s, solo),
            "trends": lambda: _trends(s), "brief": lambda: _brief(s)}.get(s["type"], lambda: "")()


REPORT_CSS = """
<style>
  .rp { max-width: 860px; margin: 0 auto; padding: 28px 24px 64px; }
  .rp-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; padding-bottom: 16px;
            border-bottom: 1px solid var(--border); }
  .rp-brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 17px; }
  .rp-brand i { width: 28px; height: 28px; border-radius: 8px; background: var(--ink); display: grid; place-items: center; }
  .rp-brand i svg { width: 16px; height: 16px; stroke: var(--accent-on-ink); fill: none; stroke-width: 1.8; }
  .rp-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .rp h1 { font-family: var(--serif); font-weight: 400; font-size: 40px; line-height: 1.12; margin: 28px 0 10px; letter-spacing: -.01em; }
  .rp-meta { font-family: var(--mono); font-size: 12px; color: var(--text-3); line-height: 1.7; }
  .rp-snap { margin-top: 14px; padding: 10px 14px; border-radius: 10px; background: var(--chip); font-size: var(--fs-sm); color: var(--text-2); line-height: 1.5; }
  .rp-intro { font-size: 17px; line-height: 1.6; margin: 20px 0 0; white-space: pre-line; }
  .r-group { font-family: var(--serif); font-weight: 400; font-size: 28px; margin: 40px 0 0; }
  .r-sec { margin-top: 28px; padding-top: 24px; border-top: 1px solid var(--border); }
  .r-kicker { font-family: var(--mono); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--accent); }
  .r-h { font-size: 24px; font-weight: 650; margin: 6px 0 10px; line-height: 1.25; }
  h3.r-h { font-size: 21px; }
  .r-sec h4 { font-size: 15px; font-weight: 600; margin: 22px 0 6px; }
  .r-lead { font-size: 16px; line-height: 1.6; margin: 0; }
  .r-sec p, .r-sec li { line-height: 1.6; }
  .r-muted { color: var(--text-3); font-size: var(--fs-sm); }
  .r-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 16px 0 10px; }
  .r-fact { border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; background: var(--surface); min-width: 0; }
  .r-fact span { display: block; font-size: 12px; color: var(--text-3); } .r-fact b { display: block; font-size: 20px; margin-top: 4px; }
  .r-fact small { display: block; font-size: 11px; color: var(--text-3); margin-top: 4px; }
  .r-bars { display: flex; gap: 8px; align-items: flex-end; height: 120px; margin: 14px 0 6px; padding: 0 2px; }
  .r-bars div { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; height: 100%; min-width: 0; }
  .r-bars i { display: block; width: 100%; max-width: 44px; background: var(--bar); border-radius: 4px 4px 0 0; }
  .r-bars b { font-size: 11px; font-family: var(--mono); order: -1; margin-bottom: 2px; font-weight: 500; }
  .r-bars span { font-size: 10px; color: var(--text-3); font-family: var(--mono); margin-top: 4px; }
  .r-ai { margin-top: 16px; padding: 14px 16px; border-radius: 12px; border: 1px dashed color-mix(in srgb, var(--accent) 45%, transparent); }
  .r-ai-l { font-family: var(--mono); font-size: 11px; color: var(--accent); text-transform: uppercase; letter-spacing: .04em; line-height: 1.5; }
  .r-ai h4 { margin-top: 14px; }
  .r-cite { font-family: var(--mono); font-size: 11px; color: var(--link); }
  .r-warn { margin: 14px 0 0; padding: 10px 14px; border-radius: 10px; background: var(--peach); border: 1px solid var(--peach-border); font-size: var(--fs-sm); }
  .r-oh { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
  .r-score { text-align: right; } .r-score span, .r-score small { display: block; font-size: 11px; color: var(--text-3); font-family: var(--mono); }
  .r-score b { font-size: 40px; font-weight: 700; line-height: 1; }
  .r-tbl { overflow-x: auto; } .r-tbl table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
  .r-tbl th { text-align: left; font-size: 11px; color: var(--text-3); font-weight: 500; font-family: var(--mono); padding: 6px 8px; border-bottom: 1px solid var(--border); }
  .r-tbl td { padding: 8px; border-bottom: 1px solid var(--border-soft); vertical-align: top; }
  .r-tbl td small { display: block; color: var(--text-3); font-size: 11px; }
  .r-tbl .n { text-align: right; font-family: var(--mono); white-space: nowrap; }
  .r-threads { padding-left: 20px; margin: 8px 0 0; } .r-threads li { margin-bottom: 8px; }
  .r-threads a, .r-sec a { color: var(--link); } .r-threads span { display: block; font-size: 12px; color: var(--text-3); font-family: var(--mono); }
  .r-tag { font-family: var(--mono); font-size: 10px; text-transform: uppercase; color: var(--accent); border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
           border-radius: 4px; padding: 0 5px; font-weight: 500; vertical-align: 2px; }
  .r-list { padding-left: 18px; } .r-list li { margin-bottom: 10px; }
  .r-md h1, .r-md h2 { font-size: 18px; margin: 18px 0 6px; } .r-md h3 { font-size: 16px; margin: 14px 0 4px; }
  .rp-foot { margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border); font-size: 12px; color: var(--text-3); line-height: 1.6; }
  .rp-banner { background: var(--ink); color: var(--bg); font-size: var(--fs-sm); padding: 10px 16px; text-align: center; }
  .rp-banner a { color: var(--accent-on-ink); }
  @media (max-width: 680px) { .rp { padding: 20px 16px 48px; } .rp h1 { font-size: 30px; } .r-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                              .r-oh { flex-direction: column; } .r-score { text-align: left; } }
  @media print { .rp-actions, .rp-banner, .noprint { display: none !important; } body { background: #fff; }
                 .rp { max-width: none; padding: 0; } .r-sec { break-inside: avoid-page; } a { color: inherit !important; }
                 .r-threads a::after { content: " (" attr(href) ")"; font-size: 10px; word-break: break-all; } }
</style>"""

_LOGO = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 8h3l2-4.5 3 9 2-4.5h3"></path></svg>'


def report_page(snap: dict, *, banner: str = "", show_copy_link: bool = True) -> str:
    """The read-only report. Everything comes from the snapshot; no DevvIT navigation or actions."""
    kind = KINDS.get(snap["kind"], "Report")
    updated = _ist_label(snap.get("data_updated_at")) if snap.get("data_updated_at") else "unavailable"
    copy = ('<button class="btn" type="button" onclick="(async b=>{try{await navigator.clipboard.writeText(location.href);'
            'b.textContent=\'Link copied\'}catch(e){b.textContent=\'Copy the address bar link\'}})(this)">Copy link</button>'
            if show_copy_link else "")
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex, nofollow"><meta name="referrer" content="no-referrer">
<title>{escape(snap["title"])} · DevvIT</title>
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
{BASE_CSS}{REPORT_CSS}
</head><body>
{banner}
<main class="rp">
  <div class="rp-top"><div class="rp-brand"><i>{_LOGO}</i>DevvIT</div>
    <div class="rp-actions">{copy}<button class="btn" type="button" onclick="window.print()">Print / Save as PDF</button></div></div>
  <div class="r-kicker" style="margin-top:28px">{escape(kind)}</div>
  <h1 style="margin-top:6px">{escape(snap["title"])}</h1>
  <div class="rp-meta">Report created {escape(_ist_label(snap["generated_at"]))}<br>DevvIT data last updated {escape(updated)}</div>
  <div class="rp-snap">This is a snapshot taken when the report was created. It does not change when DevvIT's data changes.
    Figures count public threads on Hacker News, Stack Overflow and GitHub.</div>
  {f'<p class="rp-intro">{escape(snap["intro"])}</p>' if snap.get("intro") else ""}
  {render_sections(snap)}
  <div class="rp-foot">Generated by DevvIT, developer community intelligence. Sections marked AI were written by Gemini from the
    linked threads and are hypotheses, not findings. Source links go to the original public discussions.</div>
</main>
</body></html>"""


def link_error(kind: str) -> tuple[int, str]:
    msgs = {"invalid": (404, "This link isn't valid", "Check that the whole link was copied. If it was shared with you, ask the sender for a new one."),
            "revoked": (410, "This report is no longer shared", "The owner turned off this link. Ask them for a new one if you still need it."),
            "expired": (410, "This link has expired", "Shared reports can be set to expire. Ask the owner for a new link."),
            "unavailable": (503, "This report can't be shown right now", "DevvIT couldn't load it. Try again in a few minutes.")}
    code, title, text = msgs[kind]
    return code, f"""<!doctype html><html lang="en"><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex, nofollow"><title>{escape(title)} · DevvIT</title><link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,400&display=swap" rel="stylesheet">
{BASE_CSS}{REPORT_CSS}</head><body><main class="rp"><div class="rp-top"><div class="rp-brand"><i>{_LOGO}</i>DevvIT</div></div>
<h1>{escape(title)}</h1><p class="rp-intro">{escape(text)}</p></main></body></html>"""


# ---------- owner pages (admin) ----------
def _opts(cur: str = "30") -> str:
    labels = {"never": "Never", "1": "In 1 day", "7": "In 7 days", "30": "In 30 days", "90": "In 90 days"}
    return "".join(f'<option value="{k}"{" selected" if k == cur else ""}>{v}</option>' for k, v in labels.items())


def _visibility(cur: str = "unlisted") -> str:
    return f"""
<fieldset class="field" style="border:0;padding:0;margin:12px 0 0"><span>Who can open it</span>
  <label><input type="radio" name="visibility" value="unlisted"{" checked" if cur == "unlisted" else ""}> <b>Unlisted link</b>: anyone with the link can view it.
    It isn't fully private: recipients can forward the link.</label>
  <label><input type="radio" name="visibility" value="private"{" checked" if cur == "private" else ""}> <b>Private</b>: opens only with the DevvIT admin password.</label>
</fieldset>"""


BUILDER_JS = """<script>
(() => {
  const list = document.getElementById('rep-items'); if (!list) return;
  list.addEventListener('click', e => {
    const b = e.target.closest('[data-move]'); if (!b) return;
    const li = b.closest('li');
    if (b.dataset.move === 'up' && li.previousElementSibling) list.insertBefore(li, li.previousElementSibling);
    if (b.dataset.move === 'down' && li.nextElementSibling) list.insertBefore(li.nextElementSibling, li);
    if (b.dataset.move === 'remove') li.remove();
    const left = list.querySelectorAll('li').length;
    document.getElementById('rep-empty').hidden = left > 0;
    document.querySelectorAll('[data-needs-items]').forEach(x => x.disabled = left === 0);
  });
  const f = document.getElementById('rep-form');
  f.addEventListener('submit', () => { const b = f.querySelector('button[type=submit]:focus') || f.querySelector('button.btn-primary'); if (b && !b.formTarget) { b.disabled = true; b.textContent = 'Creating…'; } });
})();
</script>"""


def builder_page(sections: list[dict], missing: list[str], title: str, intro: str, trends: dict | None,
                 history: list[dict], saving: bool) -> str:
    items = ""
    for s in sections:
        kind = "Pain point" if s["type"] == "pain_point" else "Opportunity"
        ref = f'{"pp" if s["type"] == "pain_point" else "op"}:{s["name"]}'
        facts = (f'{s["mentions"]} mentions · {s["independent_threads"]} independent threads · {len(s["sources"])} sources'
                 if s["type"] == "pain_point" else
                 f'Score {"—" if s["score"] is None else format(s["score"], ".0f")} · {s["evidence_text"]}')
        links = "".join(f'<li>{_ext(t["url"], t["title"])} <span class="sub">{escape(t["source"])} · {escape(t["date"])}</span></li>'
                        for t in s["threads"]) or "<li class='sub'>No source links stored.</li>"
        items += f"""<li class="rep-item"><input type="hidden" name="item" value="{escape(ref)}">
  <div class="rep-item-h"><span class="pill">{kind}</span><b>{escape(s["title"])}</b>
    <button type="button" class="btn" data-move="up" title="Move up">↑</button><button type="button" class="btn" data-move="down" title="Move down">↓</button>
    <button type="button" class="btn" data-move="remove">Remove</button></div>
  <div class="sub" style="margin-top:6px">{escape(facts)}</div>
  <details><summary>Review evidence and source links ({len(s["threads"])})</summary><ul class="plain">{links}</ul></details></li>"""
    miss = (f'<div class="note-box">Left out because they aren\'t in DevvIT\'s data (an opportunity must be in the latest brief): '
            f'{escape(", ".join(missing))}.</div>' if missing else "")
    trend_opt = (f'<label style="display:block;margin-top:12px"><input type="checkbox" name="trends" value="1" checked> Include emerging trends '
                 f'from the radar ({len(trends["items"])} theme{"s" if len(trends["items"]) != 1 else ""})</label>'
                 if trends and trends["items"] else "")
    gate = "" if saving else ('<div class="note-box">Creating links needs a one-time database update: run '
                              '<code>supabase/migrations/004_shared_reports.sql</code> in Supabase → SQL Editor. You can still export.</div>')
    body = f"""
<main class="fb" style="max-width:900px">
  <a class="back" href="/pain-points">← Pain points</a>
  <div class="fb-eyebrow">New report</div>
  <h1 class="fb-h1">Report preview</h1>
  <p class="fb-sub">Edit the title and introduction, reorder or remove items and check the sources. The report is saved as a
     snapshot of the data as it is now.</p>
  {gate}{miss}
  <form class="panel rep-form" id="rep-form" method="post" action="/share/create" style="margin-top:18px">
    <input type="hidden" name="kind" value="combined">
    <label class="field"><span>Report title</span><input type="text" name="title" maxlength="140" required value="{escape(title)}"></label>
    <label class="field"><span>Introduction / executive summary (drafted from the data; edit freely)</span>
      <textarea name="intro" maxlength="2000">{escape(intro)}</textarea></label>
    <div class="field"><span>Included insights, in report order</span></div>
    <ol class="rep-items" id="rep-items">{items}</ol>
    <p class="sub" id="rep-empty"{"" if not sections else " hidden"}>Nothing selected. Go to Pain points or Opportunities and tick the boxes,
      or use Share → Add to combined report.</p>
    {trend_opt}
    {_visibility()}
    <label class="field"><span>Link expires</span><select name="expires">{_opts()}</select></label>
    <div class="fb-btns" style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap">
      <button class="btn btn-primary" type="submit" data-needs-items{" disabled" if not sections or not saving else ""}>Generate shareable link</button>
      <button class="btn" type="submit" formaction="/reports/print" formtarget="_blank" data-needs-items{"" if sections else " disabled"}>Export / print</button>
      <span class="sub">Generating a link needs the admin password.</span></div>
  </form>
</main>"""
    return _page("Report preview", body, active="reports", history=history, script=BUILDER_JS)


def created_page(row: dict, link: str, summary: str, state: str, history: list[dict], flash: str | None) -> str:
    vis = row["visibility"]
    exp = _ist_label(row.get("expires_at")) if row.get("expires_at") else "Never"
    status = {"active": ("Active", "ok"), "revoked": ("Revoked", "bad"), "expired": ("Expired", "bad")}[state]
    actions = "" if state == "revoked" else f"""
  <form method="post" action="/reports/{row['id']}/update" class="rep-form" style="margin-top:8px">
    {_visibility(vis)}
    <label class="field"><span>Change expiry</span><select name="expires"><option value="keep" selected>Keep ({escape(exp)})</option>{_opts("")}</select></label>
    <label class="field"><span>…or expire on a date</span><input type="date" name="expires_on"></label>
    <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap"><button class="btn" type="submit">Save settings</button></div>
  </form>
  <form method="post" action="/reports/{row['id']}/revoke" style="margin-top:16px"
        onsubmit="return confirm('Revoke this link? Anyone who opens it will see that it is no longer shared. This can\\'t be undone.')">
    <button class="btn" type="submit">Revoke access</button> <span class="sub">The link stops working immediately, on the server.</span></form>"""
    body = f"""
<main class="fb" style="max-width:900px">
  {_flash(flash)}
  <a class="back" href="/reports">← Shared reports</a>
  <div class="fb-eyebrow">{escape(KINDS.get(row["kind"], "Report"))} · <span class="cov {status[1]}">{status[0]}</span></div>
  <h1 class="fb-h1">{escape(row["title"])}</h1>
  <p class="fb-sub">Created {escape(_ist_label(row["created_at"]))} · {escape(VISIBILITY[vis])} · expires: {escape(exp)}
     {(" · last opened " + escape(_ist_label(row["last_accessed_at"]))) if row.get("last_accessed_at") else " · not opened yet"}</p>
  <section class="panel" style="margin-top:18px"><h2 class="ph">Share link</h2>
    <p class="sub">{"Anyone with this link can view the read-only report, and recipients can forward it." if vis == "unlisted"
                    else "Private: the link asks for the DevvIT admin password, so only you can open it."}</p>
    <div class="linkbox"><input type="text" readonly value="{escape(link)}" onclick="this.select()" aria-label="Share link">
      <button class="btn btn-primary" type="button" onclick="devvitCopy({escape(repr(link))}, this.parentElement.querySelector('.copied'))">Copy link</button>
      <a class="btn" href="{escape(link)}" target="_blank" rel="noopener">Open</a><span class="copied" role="status"></span></div>
    <div class="linkbox"><button class="btn" type="button" onclick="devvitCopy(document.getElementById('sumtxt').value, this.nextElementSibling)">Copy summary with link</button>
      <span class="copied" role="status"></span></div>
    <textarea id="sumtxt" hidden>{escape(summary)}</textarea>
  </section>
  <section class="panel" style="margin-top:14px"><h2 class="ph">Access</h2>{actions or '<p class="sub">This link was revoked and can no longer be opened.</p>'}</section>
</main>"""
    clear = ("<script>window.devvitClearSelection && devvitClearSelection();</script>"
             if row["kind"] == "combined" and flash and "created" in flash.lower() else "")
    return _page(row["title"], body, active="reports", history=history, script=clear)


def reports_page(rows: list[dict], links: dict, states: dict, history: list[dict], saving: bool, flash: str | None) -> str:
    if not saving:
        content = ('<div class="note-box">Shared reports need a one-time database update: run '
                   '<code>supabase/migrations/004_shared_reports.sql</code> in Supabase → SQL Editor.</div>')
    elif not rows:
        content = ('<div class="panel"><p class="sub">No shared reports yet. Use <b>Share</b> on a pain point or opportunity, or select '
                   'several and click <b>Create report</b>.</p></div>')
    else:
        body = ""
        for r in rows:
            st = states[r["id"]]
            cls = {"active": "ok", "revoked": "bad", "expired": "bad"}[st]
            link = links[r["id"]]
            body += (f'<tr><td><a href="/reports/{r["id"]}"><b>{escape(r["title"])}</b></a><br><span class="sub">{escape(KINDS.get(r["kind"], ""))}</span></td>'
                     f'<td>{escape(VISIBILITY.get(r["visibility"], ""))}</td><td class="mono">{escape((r["created_at"] or "")[:10])}</td>'
                     f'<td class="mono">{escape((r.get("expires_at") or "never")[:10])}</td><td><span class="cov {cls}">{st.capitalize()}</span></td>'
                     f'<td class="mono">{escape((r.get("last_accessed_at") or "—")[:10])}</td>'
                     f'<td>' + (f'<button class="btn" type="button" onclick="devvitCopy({escape(repr(link))}, this.nextElementSibling)">Copy link</button>'
                                f'<span class="copied"></span> ' if st == "active" else "")
                     + f'<a class="btn" href="/reports/{r["id"]}">Manage</a></td></tr>')
        content = (f'<div class="panel" style="margin-top:14px"><div class="tbl" style="border:0"><table class="reptab"><thead><tr><th>Report</th><th>Visibility</th>'
                   f'<th>Created</th><th>Expires</th><th>Status</th><th>Last opened</th><th></th></tr></thead><tbody>{body}</tbody></table></div></div>')
    body = f"""
<main class="fb">
  {_flash(flash)}
  <div class="fb-eyebrow">Sharing</div>
  <h1 class="fb-h1">Shared reports</h1>
  <p class="fb-sub">Every link you've created. Copy a link, see when it was last opened, change its expiry or revoke it.
     Revoked and expired links stop working on the server.</p>
  {content}
</main>"""
    return _page("Shared reports", body, active="reports", history=history)


def print_banner(note: str) -> str:
    return f'<div class="rp-banner">{escape(note)} <a href="javascript:history.back()">Back to DevvIT</a></div>'
