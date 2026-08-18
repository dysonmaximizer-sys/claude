"""
Microsoft Teams integration — sends alerts and newsletter announcements via
the Teams Workflows app (Power Automate flow created from a template like
"Send webhook alerts to [chat]" or "Post to a channel when a webhook
request is received").

The flow's webhook URL expects an Adaptive Card 1.5 JSON object as the POST
body. The flow posts that card to the configured chat or channel as Flow
bot. Office 365 Connectors / classic Incoming Webhooks are deprecated by
Microsoft — this module no longer uses the MessageCard format.

Routing: every alert goes to TEAMS_GENERAL_WEBHOOK. Per-competitor webhook
routing was removed on 2026-08-18 — all 11 TEAMS_WEBHOOK_<COMPETITOR> secrets
were null, so alerts already fell through to the general webhook while the code
and docs implied 11 live channels. Because one channel now carries every
competitor, the competitor name is the headline of each card rather than a
subtitle.

Setup:
  1. In Teams, open the chat (or channel) and add a Workflow using a
     template named "Send webhook alerts to [chat]" or
     "Post to a channel when a webhook request is received".
  2. Copy the generated webhook URL (ends with `&sig=...`).
  3. Paste the URL into .env as TEAMS_GENERAL_WEBHOOK.

If TEAMS_GENERAL_WEBHOOK is not set, alerts are logged locally and not posted.
"""

import logging
import os
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


# ── Webhook Resolution ────────────────────────────────────────────────────────

def _get_webhook() -> Optional[str]:
    """
    Return the single general webhook URL, or None if it isn't configured
    (in which case alerts are skipped gracefully rather than raising).
    """
    return os.environ.get("TEAMS_GENERAL_WEBHOOK", "") or None


# ── Adaptive Cards ────────────────────────────────────────────────────────────

def _strip_recommended_action(summary: str) -> str:
    """
    RECOMMENDED ACTION was removed from alerts (2026-08-04). The summariser
    prompt no longer produces it; this strip is a backstop so a stray emission
    never reaches a card.
    """
    return "\n".join(
        line for line in (summary or "").splitlines()
        if not line.strip().upper().startswith("RECOMMENDED ACTION:")
    ).strip()


def _score_emoji(score: int) -> str:
    return "🔴" if score >= 8 else "🟡"


def _header_style(top_score: int) -> str:
    if top_score >= 8:
        return "attention"
    if top_score >= 6:
        return "warning"
    return "default"


def _build_alert_card(
    competitor: str,
    tier: str,
    category: str,
    score: int,
    summary: str,
    url: str,
    notion_url: str = "",
) -> dict:
    """Build an Adaptive Card for a single competitive change alert."""
    summary = _strip_recommended_action(summary)

    body = [
        {
            "type": "Container",
            "style": _header_style(score),
            "bleed": True,
            "items": [
                # Competitor is the headline: one channel now carries every
                # competitor, so it has to be scannable at a glance.
                {
                    "type": "TextBlock",
                    "text": competitor,
                    "weight": "Bolder",
                    "size": "Large",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": f"Competitive Intelligence Alert · {category}",
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
                {"title": "Significance:", "value": f"{_score_emoji(score)} {score}/10"},
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


def _build_digest_card(items: list, title: str, subtitle: str = "") -> dict:
    """
    Build one Adaptive Card summarising several alert-worthy changes, grouped
    by competitor. Used by the backfill/rescue paths, where a dozens-of-cards
    burst would be unreadable.

    Each item needs: competitor, tier, category, score, summary, url,
    date_detected (any missing field degrades gracefully).
    """
    top_score = max((int(i.get("score") or 0) for i in items), default=0)

    grouped: dict = {}
    for item in items:
        grouped.setdefault(item.get("competitor") or "Unknown", []).append(item)

    body = [
        {
            "type": "Container",
            "style": _header_style(top_score),
            "bleed": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": title,
                    "weight": "Bolder",
                    "size": "Large",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": subtitle or f"{len(items)} change(s) across {len(grouped)} competitor(s)",
                    "spacing": "None",
                    "isSubtle": True,
                    "wrap": True,
                },
            ],
        }
    ]

    # Highest-scoring competitor first so the worst news is at the top.
    for competitor in sorted(
        grouped,
        key=lambda c: max(int(i.get("score") or 0) for i in grouped[c]),
        reverse=True,
    ):
        entries = sorted(grouped[competitor], key=lambda i: int(i.get("score") or 0), reverse=True)
        tier = entries[0].get("tier") or ""
        body.append({
            "type": "TextBlock",
            "text": f"**{competitor}**" + (f" · {tier}" if tier else ""),
            "wrap": True,
            "size": "Medium",
            "weight": "Bolder",
            "spacing": "Medium",
            "separator": True,
        })
        for entry in entries:
            score = int(entry.get("score") or 0)
            summary = _strip_recommended_action(entry.get("summary") or "")
            summary = " ".join(summary.split())
            if len(summary) > 260:
                summary = summary[:257].rstrip() + "…"
            date = (entry.get("date_detected") or "")[:10]
            meta = " · ".join(p for p in [f"{_score_emoji(score)} {score}/10",
                                          entry.get("category") or "", date] if p)
            link = f" [source]({entry['url']})" if entry.get("url") else ""
            body.append({
                "type": "TextBlock",
                "text": f"{meta} — {summary}{link}",
                "wrap": True,
                "spacing": "Small",
            })

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body,
    }


# ── Send Functions ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _post_to_webhook(webhook_url: str, card: dict) -> None:
    response = requests.post(webhook_url, json=card, timeout=15)
    response.raise_for_status()


def _warn_unconfigured(context: str) -> None:
    logger.warning(
        "Teams not configured — %s logged locally only. "
        "Add TEAMS_GENERAL_WEBHOOK to .env (or to the workflow secrets) to "
        "enable Teams alerts.",
        context,
    )


def send_competitive_alert(
    competitor: str,
    tier: str,
    category: str,
    score: int,
    summary: str,
    url: str,
    notion_url: str = "",
) -> bool:
    """
    Post a competitive alert card to the general Teams destination.
    Returns True if the message was sent, False if Teams is not yet configured.
    """
    webhook = _get_webhook()
    if not webhook:
        _warn_unconfigured(f"alert for {competitor}")
        return False

    card = _build_alert_card(competitor, tier, category, score, summary, url, notion_url)
    _post_to_webhook(webhook, card)
    logger.info("Teams alert sent for %s (score %d)", competitor, score)
    return True


def send_digest_alert(items: list, title: str, subtitle: str = "") -> bool:
    """
    Post one card covering several alert-worthy changes, grouped by competitor.
    Returns True if the message was sent, False if Teams isn't configured or
    there is nothing to send.
    """
    if not items:
        return False

    webhook = _get_webhook()
    if not webhook:
        _warn_unconfigured(f"digest of {len(items)} change(s)")
        return False

    card = _build_digest_card(items, title, subtitle)
    _post_to_webhook(webhook, card)
    logger.info("Teams digest sent — %d change(s): %s", len(items), title)
    return True
