"""The Friday email: a short, structured summary that points to the full brief on the dashboard.

Numbers come from the metrics; only the sprint actions are taken from the written brief.
"""
import os
import re
from datetime import date
from html import escape

import markdown as md

from lib.views import parse_brief

INK, MUTED, LINE, GREEN = "#2f3242", "#6f7285", "#e7e9ee", "#007a5c"


def app_url() -> str:
    if os.getenv("APP_URL"):
        return os.getenv("APP_URL").rstrip("/")
    host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL")
    return f"https://{host}" if host else "https://dev-community-pulse.vercel.app"


def _nice(name: str) -> str:
    return name[:1].upper() + name[1:]


def _plain(html: str) -> str:
    """Text of one list item without its "(link, link)" source references."""
    html = re.sub(r"\s*[(\[](?:\s*<a [^>]*>.*?</a>\s*,?\s*(?:and\s*)?)+[)\]]", "", html, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", "", html).split())


def _actions(brief_md: str, limit: int = 3) -> list[str]:
    """Sprint actions, kept short: the bold title when an item has one, otherwise its first sentence."""
    for s in parse_brief(md.markdown(brief_md or "")):
        if s["key"] == "sprint-actions":
            out = []
            for li in re.findall(r"<li>(.*?)</li>", s["body"], flags=re.S)[:limit]:
                lead = re.match(r"\s*(?:<p>)?\s*<strong>(.*?)</strong>\s*:", li, flags=re.S)
                text = _plain(lead.group(1)) if lead else re.split(r"(?<=[.!?])\s", _plain(li))[0]
                out.append(text.rstrip(".") + ".")
            return out
    return []


def _changes(metrics: list[dict], limit: int = 3) -> list[str]:
    moved = [m for m in metrics if m["count"] != m["prev_count"] and max(m["count"], m["prev_count"]) >= 2]
    moved.sort(key=lambda m: -abs(m["count"] - m["prev_count"]))
    out = []
    for m in moved[:limit]:
        if m["prev_count"] == 0:
            out.append(f"{_nice(m['pain_point'])} is new this week ({m['count']} mentions).")
        else:
            word = "up" if m["count"] > m["prev_count"] else "down"
            out.append(f"{_nice(m['pain_point'])} is {word} from {m['prev_count']} to {m['count']} mentions.")
    return out


def build_email(brief_md: str, metrics: list[dict], week: str) -> tuple[str, str, str]:
    """Return (subject, html, text)."""
    pretty_week = date.fromisoformat(week).strftime("%d %b %Y").lstrip("0")
    total = sum(m["count"] for m in metrics)
    unresolved = sum(m["unresolved_count"] for m in metrics)
    top = metrics[:3]
    changes = _changes(metrics) or ["No pain point moved noticeably compared with last week."]
    actions = _actions(brief_md) or [
        f"Look into {m['pain_point']}: {m['unresolved_count']} threads are still unresolved."
        for m in sorted(metrics, key=lambda m: -m["unresolved_count"])[:3] if m["unresolved_count"]
    ]
    url = app_url()
    subject = f"Weekly developer brief, week of {pretty_week}: {len(actions)} things to focus on"
    summary = (f"Developers raised {len(metrics)} pain points across {total} mentions this week. "
               f"{unresolved} of those mentions are still unresolved.")

    # ---- plain text ----
    lines = [f"Hi Sumit,", "", f"Here is your developer brief for the week of {pretty_week}.", "", summary, "",
             "TOP PAIN POINTS"]
    lines += [f"{i}. {_nice(m['pain_point'])}: {m['count']} mentions, {m['unresolved_count']} unresolved"
              for i, m in enumerate(top, 1)]
    lines += ["", "WHAT'S CHANGING"] + [f"- {c}" for c in changes]
    lines += ["", "FOCUS THIS WEEK"] + [f"{i}. {a}" for i, a in enumerate(actions, 1)]
    lines += ["", f"Read the full brief: {url}", "", "Dev Community Pulse",
              "Sent every Friday at 8:30 AM IST from Hacker News, Stack Overflow and GitHub discussions."]
    text = "\n".join(lines)

    # ---- html (inline styles and tables, so every mail client renders it the same) ----
    def heading(t: str) -> str:
        return (f'<tr><td style="padding:24px 0 8px;font-size:12px;font-weight:600;letter-spacing:.06em;'
                f'text-transform:uppercase;color:{MUTED};border-bottom:1px solid {LINE}">{t}</td></tr>')

    def row(content: str) -> str:
        return f'<tr><td style="padding:10px 0;border-bottom:1px solid {LINE};font-size:14px;line-height:1.5;color:{INK}">{content}</td></tr>'

    stat = lambda n, label: (f'<td width="33%" style="padding:12px 14px;background:#f8f9fb;border-radius:8px">'
                             f'<div style="font-size:20px;font-weight:700;color:{INK}">{n}</div>'
                             f'<div style="font-size:12px;color:{MUTED}">{label}</div></td>')
    top_rows = "".join(row(
        f'<b>{i}. {escape(_nice(m["pain_point"]))}</b>'
        f'<div style="font-size:13px;color:{MUTED}">{m["count"]} mentions · {m["unresolved_count"]} unresolved'
        f'{" · " + escape(m["category"]) if m.get("category") else ""}</div>') for i, m in enumerate(top, 1))
    change_rows = "".join(row(escape(c)) for c in changes)
    action_rows = "".join(row(
        f'<span style="display:inline-block;width:22px;height:22px;line-height:22px;text-align:center;border-radius:50%;'
        f'background:#e6f6f1;color:{GREEN};font-size:12px;font-weight:700;margin-right:8px">{i}</span>{escape(a)}')
        for i, a in enumerate(actions, 1))

    html = f"""<!doctype html><html><body style="margin:0;padding:0;background:#f3f5f8">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f5f8;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid {LINE};border-radius:12px;font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif">
<tr><td style="padding:28px 32px 8px">
  <div style="font-size:12px;font-weight:600;color:{GREEN}">DEV COMMUNITY PULSE · WEEK OF {escape(pretty_week).upper()}</div>
  <h1 style="margin:10px 0 6px;font-size:22px;line-height:1.3;color:{INK}">Hi Sumit, here's your weekly brief</h1>
  <p style="margin:0;font-size:14px;line-height:1.6;color:{MUTED}">{escape(summary)}</p>
</td></tr>
<tr><td style="padding:16px 32px 0">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="6"><tr>
    {stat(len(metrics), "pain points")}{stat(total, "mentions")}{stat(unresolved, "unresolved")}
  </tr></table>
</td></tr>
<tr><td style="padding:0 32px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    {heading("Top pain points")}{top_rows}
    {heading("What's changing")}{change_rows}
    {heading("Focus this week")}{action_rows}
  </table>
</td></tr>
<tr><td style="padding:28px 32px 32px">
  <a href="{escape(url)}" style="display:inline-block;background:{GREEN};color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;padding:11px 20px;border-radius:8px">Read the full brief</a>
  <p style="margin:12px 0 0;font-size:13px;color:{MUTED}">Sources, trends and every pain point are on the dashboard.</p>
</td></tr>
</table>
<p style="margin:16px 0 0;font-size:12px;color:#9a9cab;font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif">
Sent every Friday at 8:30 AM IST from Hacker News, Stack Overflow and GitHub discussions.</p>
</td></tr></table>
</body></html>"""
    return subject, html, text
