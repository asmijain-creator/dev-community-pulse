"""Public landing page for DevvIT (/welcome): a live "runtime console" of what developers struggle with and build.

Live numbers and the console feed come from stored data when the database answers; without it the page still
renders, with dashes and a note instead of numbers. The hero's signal-line animation is decorative, drawn on a
canvas, and stops for visitors who prefer reduced motion.
"""
from html import escape

from lib.views import BASE_CSS, FAVICON, _icon, _nice, _week_no

CSS = """<style>
  body { background-size: 22px 22px; }
  .lp { max-width: 1180px; margin: 0 auto; padding-inline: 24px; }
  .lp-top { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 10; backdrop-filter: blur(10px);
            background: color-mix(in srgb, var(--bg) 82%, transparent); border-bottom: 1px solid var(--border-soft); }
  .lp-top .lp { display: flex; align-items: center; gap: 22px; height: 62px; }
  .lp-brand { display: flex; align-items: center; gap: 10px; font-family: var(--display); font-weight: 700; font-size: 18px; color: var(--text); }
  .lp-brand i { width: 30px; height: 30px; border-radius: 8px; background: var(--accent); color: var(--btn-fg); display: grid; place-items: center; }
  .lp-nav { display: flex; gap: 18px; margin-left: auto; font-size: var(--fs-sm); color: var(--text-3); }
  .lp-nav a:hover { color: var(--text); }
  .lp a:focus-visible, .lp-top a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 4px; }
  .lp-hero { position: relative; overflow: hidden; border-bottom: 1px solid var(--border-soft); }
  .lp-hero canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
  .lp-hero .lp { position: relative; display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); gap: 48px;
                 align-items: center; padding-block: 72px 80px; }
  .lp-eyebrow { font-family: var(--mono); font-size: 12px; letter-spacing: .14em; text-transform: uppercase; color: var(--accent);
                display: inline-flex; align-items: center; gap: 10px; }
  .lp-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 0 var(--accent);
            animation: lp-pulse 2s ease-out infinite; }
  @keyframes lp-pulse { 0% { box-shadow: 0 0 0 0 rgba(61,220,255,.55); } 100% { box-shadow: 0 0 0 10px rgba(61,220,255,0); } }
  .lp h1 { font-family: var(--display); font-size: clamp(34px, 5vw, 58px); line-height: 1.04; letter-spacing: -.025em;
           margin: 16px 0 18px; text-wrap: balance; font-weight: 600; }
  .lp h1 em { font-style: normal; color: var(--accent); }
  .lp-lede { font-size: 17px; line-height: 1.6; color: var(--text-2); max-width: 54ch; margin: 0; }
  .lp-ctas { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }
  .lp .btn { height: 44px; padding: 0 18px; font-size: 15px; border-radius: 10px; }
  .lp .btn.ghost { background: transparent; border-color: var(--border); color: var(--text); }
  .lp .btn.ghost:hover { border-color: var(--accent); }
  .lp-console { background: color-mix(in srgb, var(--panel) 92%, transparent); border: 1px solid var(--border); border-radius: 14px;
                box-shadow: 0 30px 80px rgba(0,0,0,.45); overflow: hidden; min-width: 0; }
  .lp-console-h { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--border-soft);
                  font-family: var(--mono); font-size: 12px; color: var(--text-3); }
  .lp-console-h b { color: var(--text); font-weight: 500; }
  .lp-console-h span:last-child { margin-left: auto; }
  .lp-log { list-style: none; margin: 0; padding: 10px 0; font-family: var(--mono); font-size: 12.5px; max-height: 360px; overflow: hidden; }
  .lp-log li { display: grid; grid-template-columns: 58px minmax(0, 1fr) auto; gap: 12px; padding: 7px 16px; align-items: baseline;
               border-left: 2px solid transparent; transition: background .3s, border-color .3s; }
  .lp-log li.on { background: var(--accent-soft); border-left-color: var(--accent); }
  .lp-log .k { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
  .lp-log .k.pain { color: var(--red); } .lp-log .k.build { color: var(--accent); } .lp-log .k.sys { color: var(--text-4); }
  .lp-log a, .lp-log .t { color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .lp-log a:hover { color: var(--link); text-decoration: underline; }
  .lp-log .m { color: var(--text-4); white-space: nowrap; }
  .lp-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-bottom: 1px solid var(--border-soft); }
  .lp-stat { padding: 26px 24px 26px 0; border-right: 1px solid var(--border-soft); min-width: 0; }
  .lp-stat + .lp-stat { padding-left: 24px; }
  .lp-stat:last-child { border-right: 0; }
  .lp-stat b { display: block; font-family: var(--display); font-size: 34px; font-weight: 600; font-variant-numeric: tabular-nums; }
  .lp-stat span { font-family: var(--mono); font-size: 11.5px; letter-spacing: .06em; text-transform: uppercase; color: var(--text-3); }
  .lp-note { font-size: var(--fs-sm); color: var(--text-3); padding: 12px 24px; border-bottom: 1px solid var(--border-soft); }
  .lp-sec { padding-block: 72px; }
  .lp-sec h2 { font-family: var(--display); font-size: clamp(26px, 3vw, 36px); letter-spacing: -.02em; margin: 10px 0 12px; font-weight: 600; text-wrap: balance; }
  .lp-sec > .lp > p { color: var(--text-2); max-width: 60ch; margin: 0; line-height: 1.6; }
  .lp-steps { list-style: none; margin: 36px 0 0; padding: 0; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0;
              border: 1px solid var(--border); border-radius: 14px; overflow: hidden; counter-reset: step; }
  .lp-steps li { padding: 22px; border-right: 1px solid var(--border-soft); counter-increment: step; position: relative; min-width: 0; }
  .lp-steps li:last-child { border-right: 0; }
  .lp-steps li::before { content: "0" counter(step); font-family: var(--mono); font-size: 12px; color: var(--accent); }
  .lp-steps h3 { margin: 10px 0 6px; font-size: 17px; font-family: var(--display); font-weight: 600; }
  .lp-steps p { margin: 0; color: var(--text-3); font-size: var(--fs-sm); line-height: 1.55; }
  .lp-feats { margin-top: 36px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
  .lp-feat { display: block; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; transition: border-color .2s; }
  .lp-feat:hover { border-color: var(--accent); }
  .lp-feat .ic { width: 34px; height: 34px; border-radius: 9px; background: var(--accent-soft); color: var(--accent); display: grid; place-items: center; }
  .lp-feat h3 { margin: 14px 0 6px; font-size: 16px; font-family: var(--display); font-weight: 600; }
  .lp-feat p { margin: 0; color: var(--text-3); font-size: var(--fs-sm); line-height: 1.55; }
  .lp-feat small { display: inline-block; margin-top: 12px; font-family: var(--mono); font-size: 11.5px; color: var(--link); }
  .lp-foot { border-top: 1px solid var(--border-soft); padding-block: 26px; font-size: var(--fs-sm); color: var(--text-3); }
  .lp-foot .lp { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; }
  @media (max-width: 960px) {
    .lp-hero .lp { grid-template-columns: minmax(0, 1fr); padding-block: 48px 56px; gap: 36px; }
    .lp-stats, .lp-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .lp-stat:nth-child(2) { border-right: 0; } .lp-stat:nth-child(-n+2) { border-bottom: 1px solid var(--border-soft); }
    .lp-stat:nth-child(3) { padding-left: 0; }
    .lp-steps li:nth-child(2) { border-right: 0; } .lp-steps li:nth-child(-n+2) { border-bottom: 1px solid var(--border-soft); }
    .lp-feats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .lp-nav a.opt { display: none; }
  }
  @media (max-width: 560px) {
    .lp { padding-inline: 16px; }
    .lp-stats, .lp-steps, .lp-feats { grid-template-columns: minmax(0, 1fr); }
    .lp-stat, .lp-steps li { border-right: 0; border-bottom: 1px solid var(--border-soft); }
    .lp-stat + .lp-stat { padding-left: 0; }
    .lp-log li { grid-template-columns: 48px minmax(0, 1fr); } .lp-log .m { display: none; }
    .lp-nav { display: none; } .lp-top .btn { margin-left: auto; }
  }
  @media (prefers-reduced-motion: reduce) { .lp-dot { animation: none; } .lp-log li { transition: none; } }
</style>"""

