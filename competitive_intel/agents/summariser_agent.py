"""
Summariser agent — writes a concise, actionable summary for high-score changes.

Only runs for changes with significance score > ALERT_SCORE_THRESHOLD (default: 5).
Summaries are written to the Notion Changes database and included in Teams alerts.

Uses prompt caching on the system prompt to reduce API costs across a batch.
"""

import logging

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a competitive intelligence analyst writing briefings for \
the Sales, Marketing, Product, and CS teams at Maximizer — a B2B SaaS CRM for \
wealth management and insurance advisory firms.

When summarising a competitor change, your output must:
1. State clearly WHAT changed (1 sentence)
2. Explain WHY it matters to Maximizer (1–2 sentences) — focus on deal impact, market shift, or positioning threat
3. Suggest a RECOMMENDED ACTION for the relevant team (1 sentence)

Format your response exactly like this (no markdown, no extra commentary):

WHAT: <what changed>
WHY IT MATTERS: <why it matters to Maximizer>
RECOMMENDED ACTION: <what the team should do>

Keep the entire response under 100 words. Use plain, direct language — no jargon."""


def summarise_change(
    competitor_name: str,
    tier: str,
    category: str,
    score: int,
    score_reasoning: str,
    raw_change: str,
    url: str,
) -> str:
    """
    Generate a concise, actionable summary for a high-score competitive change.
    Returns the summary as a plain text string.
    """
    user_content = f"""Competitor: {competitor_name} (Tier: {tier})
Category: {category}
Significance score: {score}/10
Scoring rationale: {score_reasoning}
Source URL: {url}

Raw change text:
---
{raw_change[:3000]}
---

Write the competitive intelligence briefing."""

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        return message.content[0].text.strip()

    except anthropic.APIError as e:
        logger.error("Anthropic API error during summarisation for %s: %s", competitor_name, e)
        raise
