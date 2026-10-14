"""Building Now sources beyond Show HN: what developers are building and launching in public.

- GitHub: repositories created in each week, most starred first (the search API's current star count, not
  star growth). Each repo's topics and language are kept for the industry view.
- Hacker News: "Launch HN" posts, and top-level replies in "Ask HN: What are you working on?" threads.
- Dev.to: the most-reacted #showdev and #buildinpublic posts of the last weeks.
- Product Hunt: each week's most-voted launches, only when PRODUCT_HUNT_TOKEN is set (free developer token
  from producthunt.com/v2/oauth/applications; check their API terms for your use).

Reddit is not collected: its API needs an app login and its free tier is for non-commercial use.

Parsers are pure functions (tested without network); fetchers raise on HTTP errors so the caller can record
a failed source and keep everything else. Every post comes back in the same shape as Show HN posts.
"""
import os
from datetime import datetime, timedelta, timezone

import httpx

from lib.collectors import HN_URL, HTTP_TIMEOUT, _strip_html

GH_REPOS_URL = "https://api.github.com/search/repositories"
HN_ITEM_URL = "https://hn.algolia.com/api/v1/items/{}"
DEVTO_URL = "https://dev.to/api/articles"
PH_URL = "https://api.producthunt.com/v2/api/graphql"

# Posts sampled per complete week and origin, most upvoted / starred first, so weeks stay comparable.
PER_WEEK = {"show_hn": 40, "gh_repo": 25, "launch_hn": 10, "devto": 20, "producthunt": 20}
WAWO_PER_THREAD = 40        # replies taken from each "What are you working on?" thread, most discussed first
WAWO_MIN_CHARS = 80         # shorter replies rarely say what is being built
DEVTO_TAGS = ("showdev", "buildinpublic")
GH_MIN_STARS = 10

ORIGINS = {"show_hn": "Show HN", "launch_hn": "Launch HN", "hn_wawo": "Ask HN: What are you working on?",
           "gh_repo": "New GitHub repositories", "devto": "Dev.to #showdev / #buildinpublic",
           "producthunt": "Product Hunt launches", "posts": "DevvIT pain point threads"}

_PH_QUERY = """query($after: DateTime, $before: DateTime, $n: Int) {
  posts(order: VOTES, postedAfter: $after, postedBefore: $before, first: $n) { edges { node {
    id name tagline description url website votesCount commentsCount createdAt
    topics(first: 5) { edges { node { name } } } } } } }"""


def _url(u) -> str | None:
    return u if isinstance(u, str) and u.startswith(("https://", "http://")) else None


def _ts(created_at_i) -> str | None:
    return datetime.fromtimestamp(created_at_i, tz=timezone.utc).isoformat() if isinstance(created_at_i, (int, float)) else None


def _range(start: datetime, end: datetime) -> str:
    return f"created_at_i>={int(start.timestamp())},created_at_i<{int(end.timestamp())}"


# ---------- parsers ----------
def parse_github_repos(data: dict) -> list[dict]:
    out = []
    for r in (data or {}).get("items") or []:
        url = _url(r.get("html_url"))
        if not r.get("id") or not r.get("created_at") or r.get("fork") or not url:
            continue
        name = r.get("full_name") or r.get("name") or ""
        desc = " ".join((r.get("description") or "").split())
        topics = [t for t in r.get("topics") or [] if isinstance(t, str) and t][:10]
        body = "\n".join(x for x in (desc, f"Language: {r['language']}" if r.get("language") else "",
                                     f"Topics: {', '.join(topics)}" if topics else "") if x)
        out.append({"id": f"ghrepo:{r['id']}", "source": "github", "origin": "gh_repo",
                    "title": f"{name}: {desc}" if desc else name, "body": body, "discussion_url": url,
                    "project_url": _url(r.get("homepage")), "score": r.get("stargazers_count") or 0, "comments": 0,
                    "created_at": r["created_at"], "topics": topics, "language": r.get("language") or None})
    return out


def parse_hn_launches(data: dict) -> list[dict]:
    out = []
    for h in (data or {}).get("hits") or []:
        pid, title = h.get("objectID"), h.get("title") or ""
        if not pid or not _ts(h.get("created_at_i")) or not title.lower().startswith("launch hn"):
            continue
        out.append({"id": f"hn:{pid}", "source": "hn", "origin": "launch_hn", "title": title,
                    "body": _strip_html(h.get("story_text")), "discussion_url": f"https://news.ycombinator.com/item?id={pid}",
                    "project_url": _url(h.get("url")), "score": h.get("points") or 0, "comments": h.get("num_comments") or 0,
                    "created_at": _ts(h["created_at_i"])})
    return out


def parse_wawo_thread(data: dict, n: int = WAWO_PER_THREAD) -> list[dict]:
    """Top-level replies of an 'Ask HN: What are you working on?' thread; each reply is one developer's work."""
    thread = (data or {}).get("title") or "Ask HN: What are you working on?"
    out = []
    for c in (data or {}).get("children") or []:
        text = _strip_html(c.get("text"))
        if not c.get("id") or len(text.strip()) < WAWO_MIN_CHARS or not _ts(c.get("created_at_i")):
            continue
        out.append({"id": f"hn:{c['id']}", "source": "hn", "origin": "hn_wawo", "title": f"Reply to “{thread}”",
                    "body": text, "discussion_url": f"https://news.ycombinator.com/item?id={c['id']}", "project_url": None,
                    "score": 0, "comments": len(c.get("children") or []), "created_at": _ts(c["created_at_i"])})
    return sorted(out, key=lambda p: -p["comments"])[:n]


