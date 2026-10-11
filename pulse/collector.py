"""Runs every keyword against every source in parallel, dedupes, and reports per-source health."""
import asyncio
from datetime import datetime

import httpx

from .config import Settings
from .models import Post
from .sources import (
    GITHUB_DELAY_NO_TOKEN,
    GITHUB_MAX_KEYWORDS_NO_TOKEN,
    SOURCES,
    USER_AGENT,
    SourceError,
)

MIN_TEXT_CHARS = 15  # skip posts with essentially no text


def normalize_keywords(raw: list[str]) -> list[str]:
    """Trim, drop empties, dedupe case-insensitively, keep first spelling."""
    seen, out = set(), []
    for kw in raw:
        kw = " ".join((kw or "").split())
        if kw and kw.lower() not in seen:
            seen.add(kw.lower())
            out.append(kw)
    return out


def merge_posts(batches: list[list[Post]]) -> dict[str, Post]:
    """Same post found via several keywords is stored once, with all matched keywords."""
    merged: dict[str, Post] = {}
    for batch in batches:
        for post in batch:
            if len(post.title) + len(post.body) < MIN_TEXT_CHARS:
                continue
            if post.id in merged:
                existing = merged[post.id]
                existing.matched_keywords = sorted(set(existing.matched_keywords) | set(post.matched_keywords))
            else:
                merged[post.id] = post
    return merged


async def _run_source(name: str, client: httpx.AsyncClient, keywords: list[str], since: datetime,
                      settings: Settings) -> tuple[list[list[Post]], dict]:
    fetch, concurrency, delay = SOURCES[name]
    status = {"ok": True, "queries": 0, "posts": 0, "errors": []}
    if name == "github" and not settings.github_token:
        delay = GITHUB_DELAY_NO_TOKEN
        if len(keywords) > GITHUB_MAX_KEYWORDS_NO_TOKEN:
            status["errors"].append(
                f"no GITHUB_TOKEN: only first {GITHUB_MAX_KEYWORDS_NO_TOKEN} keywords searched"
            )
            keywords = keywords[:GITHUB_MAX_KEYWORDS_NO_TOKEN]

    sem = asyncio.Semaphore(concurrency)

    async def one(keyword: str) -> list[Post]:
        async with sem:
            try:
                return await fetch(
                    client, keyword, since, settings.max_posts_per_query,
                    github_token=settings.github_token,
                    stackexchange_key=settings.stackexchange_key,
                )
            except (SourceError, KeyError, ValueError) as exc:
                status["errors"].append(f"{keyword}: {exc}")
                return []
            finally:
                status["queries"] += 1
                if delay:
                    await asyncio.sleep(delay)

    results = await asyncio.gather(*(one(kw) for kw in keywords))
    status["posts"] = sum(len(r) for r in results)
    # A source is "down" only if every query failed; partial failures are reported but not fatal.
    failed = sum(1 for e in status["errors"] if not e.startswith("no GITHUB_TOKEN"))
    status["ok"] = failed < len(keywords)
    status["errors"] = status["errors"][:5]
    return results, status


async def collect(keywords: list[str], since: datetime, settings: Settings) -> tuple[dict[str, Post], dict]:
    keywords = normalize_keywords(keywords)
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": USER_AGENT}) as client:
        outcomes = await asyncio.gather(
            *(_run_source(name, client, keywords, since, settings) for name in SOURCES)
        )
    batches, status = [], {}
    for name, (results, source_status) in zip(SOURCES, outcomes):
        batches.extend(results)
        status[name] = source_status
    return merge_posts(batches), status
