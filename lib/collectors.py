"""Live collectors: Hacker News (Algolia), Stack Overflow, GitHub Issues.

All sources are free and (mostly) unauthenticated. GitHub rate limits are
tight without a token — set GITHUB_TOKEN to raise them. Stack Exchange
accepts an optional `key` param (SO_KEY) that raises quota from 300/day
to 10k/day.

Reddit is deliberately skipped: it blocks server-side requests from
Vercel egress IPs unless you implement OAuth, which is out of scope for v1.
"""
import asyncio
import os
import re
from datetime import datetime, timedelta, timezone

import httpx

HN_URL = "https://hn.algolia.com/api/v1/search"
SO_URL = "https://api.stackexchange.com/2.3/search/advanced"
GH_URL = "https://api.github.com/search/issues"

MAX_PER_KW = 12  # cap per source per keyword to keep run inside Vercel timeout
HTTP_TIMEOUT = 15.0

_TAG_RX = re.compile(r"<[^>]+>")


def _strip_html(s: str | None) -> str:
    if not s:
        return ""
    return _TAG_RX.sub(" ", s)[:4000]


async def fetch_hn(client: httpx.AsyncClient, keyword: str, since_ts: int) -> list[dict]:
    r = await client.get(
        HN_URL,
        params={
            "query": keyword,
            "tags": "story",
            "numericFilters": f"created_at_i>{since_ts}",
            "hitsPerPage": MAX_PER_KW,
        },
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for h in r.json().get("hits", []):
        pid = h.get("objectID")
        if not pid:
            continue
        out.append({
            "id": f"hn:{pid}",
            "source": "hn",
            "title": h.get("title") or h.get("story_title") or "",
            "body": _strip_html(h.get("story_text") or h.get("comment_text")),
            "url": h.get("url") or f"https://news.ycombinator.com/item?id={pid}",
            "score": h.get("points") or 0,
            "comments": h.get("num_comments") or 0,
            "created_at": datetime.fromtimestamp(
                h["created_at_i"], tz=timezone.utc
            ).isoformat(),
        })
    return out


async def fetch_so(client: httpx.AsyncClient, keyword: str, since_ts: int) -> list[dict]:
    params = {
        "q": keyword,
        "fromdate": since_ts,
        "site": "stackoverflow",
        "pagesize": MAX_PER_KW,
        "order": "desc",
        "sort": "activity",
        "filter": "withbody",
    }
    if os.getenv("SO_KEY"):
        params["key"] = os.environ["SO_KEY"]
    r = await client.get(SO_URL, params=params, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    out = []
    for q in r.json().get("items", []):
        pid = q.get("question_id")
        if not pid:
            continue
        out.append({
            "id": f"so:{pid}",
            "source": "stackoverflow",
            "title": q.get("title") or "",
            "body": _strip_html(q.get("body")),
            "url": q.get("link"),
            "score": q.get("score") or 0,
            "comments": q.get("answer_count") or 0,
            "created_at": datetime.fromtimestamp(
                q["creation_date"], tz=timezone.utc
            ).isoformat(),
            # SO's own "answered" signal — hint for is_unresolved
            "_so_is_answered": q.get("is_answered", False),
        })
    return out


async def fetch_gh(client: httpx.AsyncClient, keyword: str, since_date: str) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    try:
        r = await client.get(
            GH_URL,
            params={
                "q": f"{keyword} created:>{since_date}",
                "per_page": MAX_PER_KW,
                "sort": "reactions",
            },
            headers=headers,
            timeout=HTTP_TIMEOUT + 5,
        )
    except httpx.HTTPError:
        return []
    if r.status_code in (403, 422, 429):
        # rate-limited or bad query — skip quietly
        return []
    r.raise_for_status()
    out = []
    for i in r.json().get("items", []):
        pid = i.get("id")
        if not pid:
            continue
        out.append({
            "id": f"gh:{pid}",
            "source": "github",
            "title": i.get("title") or "",
            "body": _strip_html(i.get("body")),
            "url": i.get("html_url"),
            "score": (i.get("reactions") or {}).get("total_count", 0),
            "comments": i.get("comments") or 0,
            "created_at": i.get("created_at"),
            "_gh_state": i.get("state"),
        })
    return out


async def collect(topics: list[dict], days_back: int = 7) -> list[dict]:
    """
    topics: [{id, category, keywords: [str]}].
    Returns deduped posts with topic_id attached.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days_back)
    since_ts = int(since.timestamp())
    since_date = since.date().isoformat()

    # Build task list: (source, keyword, topic_id, coro)
    jobs: list[tuple] = []
    async with httpx.AsyncClient(headers={"User-Agent": "dev-community-pulse/1.0"}) as client:
        for t in topics:
            for kw in t["keywords"]:
                jobs.append(("hn", kw, t["id"], fetch_hn(client, kw, since_ts)))
                jobs.append(("so", kw, t["id"], fetch_so(client, kw, since_ts)))
                jobs.append(("gh", kw, t["id"], fetch_gh(client, kw, since_date)))
        results = await asyncio.gather(*(j[3] for j in jobs), return_exceptions=True)

    dedup: dict[str, dict] = {}
    for (src, kw, tid, _), res in zip(jobs, results):
        if isinstance(res, Exception):
            print(f"[collect] {src} '{kw}' failed: {res}")
            continue
        for p in res:
            if p["id"] in dedup:
                # Already seen — but keep the first topic assignment
                continue
            p["topic_id"] = tid
            p["matched_keyword"] = kw
            dedup[p["id"]] = p
    return list(dedup.values())
