"""Tests for the extra Building Now sources: parsers, GitHub topics/languages and how sources share an update.

Run with:  python -m pytest -q
No network, database or Gemini access is needed: every API response below is a small made-up payload.
"""
import os
from datetime import date, datetime, timezone

import pytest

os.environ.update(SUPABASE_URL="x", SUPABASE_SERVICE_ROLE_KEY="x", GEMINI_API_KEY="x")

from lib import build_pipeline as BP, build_sources as S, building as B  # noqa: E402

SHAPE = {"id", "source", "origin", "title", "body", "discussion_url", "project_url", "score", "comments", "created_at"}


# ---------- parsers ----------
def test_github_repos_keep_topics_language_and_skip_forks():
    data = {"items": [
        {"id": 1, "full_name": "ana/tidepool", "description": "A  job queue\nin Rust", "html_url": "https://github.com/ana/tidepool",
         "homepage": "https://tidepool.example", "stargazers_count": 120, "created_at": "2026-10-05T10:00:00Z",
         "language": "Rust", "topics": ["queue", "rust"], "fork": False},
        {"id": 2, "full_name": "bo/fork", "html_url": "https://github.com/bo/fork", "created_at": "2026-10-05T10:00:00Z", "fork": True},
        {"id": 3, "full_name": "cy/nolink", "html_url": "javascript:x", "created_at": "2026-10-05T10:00:00Z"},
        {"id": 4, "full_name": "di/bare", "html_url": "https://github.com/di/bare", "homepage": "", "created_at": "2026-10-06T10:00:00Z"},
    ]}
    out = S.parse_github_repos(data)
    assert [p["id"] for p in out] == ["ghrepo:1", "ghrepo:4"]
    p = out[0]
    assert SHAPE <= set(p) and p["source"] == "github" and p["origin"] == "gh_repo"
    assert p["title"] == "ana/tidepool: A job queue in Rust" and p["score"] == 120
    assert p["topics"] == ["queue", "rust"] and p["language"] == "Rust"
    assert "Topics: queue, rust" in p["body"] and "Language: Rust" in p["body"]
    assert out[1]["title"] == "di/bare" and out[1]["project_url"] is None and out[1]["language"] is None


def test_hn_launches_only_keep_launch_posts():
    data = {"hits": [{"objectID": "9", "title": "Launch HN: Acme (YC W26) – build logs", "created_at_i": 1760000000,
                      "points": 80, "num_comments": 30, "url": "https://acme.example", "story_text": "<p>We built Acme</p>"},
                     {"objectID": "10", "title": "Why I quit my launch job", "created_at_i": 1760000000}]}
    out = S.parse_hn_launches(data)
    assert len(out) == 1 and out[0]["origin"] == "launch_hn" and out[0]["id"] == "hn:9"
    assert "We built Acme" in out[0]["body"] and out[0]["discussion_url"] == "https://news.ycombinator.com/item?id=9"


def test_wawo_replies_skip_short_ones_and_rank_by_discussion():
    long = "I'm building a local-first notes app with CRDT sync, mostly in Rust, and testing it with five friends now."
    data = {"title": "Ask HN: What are you working on? (October 2026)", "children": [
        {"id": 1, "text": long, "created_at_i": 1760000000, "children": [{}]},
        {"id": 2, "text": "Nothing much.", "created_at_i": 1760000000, "children": []},
        {"id": 3, "text": long + " Also a CLI.", "created_at_i": 1760000000, "children": [{}, {}, {}]},
        {"id": 4, "text": None, "created_at_i": 1760000000},
    ]}
    out = S.parse_wawo_thread(data, n=5)
    assert [p["id"] for p in out] == ["hn:3", "hn:1"]
    assert out[0]["origin"] == "hn_wawo" and out[0]["comments"] == 3
    assert out[0]["title"] == "Reply to “Ask HN: What are you working on? (October 2026)”"
    assert S.parse_wawo_thread(data, n=1)[0]["id"] == "hn:3"


def test_devto_skips_posts_older_than_the_window():
    since = datetime(2026, 9, 10, tzinfo=timezone.utc)
    arts = [{"id": 7, "title": "I built a habit tracker", "description": "Next.js + Supabase", "url": "https://dev.to/a/x",
             "published_at": "2026-10-01T09:00:00Z", "positive_reactions_count": 40, "comments_count": 5,
             "tag_list": ["showdev", "nextjs"]},
            {"id": 8, "title": "Old", "url": "https://dev.to/a/old", "published_at": "2026-08-01T09:00:00Z"},
            {"id": 9, "title": "No date", "url": "https://dev.to/a/nd"}]
    out = S.parse_devto(arts, since)
    assert [p["id"] for p in out] == ["devto:7"]
    assert out[0]["source"] == "devto" and out[0]["score"] == 40 and "Tags: showdev, nextjs" in out[0]["body"]


