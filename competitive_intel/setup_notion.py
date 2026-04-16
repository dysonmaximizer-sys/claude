"""
One-time Notion setup script.

Run this ONCE after:
  1. Creating a "Competitive Intelligence" page in Notion
  2. Sharing that page with your Notion integration
     (Page → Share → Search for your integration by name → Invite)
  3. Copying the page ID from the URL into .env as NOTION_PARENT_PAGE_ID

Usage:
  cd competitive_intel
  pip install -r requirements.txt
  python setup_notion.py

The script will:
  - Create the Competitors database
  - Create the Changes database
  - Create a Battlecard page for each competitor
  - Print the DB IDs to add to your .env file
"""

import sys
import logging
import requests as _requests
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

import os

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
PARENT_PAGE_ID = os.environ["NOTION_PARENT_PAGE_ID"]

notion = Client(auth=NOTION_TOKEN)

# notion-client 3.x has a bug that silently drops properties on databases.create.
# Use raw HTTP for database creation to work around it.
_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def _create_database(payload: dict) -> dict:
    """Create a Notion database via raw HTTP (bypasses notion-client 3.x property bug)."""
    r = _requests.post("https://api.notion.com/v1/databases", headers=_HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

# All competitors with their tiers (from config)
COMPETITORS = {
    "Equisoft":   "Tier 1",
    "Cloven":     "Tier 1",
    "HubSpot":    "Tier 1",
    "Laylah":     "Tier 2",
    "Salesforce": "Tier 2",
    "Wealthbox":  "Tier 2",
    "Monday":     "Tier 2",
    "Zoho":       "Tier 2",
    "Onevest":    "Ankle Biter",
    "Pipedrive":  "Ankle Biter",
    "Advora":     "Ankle Biter",
}


def create_competitors_db() -> str:
    """Create the Competitors tracking database."""
    logger.info("Creating Competitors database...")
    response = _create_database({
        "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
        "title": [{"type": "text", "text": {"content": "Competitors"}}],
        "properties": {
            "Name": {"title": {}},
            "Tier": {
                "select": {
                    "options": [
                        {"name": "Tier 1", "color": "red"},
                        {"name": "Tier 2", "color": "yellow"},
                        {"name": "Ankle Biter", "color": "gray"},
                    ]
                }
            },
            "Notes": {"rich_text": {}},
            "Last Updated": {"date": {}},
        },
    })
    db_id = response["id"]
    logger.info("  ✓ Competitors DB created: %s", db_id)
    return db_id


def create_changes_db() -> str:
    """Create the Changes (source of truth) database."""
    logger.info("Creating Changes database...")
    response = _create_database({
        "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
        "title": [{"type": "text", "text": {"content": "Competitive Changes"}}],
        "properties": {
            "Name": {"title": {}},
            "Competitor": {
                "select": {
                    "options": [{"name": name, "color": "default"} for name in COMPETITORS]
                }
            },
            "Tier": {
                "select": {
                    "options": [
                        {"name": "Tier 1", "color": "red"},
                        {"name": "Tier 2", "color": "yellow"},
                        {"name": "Ankle Biter", "color": "gray"},
                    ]
                }
            },
            "Source Type": {
                "select": {
                    "options": [
                        {"name": "Web", "color": "blue"},
                        {"name": "CRM", "color": "green"},       # Phase 2
                        {"name": "Staff Intel", "color": "purple"},  # Phase 2
                        {"name": "Fathom", "color": "orange"},   # Phase 2
                    ]
                }
            },
            "Category": {
                "select": {
                    "options": [
                        {"name": "Pricing", "color": "red"},
                        {"name": "Feature", "color": "blue"},
                        {"name": "Messaging", "color": "green"},
                        {"name": "Integration", "color": "yellow"},
                        {"name": "Other", "color": "gray"},
                    ]
                }
            },
            "URL": {"url": {}},
            "Date Detected": {"date": {}},
            "Raw Change": {"rich_text": {}},
            "AI Summary": {"rich_text": {}},
            "Significance Score": {"number": {"format": "number"}},
            "Score Reasoning": {"rich_text": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "Unscored", "color": "gray"},
                        {"name": "Scored", "color": "yellow"},
                        {"name": "Distributed", "color": "green"},
                    ]
                }
            },
            "Teams Alert Sent": {"checkbox": {}},
            "Battlecard Updated": {"checkbox": {}},
        },
    })
    db_id = response["id"]
    logger.info("  ✓ Changes DB created: %s", db_id)
    return db_id


