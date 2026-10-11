"""Write the weekly brief with Gemini. Numbers come from Python/SQL,
Gemini only writes the prose around them. Every claim must link to a real post.
"""
import os

from google import genai
from google.genai import types

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")


def write_brief(metrics: list[dict], examples: dict[str, list[dict]]) -> str:
    """
    metrics: [{pain_point, category, count, prev_count, change_pct, trend,
               unresolved_count, engagement}] ranked by count desc
    examples: {pain_point: [{title, url}, ...]}
    """
    metrics_lines = []
    for m in metrics:
        metrics_lines.append(
            f"- {m['pain_point']} ({m['category']}): {m['count']} mentions, "
            f"prev {m['prev_count']}, {m['change_pct']:+.0f}% {m['trend']}, "
            f"{m['unresolved_count']} unresolved, engagement {m['engagement']}"
        )
    metrics_block = "\n".join(metrics_lines) or "(no metrics)"

    ex_blocks = []
    for pp, posts in examples.items():
        links = "\n".join(f"  - [{(p['title'] or '')[:120]}]({p['url']})" for p in posts[:3])
        ex_blocks.append(f"PAIN POINT: {pp}\n{links}")
    ex_block = "\n\n".join(ex_blocks) or "(none)"

    prompt = f"""Write a weekly product-opportunity brief for Sumit, the sole PM at a
startup building a code-review automation tool.

Use ONLY the data below. Every concrete claim MUST include an inline markdown link
to one of the evidence posts. Do not invent numbers. If a section has no data, say so.

METRICS THIS WEEK (ranked by mentions):
{metrics_block}

EVIDENCE POSTS (use these inline links):
{ex_block}

Required sections (## headers, in this order):

## Top 5 pain points this week
Ranked list. Each item: pain point, mention count, 1-2 inline links.

## Trending
What is rising, falling, or new vs last week. Only call something a trend when
mention count is 3 or more. State the actual counts, not just percentages.

## Unsolved opportunities
Pain points with high unresolved_count — these are product gaps worth building for.
Say briefly why existing tools fail based on the evidence.

## Out of scope
Complaints and doubts about code-review tools that are outside the product's focus right
now, drawn from the posts. Context only, not priorities: keep it to 2-4 short bullets.

## 3 actions for Monday sprint
Three concrete, specific actions, each tied to one pain point and one evidence link.

Tone: direct, no filler, no hype. Lead with evidence. Short paragraphs."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    return resp.text or "_Gemini returned empty response._"