JS = """<script>
(() => {
  // Decorative signal lines: faint horizontal buses with small pulses travelling along them.
  const cv = document.getElementById('lp-signal'), still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (cv && cv.getContext) {
    const ctx = cv.getContext('2d'); let w, h, lines = [];
    const size = () => {
      const r = cv.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2);
      w = r.width; h = r.height; cv.width = w * d; cv.height = h * d; ctx.setTransform(d, 0, 0, d, 0, 0);
      lines = Array.from({ length: Math.max(6, Math.round(h / 46)) }, (_, i) => ({
        y: 24 + i * (h - 48) / Math.max(1, Math.round(h / 46) - 1), x: Math.random() * w,
        v: 0.4 + Math.random() * 1.4, len: 40 + Math.random() * 120, a: 0.25 + Math.random() * 0.5 }));
    };
    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (const l of lines) {
        ctx.strokeStyle = 'rgba(140,170,200,0.07)'; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(0, l.y); ctx.lineTo(w, l.y); ctx.stroke();
        const g = ctx.createLinearGradient(l.x - l.len, 0, l.x, 0);
        g.addColorStop(0, 'rgba(61,220,255,0)'); g.addColorStop(1, `rgba(61,220,255,${l.a})`);
        ctx.strokeStyle = g; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.moveTo(l.x - l.len, l.y); ctx.lineTo(l.x, l.y); ctx.stroke();
        if (!still) { l.x += l.v; if (l.x - l.len > w) l.x = -Math.random() * 200; }
      }
      if (!still) requestAnimationFrame(draw);
    };
    size(); draw(); addEventListener('resize', () => { size(); if (still) draw(); });
  }
  // Console: a highlight steps through the live feed. Every line is visible at rest.
  const rows = [...document.querySelectorAll('.lp-log li')];
  if (rows.length && !still) {
    let i = 0;
    setInterval(() => { rows.forEach((r, j) => r.classList.toggle('on', j === i)); i = (i + 1) % rows.length; }, 1400);
  }
})();
</script>"""


