"""
Microsoft Teams integration — sends alerts and newsletter digests.

Uses incoming webhooks (simplest setup, no Azure app registration needed).

Setup for each channel:
  1. In Teams, open the channel → … → Connectors → Incoming Webhook
  2. Name it "Competitive Intel Bot", copy the webhook URL
  3. Paste the URL into .env as TEAMS_GENERAL_WEBHOOK or TEAMS_WEBHOOK_<SLUG>

TODO: Once Teams channels are created, add all webhook URLs to .env.
      Until then, alerts are logged locally and not posted to Teams.
"""

import logging
import os
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


# ── Webhook Resolution ────────────────────────────────────────────────────────

def _get_webhook(competitor_slug: Optional[str] = None) -> Optional[str]:
    """
    Return the webhook URL for a competitor channel, or the general channel.
    Returns None if not yet configured (alerts will be skipped gracefully).
    """
    from typing import Optional  # local import for forward-compat
    if competitor_slug:
        key = f"TEAMS_WEBHOOK_{competitor_slug.upper()}"
        url = os.environ.get(key, "")
        if url:
            return url
        logger.debug("No Teams webhook configured for %s — falling back to general", competitor_slug)

    general = os.environ.get("TEAMS_GENERAL_WEBHOOK", "")
    return general or None


# ── Message Cards ─────────────────────────────────────────────────────────────

def _build_alert_card(
    competitor: str,
    tier: str,
    category: str,
    score: int,
    summary: str,
    url: str,
    notion_url: str = "",
) -> dict:
    """Build a Teams Adaptive Card for a high-score competitive change."""
    score_emoji = "🔴" if score >= 8 else "🟡"
    facts = [
        {"title": "Competitor", "value": competitor},
        {"title": "Tier", "value": tier},
        {"title": "Category", "value": category},
        {"title": "Significance", "value": f"{score_emoji} {score}/10"},
    ]
    if url:
        facts.append({"title": "Source URL", "value": url})

    actions = []
    if notion_url:
        actions.append({
            "@type": "OpenUri",
            "name": "View in Notion",
            "targets": [{"os": "default", "uri": notion_url}],
        })

    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": "FF0000" if score >= 8 else "FFA500",
        "summary": f"Competitive alert: {competitor} ({score}/10)",
        "sections": [
            {
                "activityTitle": f"**Competitive Intelligence Alert**",
                "activitySubtitle": f"{competitor} — {category}",
                "facts": facts,
                "text": summary,
            }
        ],
        "potentialAction": actions,
    }


def _build_newsletter_card(subject: str, body_preview: str, notion_url: str = "") -> dict:
    """Build a Teams card announcing the monthly newsletter."""
    actions = []
    if notion_url:
        actions.append({
            "@type": "OpenUri",
            "name": "Read Full Newsletter",
            "targets": [{"os": "default", "uri": notion_url}],
        })

    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": "0078D4",
        "summary": subject,
        "sections": [
            {
                "activityTitle": f"**{subject}**",
                "text": body_preview[:500] + ("…" if len(body_preview) > 500 else ""),
            }
        ],
        "potentialAction": actions,
    }


# ── Send Functions ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _post_to_webhook(webhook_url: str, card: dict) -> None:
    response = requests.post(webhook_url, json=card, timeout=15)
    response.raise_for_status()


def send_competitive_alert(
    competitor: str,
    tier: str,
    category: str,
    score: int,
    summary: str,
    url: str,
    competitor_slug: str,
    notion_url: str = "",
) -> bool:
    """
    Post a competitive alert card to the competitor's Teams channel
    (or general channel if no per-competitor webhook is set).
    Returns True if the message was sent, False if Teams is not yet configured.
    """
    webhook = _get_webhook(competitor_slug)
    if not webhook:
        logger.warning(
            "Teams not configured for %s — alert logged locally only. "
            "Add TEAMS_WEBHOOK_%s to .env to enable Teams alerts.",
            competitor,
            competitor_slug.upper(),
        )
        return False

    card = _build_alert_card(competitor, tier, category, score, summary, url, notion_url)
    _post_to_webhook(webhook, card)
    logger.info("Teams alert sent for %s (score %d)", competitor, score)
    return True


def send_newsletter_announcement(
    subject: str,
    body_preview: str,
    notion_url: str = "",
) -> bool:
    """Post a newsletter announcement to the general Teams channel."""
    webhook = _get_webhook()
    if not webhook:
        logger.warning(
            "TEAMS_GENERAL_WEBHOOK not configured — newsletter announcement skipped. "
            "Add it to .env to enable Teams delivery."
        )
        return False

    card = _build_newsletter_card(subject, body_preview, notion_url)
    _post_to_webhook(webhook, card)
    logger.info("Newsletter announcement sent to Teams general channel")
    return True


# Fix missing Optional import at module level
from typing import Optional  # noqa: E402 — kept at bottom to avoid circular issues
