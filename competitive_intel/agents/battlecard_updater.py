"""
Battlecard updater — keeps Notion battlecard pages current after high-score changes.

Battlecard structure (mirrors the Equisoft template in resources/):
  - Overview: competitor summary paragraph
  - Feature Comparison: table of Feature | Them | Us
  - Why We Win: bullet points
  - Recent Intel: timestamped log of high-score changes

When a change scores above the threshold, this agent:
  1. Retrieves the competitor's battlecard Notion page
  2. Appends a timestamped "Recent Intel" entry
  3. Optionally updates the Overview if the change is score 8+
"""

import logging
from datetime import datetime, timezone

import anthropic
from notion_client import Client

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, NOTION_TOKEN
from integrations.notion_client import get_battlecard_page_id, mark_battlecard_updated

logger = logging.getLogger(__name__)
notion = Client(auth=NOTION_TOKEN)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

OVERVIEW_UPDATE_SYSTEM = """You are a competitive intelligence analyst updating a sales battlecard \
for Maximizer, a B2B SaaS CRM for financial services.

You will be given the current battlecard overview for a competitor and a new high-significance \
competitive change. Write an updated one-paragraph overview (3–4 sentences) that:
- Accurately reflects what we know about this competitor
- Incorporates the new intelligence naturally
- Remains factual and objective (this is internal intel, not marketing copy)
- Stays under 80 words

Return ONLY the updated overview paragraph. No preamble."""


def update_battlecard(
    competitor_name: str,
    tier: str,
    category: str,
    score: int,
    summary: str,
    url: str,
    change_page_id: str,
) -> bool:
    """
    Update the competitor's battlecard in Notion.
    Returns True if updated, False if no battlecard page found.
    """
    battlecard_page_id = get_battlecard_page_id(competitor_name)
    if not battlecard_page_id:
        logger.warning("No battlecard page found for %s — skipping update", competitor_name)
        return False

    # Always append to the Recent Intel section
    _append_intel_entry(battlecard_page_id, competitor_name, category, score, summary, url)

    # For very high scores, also refresh the overview paragraph
    if score >= 8:
        _refresh_overview(battlecard_page_id, competitor_name, summary, score)

    mark_battlecard_updated(change_page_id)
    logger.info("Battlecard updated for %s (score %d)", competitor_name, score)
    return True


def _append_intel_entry(
    page_id: str,
    competitor_name: str,
    category: str,
    score: int,
    summary: str,
    url: str,
) -> None:
    """Append a timestamped intel entry block to the battlecard page."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    score_label = f"{'🔴' if score >= 8 else '🟡'} {score}/10"

    blocks = [
        # Divider before each entry
        {"object": "block", "type": "divider", "divider": {}},
        # Heading: date + competitor + category
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"{date_str} — {category} Update ({score_label})"}}
                ]
            },
        },
        # Summary text
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": summary}}]
            },
        },
        # Source URL
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "Source: "}},
                    {
                        "type": "text",
                        "text": {"content": url, "link": {"url": url}},
                        "annotations": {"color": "blue"},
                    },
                ]
            },
        },
    ]

    notion.blocks.children.append(block_id=page_id, children=blocks)


def _refresh_overview(
    page_id: str,
    competitor_name: str,
    new_intel: str,
    score: int,
) -> None:
    """
    For score ≥ 8 changes, use the AI to update the overview paragraph
    at the top of the battlecard.
    """
    try:
        # Retrieve existing page content to find the current overview
        blocks = notion.blocks.children.list(block_id=page_id)
        current_overview = _extract_overview(blocks.get("results", []))

        if not current_overview:
            return  # No overview block to update

        user_content = f"""Current overview for {competitor_name}:
{current_overview}

New high-significance change (score {score}/10):
{new_intel}

Write the updated overview."""

        message = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            system=[
                {
                    "type": "text",
                    "text": OVERVIEW_UPDATE_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        updated_overview = message.content[0].text.strip()

        # Find and update the overview block
        _update_overview_block(blocks.get("results", []), updated_overview)

    except Exception as e:
        logger.warning("Could not refresh overview for %s: %s", competitor_name, e)


def _extract_overview(blocks: list) -> str:
    """Pull text from the first paragraph block on the page (assumed to be the overview)."""
    for block in blocks:
        if block.get("type") == "paragraph":
            rich_text = block["paragraph"].get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text)
            if text.strip():
                return text
    return ""


def _update_overview_block(blocks: list, new_text: str) -> None:
    """Update the first paragraph block with new overview text."""
    for block in blocks:
        if block.get("type") == "paragraph":
            rich_text = block["paragraph"].get("rich_text", [])
            if "".join(t.get("plain_text", "") for t in rich_text).strip():
                notion.blocks.update(
                    block_id=block["id"],
                    paragraph={
                        "rich_text": [{"type": "text", "text": {"content": new_text}}]
                    },
                )
                return
