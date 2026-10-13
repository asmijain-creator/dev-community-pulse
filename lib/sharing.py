"""Shared reports: link tokens, snapshot storage, access checks and the plain-text summary.

Links: each report gets a random nonce. The link token is HMAC-SHA256(server secret, nonce), so the server
can show the owner the link again, but the database holds neither the token nor anything that produces it
without the secret. Lookups use SHA-256(token). Tokens are 43 URL-safe characters (256 bits).

The secret is SHARE_LINK_SECRET, or the Supabase service key when that isn't set (already server-only).
Changing the secret invalidates every existing link.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

KINDS = {"pain_point": "Pain point", "opportunity": "Opportunity", "combined": "Intelligence report",
         "weekly": "Weekly report"}
VISIBILITY = {"unlisted": "Unlisted link", "private": "Private"}
EXPIRY_DAYS = {"never": None, "1": 1, "7": 7, "30": 30, "90": 90}
MAX_TITLE, MAX_INTRO = 140, 2000
_TOKEN_RX = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _secret() -> bytes:
    s = os.getenv("SHARE_LINK_SECRET") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not s:
        raise RuntimeError("No server secret for share links (set SHARE_LINK_SECRET)")
    return s.encode()


def token_for(nonce: str) -> str:
    mac = hmac.new(_secret(), nonce.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def valid_token(token: str) -> bool:
    return bool(_TOKEN_RX.match(token or ""))


def new_link() -> tuple[str, str, str]:
    """(nonce, token, token_hash) for a new report."""
    nonce = secrets.token_hex(16)
    tok = token_for(nonce)
    return nonce, tok, token_hash(tok)


def clean_text(s: str | None, n: int) -> str:
    """Plain text only: control characters removed, whitespace tidied, length capped. Rendered escaped."""
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s or "")
    s = "\n".join(" ".join(line.split()) for line in s.replace("\r\n", "\n").split("\n"))
    return re.sub(r"\n{3,}", "\n\n", s).strip()[:n]


def safe_url(u: str | None) -> str | None:
    return u if isinstance(u, str) and u.startswith(("https://", "http://")) else None


def expiry(choice: str, now: datetime) -> datetime | None:
    """'never', a number of days from EXPIRY_DAYS, or a YYYY-MM-DD date (end of that day, UTC)."""
    if choice in EXPIRY_DAYS:
        d = EXPIRY_DAYS[choice]
        return now + timedelta(days=d) if d else None
    try:
        day = datetime.strptime(choice, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    except ValueError:
        raise ValueError("Expiry must be a listed option or a date")
    if day <= now:
        raise ValueError("Expiry date must be in the future")
    return day


def _ts(iso: str | None) -> datetime | None:
    try:
        d = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def status(row: dict, now: datetime) -> str:
    """active | revoked | expired. Checked on the server for every view."""
    if row.get("revoked_at"):
        return "revoked"
    exp = _ts(row.get("expires_at"))
    if exp and exp <= now:
        return "expired"
    return "active"


# ---------- storage ----------
def create(sb, kind: str, title: str, refs: list[dict], snapshot: dict, visibility: str,
           expires_at: datetime | None) -> tuple[dict, str]:
    nonce, tok, th = new_link()
    row = sb.table("shared_reports").insert({
        "kind": kind, "title": title, "refs": refs, "snapshot": snapshot, "visibility": visibility,
        "token_hash": th, "token_nonce": nonce, "expires_at": expires_at.isoformat() if expires_at else None,
    }).execute().data[0]
    return row, tok


def by_token(sb, token: str) -> dict | None:
    if not valid_token(token):
        return None
    rows = sb.table("shared_reports").select("*").eq("token_hash", token_hash(token)).limit(1).execute().data
    return rows[0] if rows else None


def by_id(sb, rid: int) -> dict | None:
    rows = sb.table("shared_reports").select("*").eq("id", rid).limit(1).execute().data
    return rows[0] if rows else None


def all_reports(sb) -> list[dict]:
    return sb.table("shared_reports").select("id,kind,title,visibility,token_nonce,created_at,expires_at,revoked_at,"
                                             "last_accessed_at").order("created_at", desc=True).limit(200).execute().data or []


def touch(sb, row: dict, now: datetime) -> None:
    """Record that the report was opened, at most once an hour. No visitor information is stored."""
    last = _ts(row.get("last_accessed_at"))
    if last is None or now - last > timedelta(hours=1):
        sb.table("shared_reports").update({"last_accessed_at": now.isoformat()}).eq("id", row["id"]).execute()


# ---------- copy summary ----------
def _n(x, word):
    return f"{x} {word}{'' if x == 1 else 's'}"


def summary_text(snap: dict, link: str | None = None) -> str:
    """Plain text for Slack, WhatsApp, email or a planning doc. Only facts from the snapshot."""
    out = [f"*{snap['title']}*", f"DevvIT {KINDS.get(snap['kind'], 'report').lower()} · {snap['generated_at'][:10]}"]
    if snap.get("intro"):
        out += ["", snap["intro"]]
    for s in snap.get("sections", []):
        out.append("")
        if s["type"] == "pain_point":
            if len(snap["sections"]) > 1:
                out.append(f"*{s['title']}* (pain point)")
            out.append(s["explanation"])
            if s.get("why"):
                out.append(f"Why it matters: {s['why']}")
            if s.get("trend_text"):
                out.append(f"Trend: {s['trend_text']}")
            out.append(f"Evidence: {s['evidence_text']}")
            out += [f"• {t['title']} — {t['url']}" for t in s["threads"][:3]]
        elif s["type"] == "opportunity":
            if len(snap["sections"]) > 1:
                out.append(f"*{s['title']}* (opportunity)")
            if s.get("score") is not None:
                out.append(f"DevvIT priority score: {s['score']:.0f}/100 (ranks where to look first; not proof of demand)")
            out.append(s["explanation"])
            out.append(f"Evidence: {s['evidence_text']}")
            out += [f"• {t['title']} — {t['url']}" for t in s["threads"][:3]]
        elif s["type"] == "trends" and s["items"]:
            out.append("*Emerging trends*")
            out += [f"• {t['label']}: {t['reason']}" for t in s["items"][:5]]
        elif s["type"] == "brief":
            out.append(f"Top pain points this week: " + "; ".join(f"{p['title']} ({p['mentions']})" for p in s["top"][:5]))
    if link:
        out += ["", f"Full report: {link}"]
    return "\n".join(out).strip()
