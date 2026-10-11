"""Smoke-test the live sources without Supabase or Gemini.

    python scripts/check_sources.py "false positive" "flaky tests"
"""
import asyncio
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles choke on emoji in post titles

from pulse.collector import collect  # noqa: E402
from pulse.config import get_settings  # noqa: E402


async def main(keywords: list[str]) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=14)
    posts, status = await collect(keywords, since, get_settings())
    for name, s in status.items():
        print(f"{name:14} ok={s['ok']} queries={s['queries']} posts={s['posts']} errors={s['errors']}")
    print(f"\n{len(posts)} unique posts; by source: {dict(Counter(p.source for p in posts.values()))}")
    for post in sorted(posts.values(), key=lambda p: p.engagement, reverse=True)[:8]:
        print(f"  [{post.source}] {post.engagement:>4}  {post.title[:80]}  {post.url}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["false positive", "flaky tests", "code review"]))
