"""Live developer-community sources. Each fetcher returns Posts for one keyword since a cutoff."""
import asyncio
from datetime import datetime, timezone

import httpx

from .models import Post, clean_text

USER_AGENT = "dev-community-pulse/1.0 (weekly PM digest)"


class SourceError(Exception):
    pass


async def get_json(client: httpx.AsyncClient, url: str, *, params=None, headers=None, retries: int = 2) -> dict:
    """GET with retry + backoff on rate limits (429/403 rate) and server errors."""
    for attempt in range(retries + 1):
        try:
            resp = await client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            if attempt == retries:
                raise SourceError(f"{url}: {exc.__class__.__name__}") from exc
            await asyncio.sleep(2 ** attempt)
            continue
        rate_limited = resp.status_code == 429 or (
            resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0"
        )
        if resp.status_code < 400:
            return resp.json()
        if (rate_limited or resp.status_code >= 500) and attempt < retries:
            wait = min(float(resp.headers.get("retry-after", 2 ** (attempt + 1))), 20)
            await asyncio.sleep(wait)
            continue
        raise SourceError(f"{url}: HTTP {resp.status_code}")
    raise SourceError(f"{url}: retries exhausted")


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


# ---------- Hacker News (Algolia search API, no key) ----------

async def fetch_hackernews(client: httpx.AsyncClient, keyword: str, since: datetime, limit: int, **_) -> list[Post]:
    data = await get_json(
        client,
        "https://hn.algolia.com/api/v1/search",
        params={
            "query": keyword,
            "tags": "story",
            "numericFilters": f"created_at_i>{_ts(since)}",
            "hitsPerPage": limit,
        },
    )
    return [parse_hn_hit(hit, keyword) for hit in data.get("hits", [])]


def parse_hn_hit(hit: dict, keyword: str) -> Post:
    item_id = str(hit["objectID"])
    return Post(
        source="hackernews",
        external_id=item_id,
        title=clean_text(hit.get("title"), 300),
        body=clean_text(hit.get("story_text") or hit.get("url") or ""),
        url=f"https://news.ycombinator.com/item?id={item_id}",
        score=int(hit.get("points") or 0),
        comments=int(hit.get("num_comments") or 0),
        created_at=datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc),
        matched_keywords=[keyword],
    )


# ---------- Stack Overflow (Stack Exchange API; key optional but raises daily quota 300 -> 10k) ----------

async def fetch_stackoverflow(client: httpx.AsyncClient, keyword: str, since: datetime, limit: int,
                              stackexchange_key: str = "", **_) -> list[Post]:
    params = {
        "order": "desc",
        "sort": "activity",
        "q": keyword,
        "fromdate": _ts(since),
        "site": "stackoverflow",
        "pagesize": limit,
        "filter": "withbody",
    }
    if stackexchange_key:
        params["key"] = stackexchange_key
    data = await get_json(client, "https://api.stackexchange.com/2.3/search/advanced", params=params)
    if data.get("backoff"):  # API asks us to pause before the next call
        await asyncio.sleep(min(int(data["backoff"]), 10))
    return [parse_so_item(item, keyword) for item in data.get("items", [])]


def parse_so_item(item: dict, keyword: str) -> Post:
    return Post(
        source="stackoverflow",
        external_id=str(item["question_id"]),
        title=clean_text(item.get("title"), 300),
        body=clean_text(item.get("body")),
        url=item.get("link", ""),
        score=int(item.get("score") or 0),
        comments=int(item.get("answer_count") or 0),
        created_at=datetime.fromtimestamp(item["creation_date"], tz=timezone.utc),
        is_answered=bool(item.get("is_answered")),
        matched_keywords=[keyword],
    )


# ---------- GitHub issues & PR discussions (search API; token raises limit 10 -> 30 req/min) ----------

async def fetch_github(client: httpx.AsyncClient, keyword: str, since: datetime, limit: int,
                       github_token: str = "", **_) -> list[Post]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    query = f'"{keyword}" in:title,body created:>={since.date().isoformat()} is:issue'
    # Default "best match" ranking: sorting by comments surfaces bot/agent log threads.
    data = await get_json(
        client,
        "https://api.github.com/search/issues",
        params={"q": query, "per_page": limit},
        headers=headers,
    )
    return [parse_github_item(item, keyword) for item in data.get("items", []) if is_human_discussion(item)]


GITHUB_MAX_COMMENTS = 300  # threads beyond this are almost always automated status/log boards


def is_human_discussion(item: dict) -> bool:
    user = item.get("user") or {}
    if user.get("type") == "Bot" or str(user.get("login", "")).endswith("[bot]"):
        return False
    return int(item.get("comments") or 0) <= GITHUB_MAX_COMMENTS


def parse_github_item(item: dict, keyword: str) -> Post:
    created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
    return Post(
        source="github",
        external_id=str(item["id"]),
        title=clean_text(item.get("title"), 300),
        body=clean_text(item.get("body")),
        url=item.get("html_url", ""),
        score=int((item.get("reactions") or {}).get("total_count") or 0),
        comments=int(item.get("comments") or 0),
        created_at=created,
        is_answered=item.get("state") == "closed",
        matched_keywords=[keyword],
    )


# Per-source pacing so we stay under each API's rate limit.
# (max concurrent requests, seconds to wait after each request)
SOURCES = {
    "hackernews": (fetch_hackernews, 4, 0.0),
    "stackoverflow": (fetch_stackoverflow, 2, 0.2),
    "github": (fetch_github, 1, 2.1),  # 30/min with a token
}
GITHUB_DELAY_NO_TOKEN = 6.5            # 10/min without a token
GITHUB_MAX_KEYWORDS_NO_TOKEN = 8       # keeps the run inside Vercel's time limit
