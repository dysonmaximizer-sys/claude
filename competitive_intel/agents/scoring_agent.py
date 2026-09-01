"""
Scoring agent — assesses the competitive significance of each detected change.

Runs monthly across all unscored changes in Notion.
Outputs a score (1–10) and brief reasoning for each change.
Uses prompt caching on the system prompt to reduce API costs.
"""

import json
import logging

import anthropic

from integrations.anthropic_retry import response_text, retry_transient
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, SCORE_GUIDE

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


@retry_transient
def _create(**kwargs):
    """messages.create with backoff on 429/5xx/connection errors."""
    return client.messages.create(**kwargs)


SYSTEM_PROMPT = f"""You are a senior competitive intelligence analyst for Maximizer, \
a B2B SaaS CRM built for financial services — specifically wealth management and insurance advisory firms.

Your job is to assess the competitive significance of a detected change on a competitor's website \
and score it from 1 to 10 using this rubric:

{SCORE_GUIDE}

Each change carries a Tier label telling you how much weight its source deserves:
- Tier 1 — direct, head-to-head competitors for our core market. Weight these most heavily.
- Tier 2 — genuine competitors, less directly aimed at our market. Relevant, rarely urgent alone.
- Ankle Biter — monitor only. A change here has to be genuinely consequential to reach the upper bands.
- Frenemies — AI meeting-notes and client-intelligence assistants that integrate with CRMs, ours included. Do not weight them as heavily as Tier 1, but do not dismiss them either: there is substantial overlap with our own product features and they target the same advisors we do, so feature expansion, CRM integrations, and positioning moves from them are worth staying on top of.

Tier adjusts how much weight a change carries; it never overrides the rubric. A cosmetic change is still a 1 or 2 no matter whose site it is on, and a major pricing or product move is still high-impact even from an Ankle Biter.

When scoring, consider:
- Does this change affect our core differentiators (financial services focus, advisor workflows, compliance support)?
- Does it signal a strategic shift toward our target market (wealth/insurance advisors)?
- Does it affect pricing or packaging in a way that could shift buying decisions?
- Is this a direct attack on Maximizer's positioning or features?

Respond ONLY with a JSON object. No prose, no markdown.
Format: {{"score": <integer 1-10>, "reasoning": "<one sentence>", "category": "<Pricing|Feature|Messaging|Integration|Other>"}}
"""


def score_change(
    competitor_name: str,
    tier: str,
    category: str,
    url: str,
    raw_change: str,
) -> tuple[int, str, str]:
    """
    Score a single competitive change.

    Returns: (score, reasoning, refined_category)
    """
    user_content = f"""Competitor: {competitor_name} (Tier: {tier})
Initial category guess: {category}
Source URL: {url}

Detected change:
---
{raw_change[:3000]}
---

Score this change for competitive significance."""

    try:
        message = _create(
            model=CLAUDE_MODEL,
            max_tokens=256,
            thinking={"type": "disabled"},
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},  # cache system prompt across batch
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )

        result = json.loads(response_text(message).strip())
        score = int(result.get("score", 1))
        reasoning = result.get("reasoning", "")
        refined_category = result.get("category", category)

        # Clamp score to valid range
        score = max(1, min(10, score))
        return score, reasoning, refined_category

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error("Failed to parse scoring response for %s: %s", competitor_name, e)
        return 1, "Scoring failed — manual review required", category
    except anthropic.APIError as e:
        logger.error("Anthropic API error during scoring: %s", e)
        raise