def _num(v) -> str:
    return "—" if v is None else f"{v:,}"


def _feed(live: dict | None) -> str:
    if not live or not live.get("feed"):
        return ('<li><span class="k sys">sys</span><span class="t">Waiting for the first weekly brief</span><span class="m">—</span></li>'
                '<li><span class="k sys">sys</span><span class="t">Run now collects Hacker News, Stack Overflow and GitHub</span><span class="m">—</span></li>')
    out = ""
    for e in live["feed"]:
        target = ' target="_blank" rel="noopener noreferrer"' if e["external"] else ""
        out += (f'<li><span class="k {e["kind"]}">{"pain" if e["kind"] == "pain" else "build"}</span>'
                f'<a href="{escape(e["href"])}"{target}>{escape(e["label"])}</a>'
                f'<span class="m">{escape(e["meta"])}</span></li>')
    return out


def landing_page(live: dict | None) -> str:
    """live: {"week", "pain_points", "mentions", "unresolved", "builds", "feed": [{"kind", "label", "meta", "href", "external"}]}
    or None when the database isn't available."""
    week = f'week {_week_no(live["week"])}' if live and live.get("week") else "waiting for data"
    stats = [("pain_points", "Pain points this week"), ("mentions", "Pain-point mentions"),
             ("unresolved", "Unresolved threads"), ("builds", "Build discussions · 30 days")]
    stat_html = "".join(f'<div class="lp-stat"><b>{_num((live or {}).get(k))}</b><span>{label}</span></div>' for k, label in stats)
    note = "" if live else '<div class="lp-note lp">Live numbers appear here once DevvIT is connected to its database.</div>'
    feats = [("/", "grid", "Weekly brief", "Every Friday at 8:30 AM IST: the top pain points, what's rising and three actions for sprint planning.", "This week →"),
             ("/radar", "target", "Radar", "Themes that are new, rising or back again, compared with their four-week baseline, with the evidence behind each.", "Open radar →"),
             ("/opportunities", "zap", "Opportunities", "Pain points scored on frequency, growth, severity, unresolved share and source diversity. You set the weights.", "See scores →"),
             ("/building", "wrench", "Building Now", "What developers are publicly building on GitHub, Hacker News, Dev.to and Product Hunt, and what blocks them.", "See projects →"),
             ("/pain-points", "flame", "Pain points", "Every problem developers raised, with week-by-week history and links to the original threads.", "Browse →"),
             ("/watchlist", "eye", "Watchlist", "Keep an eye on the problems you care about and see them change each week.", "Watchlist →")]
    feat_html = "".join(f'<a class="lp-feat" href="{h}"><span class="ic">{_icon(i)}</span><h3>{t}</h3><p>{escape(d)}</p><small>{c}</small></a>'
                        for h, i, t, d, c in feats)
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>DevvIT</title>
<meta name="description" content="DevvIT turns public developer discussions into weekly product intelligence: what developers struggle with, what they build and where the opportunities are.">
<meta name="theme-color" content="#070a0e">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
{BASE_CSS}{CSS}
</head><body>
<header class="lp-top"><div class="lp">
  <a class="lp-brand" href="/welcome"><i>{_icon("pulse")}</i>DevvIT</a>
  <nav class="lp-nav" aria-label="Product"><a class="opt" href="/radar">Radar</a><a class="opt" href="/opportunities">Opportunities</a><a href="/building">Building Now</a></nav>
  <a class="btn btn-primary" href="/">Open dashboard</a>
