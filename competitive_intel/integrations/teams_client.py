"""
Microsoft Teams integration — sends alerts and newsletter announcements via
the Teams Workflows app (Power Automate flow created from a template like
"Send webhook alerts to [chat]" or "Post to a channel when a webhook
request is received").

The flow's webhook URL expects an Adaptive Card 1.5 JSON object as the POST
body. The flow posts that card to the configured chat or channel as Flow
bot. Office 365 Connectors / classic Incoming Webhooks are deprecated by
Microsoft — this module no longer uses the MessageCard format.

Setup for each destination chat or channel:
  1. In Teams, open the chat (or channel) and add a Workflow using a
     template named "Send webhook alerts to [chat]" or
     "Post to a channel when a webhook request is received".
  2. Copy the generated webhook URL (ends with `&sig=...`).
  3. Paste the URL into .env as TEAMS_GENERAL_WEBHOOK or
     TEAMS_WEBHOOK_<COMPETITOR_SLUG>.

If a per-competitor webhook isn't set, the general one is used. If neither
is set, alerts are logged locally and not posted to Teams.
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
    Return the webhook URL for a competitor destination, or the general one.
    Returns None if not yet configured (alerts will be skipped gracefully).
    """
    if competitor_slug:
        key = f"TEAMS_WEBHOOK_{competitor_slug.upper()}"
        url = os.environ.get(key, "")
        if url:
            return url
        logger.debug(
            "No Teams webhook configured for %s, falling back to general",
            competitor_slug,
        )

    general = os.environ.get("TEAMS_GENERAL_WEBHOOK", "")
    return general or None


# ── Adaptive Cards ────────────────────────────────────────────────────────────

def _build_alert_card(
    competitor: str,
    tier: str,
    category: str,
    score: int,
    summary: str,
    url: str,
    notion_url: str = "",
) -> dict:
    """Build an Adaptive Card for a competitive change alert."""
    score_emoji = "🔴" if score >= 8 else "🟡"

    if score >= 8:
        header_style = "attention"
    elif score >= 6:
        header_style = "warning"
    else:
        header_style = "default"

    body = [
        {
            "type": "Container",
            "style": header_style,
            "bleed": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": "Competitive Intelligence Alert",
                    "weight": "Bolder",
                    "size": "Medium",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": f"{competitor}: {category}",
                    "spacing": "None",
                    "isSubtle": True,
                    "wrap": True,
                },
            ],
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Competitor:",   "value": competitor},
                {"title": "Tier:",         "value": tier},
                {"title": "Category:",     "value": category},
                {"title": "Significance:", "value": f"{score_emoji} {score}/10"},
            ],
        },
        {
            "type": "TextBlock",
            "text": summary,
            "wrap": True,
            "spacing": "Medium",
        },
    ]

    # Notion button intentionally removed (Notion link is the broader Hub,
    # not the specific change page, and the source URL is more actionable).
    # The notion_url argument is kept for API compatibility but ignored here.
    actions = []
    if url:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "Open Source",
            "url": url,
        })

    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body,
    }
    if actions:
        card["actions"] = actions

    return card


def _build_newsletter_card(
    subject: str,
    body_preview: str,
    notion_url: str = "",
) -> dict:
    """Build an Adaptive Card announcing the monthly newsletter."""
    preview_text = body_preview[:500] + ("…" if len(body_preview) > 500 else "")

    body = [
        {
            "type": "Container",
            "style": "accent",
            "bleed": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": subject,
                    "weight": "Bolder",
                    "size": "Medium",
                    "wrap": True,
                },
            ],
        },
        {
            "type": "TextBlock",
            "text": preview_text,
            "wrap": True,
            "spacing": "Medium",
        },
    ]

    actions = []
    if notion_url:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "Read Full Newsletter",
            "url": notion_url,
        })

    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body,
    }
    if actions:
        card["actions"] = actions

    return card


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
    Post a competitive alert card to the competitor's Teams destination
    (or the general one if no per-competitor webhook is set).
    Returns True if the message was sent, False if Teams is not yet configured.
    """
    webhook = _get_webhook(competitor_slug)
    if not webhook:
        logger.warning(
            "Teams not configured for %s. Alert logged locally only. "
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
    """Post a newsletter announcement to the general Teams destination."""
    webhook = _get_webhook()
    if not webhook:
        logger.warning(
            "TEAMS_GENERAL_WEBHOOK not configured. Newsletter announcement "
            "skipped. Add it to .env to enable Teams delivery."
        )
        return False

    card = _build_newsletter_card(subject, body_preview, notion_url)
    _post_to_webhook(webhook, card)
    logger.info("Newsletter announcement sent to Teams")
    return True