def parse_devto(articles: list, since: datetime) -> list[dict]:
    out = []
    for a in articles or []:
        url, published = _url(a.get("url")), a.get("published_at")
        if not a.get("id") or not url or not published:
            continue
        try:
            if datetime.fromisoformat(published.replace("Z", "+00:00")) < since:
                continue
        except ValueError:
            continue
        tags = a.get("tag_list") if isinstance(a.get("tag_list"), list) else []
        body = "\n".join(x for x in ((a.get("description") or "").strip(), f"Tags: {', '.join(tags)}" if tags else "") if x)
        out.append({"id": f"devto:{a['id']}", "source": "devto", "origin": "devto", "title": a.get("title") or "",
                    "body": body, "discussion_url": url, "project_url": None,
                    "score": a.get("positive_reactions_count") or 0, "comments": a.get("comments_count") or 0,
                    "created_at": published})
    return out


def parse_producthunt(data: dict) -> list[dict]:
    if (data or {}).get("errors"):
        raise ValueError(f"Product Hunt API error: {str(data['errors'])[:200]}")
    out = []
    for e in (((data or {}).get("data") or {}).get("posts") or {}).get("edges") or []:
        p = e.get("node") or {}
        url = _url(p.get("url"))
        if not p.get("id") or not url or not p.get("createdAt"):
            continue
        topics = [t["node"]["name"] for t in ((p.get("topics") or {}).get("edges") or []) if (t.get("node") or {}).get("name")]
        body = "\n".join(x for x in ((p.get("description") or "").strip(), f"Topics: {', '.join(topics)}" if topics else "") if x)
        out.append({"id": f"ph:{p['id']}", "source": "producthunt", "origin": "producthunt",
                    "title": f"{p.get('name') or ''}: {p.get('tagline') or ''}".strip(": "), "body": body,
                    "discussion_url": url, "project_url": _url(p.get("website")), "score": p.get("votesCount") or 0,
                    "comments": p.get("commentsCount") or 0, "created_at": p["createdAt"]})
    return out


# ---------- fetchers ----------
async def github_week(client: httpx.AsyncClient, start: datetime, end: datetime, n: int) -> list[dict]:
    last = (end - timedelta(seconds=1)).date()
    headers = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    r = await client.get(GH_REPOS_URL, headers=headers, timeout=HTTP_TIMEOUT, params={
        "q": f"created:{start.date()}..{last} stars:>={GH_MIN_STARS} fork:false",
        "sort": "stars", "order": "desc", "per_page": min(n, 100)})
    r.raise_for_status()
    return parse_github_repos(r.json())


async def launch_hn_week(client: httpx.AsyncClient, start: datetime, end: datetime, n: int) -> list[dict]:
    r = await client.get(HN_URL, timeout=HTTP_TIMEOUT, params={
        "query": "Launch HN", "tags": "story", "restrictSearchableAttributes": "title", "hitsPerPage": n,
        "numericFilters": _range(start, end)})
    r.raise_for_status()
    return parse_hn_launches(r.json())


async def wawo_replies(client: httpx.AsyncClient, since: datetime) -> list[dict]:
    r = await client.get(HN_URL, timeout=HTTP_TIMEOUT, params={
        "query": "What are you working on", "tags": "ask_hn", "restrictSearchableAttributes": "title",
        "hitsPerPage": 5, "numericFilters": f"created_at_i>={int(since.timestamp())},num_comments>=10"})
    r.raise_for_status()
    out = []
    for h in r.json().get("hits") or []:
        if "working on" not in (h.get("title") or "").lower():
            continue
        t = await client.get(HN_ITEM_URL.format(h["objectID"]), timeout=HTTP_TIMEOUT * 2)
        t.raise_for_status()
        out += parse_wawo_thread(t.json())
    return out


async def devto_recent(client: httpx.AsyncClient, since: datetime) -> list[dict]:
    days = max(1, (datetime.now(timezone.utc) - since).days + 1)
    out, seen = [], set()
    for tag in DEVTO_TAGS:
        r = await client.get(DEVTO_URL, timeout=HTTP_TIMEOUT, params={"tag": tag, "top": days, "per_page": 100})
        r.raise_for_status()
        for p in parse_devto(r.json(), since):
            if p["id"] not in seen:
                seen.add(p["id"])
                out.append(p)
    return out


async def producthunt_week(client: httpx.AsyncClient, start: datetime, end: datetime, n: int, token: str) -> list[dict]:
    r = await client.post(PH_URL, timeout=HTTP_TIMEOUT, headers={"Authorization": f"Bearer {token}"},
                          json={"query": _PH_QUERY, "variables": {"after": start.isoformat(), "before": end.isoformat(),
                                                                  "n": min(n, 50)}})
    r.raise_for_status()
    return parse_producthunt(r.json())
