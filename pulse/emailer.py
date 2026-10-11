"""Sends the brief through Resend."""
import re

import markdown
import resend

_UNSAFE_HREF = re.compile(r'href="(?!https?://|#)[^"]*"', re.IGNORECASE)


def safe_markdown(content_md: str) -> str:
    """Markdown -> HTML without raw HTML or javascript: links (brief text can echo untrusted posts)."""
    html_out = markdown.markdown(content_md.replace("<", "&lt;"), extensions=["tables"])
    return _UNSAFE_HREF.sub('href="#"', html_out)


def render_html(content_md: str, dashboard_url: str = "") -> str:
    body = safe_markdown(content_md)
    link = f'<p><a href="{dashboard_url}">Open the dashboard</a></p>' if dashboard_url else ""
    return f"""<div style="font-family:Arial,sans-serif;max-width:720px;margin:auto;color:#1f2937;line-height:1.5">
<style>table{{border-collapse:collapse}}td,th{{border:1px solid #e5e7eb;padding:4px 8px;font-size:13px}}</style>
{body}{link}</div>"""


def send_brief(api_key: str, sender: str, recipients: str, subject: str, content_md: str,
               dashboard_url: str = "") -> str:
    """Returns the Resend email id. Raises on failure so the caller can record it."""
    resend.api_key = api_key
    result = resend.Emails.send({
        "from": sender,
        "to": [r.strip() for r in recipients.split(",") if r.strip()],
        "subject": subject,
        "html": render_html(content_md, dashboard_url),
    })
    return result["id"] if isinstance(result, dict) else getattr(result, "id", "")
