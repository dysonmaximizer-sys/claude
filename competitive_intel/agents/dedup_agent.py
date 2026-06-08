"""
Insight de-duplication agent — groups a single competitor's alert-worthy
changes by the underlying announcement they describe.

A competitor usually surfaces one announcement across several monitored pages
(homepage, pricing, blog, webinars, etc.) in the same scan crawl. Each page is
a genuinely separate change in changedetection.io and gets logged + scored
separately, but they all describe ONE event. Without grouping, the daily poll
fires one Teams alert per page — e.g. four near-identical cards for a single
"Custom Objects launch".

This agent clusters those pages so the daily poll can alert once per distinct
insight (one normal alert card, picked from the cluster), instead of once per
page. Suppressed pages still live in Notion and feed the monthly newsletter;
only the duplicate Teams cards are collapsed.

Uses prompt caching on the system prompt for consistency with the other agents.
"""

import json
import logging

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You group website changes detected on a single competitor's \
site by the underlying announcement or event they describe.

Competitors routinely reflect one announcement across multiple pages on the \
same day — a launch shows up on the homepage hero, the pricing table, a blog \
post, and a webinars/events page all at once. Those are ONE insight, not four.

You will be given a numbered list of changes detected for one competitor. \
Group them so that changes describing the same underlying announcement, \
feature, product, or event share a cluster. Changes that describe genuinely \
DIFFERENT and unrelated events belong in separate clusters.

When unsure whether two changes are the same event, keep them SEPARATE.

Respond ONLY with a JSON object. No prose, no markdown.
Format: {"clusters": [[<indices for insight A>], [<indices for insight B>], ...]}
Every index from the input must appear exactly once across all clusters."""


def _fallback(n: int) -> list[list[int]]:
    """One cluster per change — i.e. no grouping (pre-existing behaviour)."""
    return [[i] for i in range(n)]


def cluster_changes_by_insight(competitor_name: str, changes: list[dict]) -> list[list[int]]:
    """
    Group one competitor's alert-worthy changes by underlying insight.

    `changes` is a list of dicts, each with at least: `category`, `url`,
    `summary` (and optionally `raw_change`). Returns a list of clusters, where
    each cluster is a list of indices into `changes`.

    On any failure (API error, malformed response, non-partition result), falls
    back to one cluster per change — identical to the old one-alert-per-page
    behaviour, so de-dup never drops or merges incorrectly on error.
    """
    n = len(changes)
    if n <= 1:
        return _fallback(n)

    lines = []
    for i, c in enumerate(changes):
        summary = (c.get("summary") or c.get("raw_change") or "").strip()
        lines.append(
            f"[{i}] category={c.get('category', 'Other')} | url={c.get('url', '')}\n"
            f"    {summary[:600]}"
        )
    user_content = (
        f"Competitor: {competitor_name}\n"
        f"{n} changes detected in this poll:\n\n"
        + "\n\n".join(lines)
        + "\n\nGroup these changes by underlying announcement/insight."
    )

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=256,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        result = json.loads(message.content[0].text.strip())
        clusters = result.get("clusters", [])

        # Validate the result is a clean partition of range(n): every index
        # present exactly once, nothing out of range, nothing duplicated.
        flat = [idx for cluster in clusters for idx in cluster]
        if sorted(flat) != list(range(n)):
            logger.warning(
                "Insight clustering for %s returned a non-partition (%s) — "
                "falling back to one alert per change",
                competitor_name, clusters,
            )
            return _fallback(n)

        logger.info(
            "Insight clustering for %s: %d changes → %d distinct insight(s)",
            competitor_name, n, len(clusters),
        )
        return clusters

    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.error("Failed to parse clustering response for %s: %s", competitor_name, e)
        return _fallback(n)
    except anthropic.APIError as e:
        logger.error("Anthropic API error during clustering for %s: %s", competitor_name, e)
        return _fallback(n)
