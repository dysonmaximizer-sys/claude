"""
One-shot cleanup: remove the legacy 'Battlecard Updated' column from the
Notion Changes database.

Run once after the battlecard pipeline was removed from the codebase. The
column is no longer written or read by any code; this script archives the
property so the schema matches the code.

Usage (from the competitive_intel/ directory):
    python3 -m scripts.drop_battlecard_column

Safe to re-run — it no-ops if the property is already gone.
"""

import logging
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
CHANGES_DB_ID = os.environ["NOTION_CHANGES_DB_ID"]
PROPERTY_NAME = "Battlecard Updated"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

BASE = "https://api.notion.com/v1"


def main() -> int:
    # 1. Confirm the property still exists
    r = requests.get(f"{BASE}/databases/{CHANGES_DB_ID}", headers=HEADERS, timeout=30)
    if r.status_code >= 400:
        logger.error("Could not read database: %d — %s", r.status_code, r.text[:500])
        return 1
    props = r.json().get("properties", {})
    if PROPERTY_NAME not in props:
        logger.info("'%s' is already gone — nothing to do.", PROPERTY_NAME)
        return 0

    logger.info("Found '%s' in Changes DB schema. Removing it...", PROPERTY_NAME)

    # 2. Remove the property (Notion deletes a property when it's set to null in an update)
    r = requests.patch(
        f"{BASE}/databases/{CHANGES_DB_ID}",
        headers=HEADERS,
        json={"properties": {PROPERTY_NAME: None}},
        timeout=30,
    )
    if r.status_code >= 400:
        logger.error("Notion rejected the update: %d — %s", r.status_code, r.text[:500])
        return 1

    logger.info("✓ '%s' removed from Changes DB.", PROPERTY_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