def test_producthunt_parses_launches_and_raises_on_api_errors():
    data = {"data": {"posts": {"edges": [{"node": {
        "id": "55", "name": "Shipfast", "tagline": "Deploy previews for every PR", "description": "Built on Fly.io",
        "url": "https://www.producthunt.com/posts/shipfast", "website": "https://shipfast.example", "votesCount": 300,
        "commentsCount": 20, "createdAt": "2026-10-07T07:01:00Z",
        "topics": {"edges": [{"node": {"name": "Developer Tools"}}]}}}]}}}
    out = S.parse_producthunt(data)
    assert out[0]["id"] == "ph:55" and out[0]["title"] == "Shipfast: Deploy previews for every PR"
    assert out[0]["source"] == "producthunt" and "Topics: Developer Tools" in out[0]["body"]
    with pytest.raises(ValueError):
        S.parse_producthunt({"errors": [{"message": "invalid token"}]})


# ---------- topics and languages ----------
def test_repo_tags_are_explicit_and_never_collide_with_technologies():
    post = {"id": "ghrepo:1", "language": "Python", "topics": ["python", "ai-agents", "ai-agents", "!!"]}
    rows = B.repo_tags(post, {"fastapi"})
    assert [(r["key"], r["kind"]) for r in rows] == [("python", "language"), ("topicpython", "topic"), ("topicaiagents", "topic")]
    assert all(r["explicit"] for r in rows)
    assert [r["key"] for r in B.repo_tags(post, {"python"})][0] == "topicpython"      # language already named by Gemini


def test_topics_are_counted_apart_from_technologies():
    it = {"posted_at": "2026-10-06T10:00:00+00:00", "category": "Developer tools", "techs": [
        {"key": "rust", "name": "Rust", "kind": "language", "explicit": True},
        {"key": "topicqueue", "name": "queue", "kind": "topic", "explicit": True},
        {"key": "redis", "name": "Redis", "kind": "database", "explicit": False}]}
    assert [c["label"] for c in B.top_counts([it], "tech")] == ["Rust"]
    assert [c["label"] for c in B.top_counts([it], "topic")] == ["queue"]
    assert [c["label"] for c in B.top_counts([it], "language")] == ["Rust"]
    rows = B.trends([it, it, it], date(2026, 10, 20), "topic")["rows"]
    assert [r["label"] for r in rows] == ["queue"]


# ---------- sharing an update between sources ----------
def test_interleave_lets_every_source_take_turns():
    posts = [{"origin": "gh_repo", "score": s} for s in (900, 800, 700)] + [{"origin": "show_hn", "score": s} for s in (50, 40)] \
        + [{"origin": "devto", "score": 5}]
    out = BP._interleave(posts)
    assert [(p["origin"], p["score"]) for p in out[:3]] == [("gh_repo", 900), ("show_hn", 50), ("devto", 5)]
    assert len(out) == len(posts)


def test_every_weekly_source_has_a_label():
    assert set(S.PER_WEEK) <= set(S.ORIGINS)


# ---------- Gemini request format ----------
def _enums(node):
    if isinstance(node, dict):
        if "enum" in node:
            yield node["enum"]
        for v in node.values():
            yield from _enums(v)
    elif isinstance(node, list):
        for v in node:
            yield from _enums(v)


def test_schema_has_no_empty_enum_values():
    # Gemini rejects the whole request when an enum contains "", which made every classification batch fail
    assert all(v != "" for e in _enums(BP._SCHEMA) for v in e)


def test_none_exclusion_reason_means_no_reason():
    post = {"id": "hn:1", "source": "hn", "origin": "show_hn", "discussion_url": "https://news.ycombinator.com/item?id=1",
            "title": "Show HN: Tidepool", "body": "I built Tidepool.", "created_at": "2026-10-05T10:00:00+00:00"}
    base = {"post_id": "hn:1", "activity_type": "open_source", "project_name": "Tidepool", "descriptive_title": "",
            "summary": "A queue.", "category": "Developer tools", "technologies": [], "stage": "not_stated",
            "stage_evidence": "", "blockers": [], "excerpt": "I built Tidepool.", "confidence": 0.9}
    item, _, _ = B.validate({**base, "is_build_activity": True, "exclusion_reason": "none"}, post, "m")
    assert item["relevant"] and item["exclusion_reason"] is None
    item, _, _ = B.validate({**base, "is_build_activity": False, "exclusion_reason": "none"}, post, "m")
    assert not item["relevant"] and item["exclusion_reason"] == "not_build"