def create_battlecard_page(competitor_name: str, tier: str) -> str:
    """Create a structured battlecard Notion page for a competitor."""
    response = notion.pages.create(
        parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
        properties={
            "title": [{"type": "text", "text": {"content": f"Battlecard: {competitor_name}"}}]
        },
        children=[
            # Header
            {
                "object": "block", "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": f"{competitor_name} Battlecard"}}]},
            },
            {
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [
                    {"type": "text", "text": {"content": f"Tier: {tier} | Last Updated: —"}}
                ]},
            },
            # Overview
            {"object": "block", "type": "heading_2",
             "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Overview"}}]}},
            {"object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"[Add overview of {competitor_name} here]"}}]}},
            # Key Differentiators
            {"object": "block", "type": "heading_2",
             "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Key Differentiators & Features"}}]}},
            {"object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Feature | Them | Us"}}]}},
            {"object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"type": "text", "text": {"content": "[Add feature comparison rows]"}}]}},
            # Why We Win
            {"object": "block", "type": "heading_2",
             "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Why We Win"}}]}},
            {"object": "block", "type": "bulleted_list_item",
             "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "[Add win reasons]"}}]}},
            # Talk Tracks
            {"object": "block", "type": "heading_2",
             "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Talk Tracks"}}]}},
            {"object": "block", "type": "bulleted_list_item",
             "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "[Add talk track bullets for Sales]"}}]}},
            # Recent Intel (auto-populated by battlecard_updater.py)
            {"object": "block", "type": "heading_2",
             "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Recent Intel"}}]}},
            {"object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"type": "text", "text": {"content": "High-score changes are appended here automatically."}}]}},
        ],
    )
    return response["id"]


def populate_competitors_db(competitors_db_id: str) -> dict:
    """Add a row for each competitor and link their battlecard page."""
    from datetime import datetime, timezone

    logger.info("Creating battlecard pages and populating Competitors database...")
    page_ids = {}

    for name, tier in COMPETITORS.items():
        # Create battlecard page
        battlecard_id = create_battlecard_page(name, tier)

        # Add to Competitors DB
        notion.pages.create(
            parent={"database_id": competitors_db_id},
            properties={
                "Name": {"title": [{"text": {"content": name}}]},
                "Tier": {"select": {"name": tier}},
                "Last Updated": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
            },
        )
        page_ids[name] = battlecard_id
        logger.info("  ✓ %s (%s) — battlecard: %s", name, tier, battlecard_id)

    return page_ids


def resolve_parent_page_id(raw_id: str) -> str:
    """
    The Notion API requires databases to be parented by a PAGE, not a database.
    If the provided ID belongs to a database, create a plain page inside it
    and return that page's ID instead.
    """
    try:
        notion.databases.retrieve(raw_id)
        # It's a database — create a container page inside it
        logger.info(
            "  Provided ID is a database. Creating an 'Intel Hub' page inside it..."
        )
        response = notion.pages.create(
            parent={"database_id": raw_id},
            properties={
                "title": [{"type": "text", "text": {"content": "Intel Hub"}}]
            },
        )
        page_id = response["id"]
        logger.info("  ✓ Container page created: %s", page_id)
        return page_id
    except Exception:
        # Not a database (or already a page) — use as-is
        return raw_id


def main():
    global PARENT_PAGE_ID
    logger.info("\n=== Notion Setup ===\n")

    if not PARENT_PAGE_ID or PARENT_PAGE_ID == "REPLACE_WITH_NOTION_PAGE_ID":
        logger.error(
            "ERROR: Set NOTION_PARENT_PAGE_ID in .env before running setup.\n"
            "  1. Create a page called 'Competitive Intelligence' in Notion\n"
            "  2. Share it with your integration (Page → Share → invite integration)\n"
            "  3. Copy the page ID from the URL (the 32-char hex string)\n"
            "  4. Paste it into .env as NOTION_PARENT_PAGE_ID"
        )
        sys.exit(1)

    # Resolve the parent: if it's a database URL, create a container page first
    PARENT_PAGE_ID = resolve_parent_page_id(PARENT_PAGE_ID)

    competitors_db_id = create_competitors_db()
    changes_db_id = create_changes_db()
    populate_competitors_db(competitors_db_id)

    logger.info("\n=== Setup complete! ===\n")
    logger.info("Add these to your .env file:\n")
    logger.info("NOTION_COMPETITORS_DB_ID=%s", competitors_db_id)
    logger.info("NOTION_CHANGES_DB_ID=%s", changes_db_id)
    logger.info("\nThen add these as GitHub Actions secrets (Settings → Secrets → Actions):")
    logger.info("  ANTHROPIC_API_KEY, NOTION_TOKEN, VISUALPING_API_KEY,")
    logger.info("  NOTION_PARENT_PAGE_ID, NOTION_COMPETITORS_DB_ID, NOTION_CHANGES_DB_ID")


if __name__ == "__main__":
    main()