</div></header>
<section class="lp-hero"><canvas id="lp-signal" aria-hidden="true"></canvas><div class="lp">
  <div>
    <span class="lp-eyebrow"><span class="lp-dot" aria-hidden="true"></span>Developer intelligence runtime</span>
    <h1>What developers <em>struggle with</em> and what they <em>build</em>, every week.</h1>
    <p class="lp-lede">DevvIT reads public discussions on Hacker News, Stack Overflow, GitHub and Dev.to, groups them into pain points
      and projects, and compares each week with the last. Every claim links back to a real thread.</p>
    <div class="lp-ctas"><a class="btn btn-primary" href="/">Open the dashboard</a><a class="btn ghost" href="/building">See what's being built</a></div>
  </div>
  <div class="lp-console" role="region" aria-label="Live DevvIT feed">
    <div class="lp-console-h"><span class="lp-dot" aria-hidden="true"></span><b>devvit.runtime</b><span>{escape(week)}</span></div>
    <ul class="lp-log">{_feed(live)}</ul>
  </div>
</div></section>
<section class="lp-stats lp" aria-label="This week in numbers">{stat_html}</section>
{note}
<section class="lp-sec"><div class="lp">
  <span class="lp-eyebrow">How it runs</span>
  <h2>A weekly pipeline from raw threads to sprint actions</h2>
  <p>Numbers are computed from stored data; Gemini names and classifies, and its claims are checked against the post text.</p>
  <ol class="lp-steps">
    <li><h3>Collect</h3><p>Fresh threads and project posts from Hacker News, Stack Overflow, GitHub, Dev.to and Product Hunt.</p></li>
    <li><h3>Classify</h3><p>Gemini Flash tags each thread once: pain point, category, sentiment, whether it's solved.</p></li>
    <li><h3>Compare</h3><p>Mentions are counted per week and compared with the baseline: new, rising, falling.</p></li>
    <li><h3>Brief</h3><p>Friday 8:30 AM IST: a brief with linked evidence lands on the dashboard and in email.</p></li>
  </ol>
</div></section>
<section class="lp-sec" style="padding-top:0"><div class="lp">
  <span class="lp-eyebrow">Inside DevvIT</span>
  <h2>Everything a product team needs from developer communities</h2>
  <div class="lp-feats">{feat_html}</div>
</div></section>
<footer class="lp-foot"><div class="lp"><span>DevvIT · new brief every Friday, 8:30 AM IST</span><a href="/health">System health</a></div></footer>
{JS}
</body></html>"""
