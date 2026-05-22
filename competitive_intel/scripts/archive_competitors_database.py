"""
One-shot cleanup: archive the defunct 'Competitors' database from the
Competitive Intelligence Hub in Notion.

This database is leftover infrastructure from when battlecards were in
scope. No code reads or writes it anymore. Archiving it tidies the Hub.

Run once from the competitive_intel/ directory:
    python3 -m scripts.archive_competitors_database

Safe to re-run. No-ops if the database is already archived or missing.
The archived database goes to Notion trash, recoverable for 30 days.
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

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

BASE = "https://api.notion.com/v1"

# The defunct Competitors database under the Competitive Intelligence Hub
COMPETITORS_DB_ID = "34474af3-15fe-8102-adc0-f4669b1e137d"


def main() -> int:
    # 1. Confirm the database still exists and is not already archived
    r = requests.get(f"{BASE}/databases/{COMPETITORS_DB_ID}", headers=HEADERS, timeout=30)
    if r.status_code == 404:
        logger.info("Competitors database is already gone or inaccessible. Nothing to do.")
        return 0
    if not r.ok:
        logger.error("Could not read Competitors database: %d %s",
                     r.status_code, r.text[:300])
        return 1

    if r.json().get("archived"):
        logger.info("Competitors database is already archived. Nothing to do.")
        return 0

    # 2. Archive it (Notion archives a DB when PATCHed with archived=true)
    logger.info("Archiving Competitors database (%s)", COMPETITORS_DB_ID)
    r = requests.patch(
        f"{BASE}/databases/{COMPETITORS_DB_ID}",
        headers=HEADERS,
        json={"archived": True},
        timeout=30,
    )
    if r.ok:
        logger.info("Competitors database archived. Goes to Notion trash.")
        return 0

    logger.error("Notion rejected the archive request: %d %s",
                 r.status_code, r.text[:300])
    return 1


if __name__ == "__main__":
    sys.exit(main())
