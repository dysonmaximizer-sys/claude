"""
One-shot cleanup: archive the 11 legacy 'Battlecard: <competitor>' pages from
the Competitive Intelligence Hub in Notion.

Run once after battlecards were removed from the pipeline. The pipeline never
touches these pages anymore — this just removes them from the live workspace.
They go to Notion trash, recoverable for 30 days if you change your mind.

Usage (from the competitive_intel/ directory):
    python3 -m scripts.archive_battlecard_pages

Safe to re-run — it no-ops if a page is already archived.
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

# The 11 legacy battlecard pages under the Competitive Intelligence Hub
BATTLECARD_PAGES = [
    ("Equisoft",   "34474af3-15fe-8166-b56b-c93afc08ca59"),
    ("Cloven",     "34474af3-15fe-81f2-a124-d675099fbbaa"),
    ("Salesforce", "34474af3-15fe-81f4-85ee-c7dcf61f24a6"),
    ("HubSpot",    "34474af3-15fe-8124-bc46-ca41576fe8f2"),
    ("Advora",     "34474af3-15fe-8167-ad3f-c90553ef5012"),
    ("Pipedrive",  "34474af3-15fe-81e3-9941-d1253bc13a8c"),
    ("Zoho",       "34474af3-15fe-8142-80d4-f0bde8104ef8"),
    ("Laylah",     "34474af3-15fe-819f-b239-e704b3432e96"),
    ("Wealthbox",  "34474af3-15fe-811a-a632-f5a4c15ccbf7"),
    ("Monday",     "34474af3-15fe-8138-a2cb-dc93781648c4"),
    ("Onevest",    "34474af3-15fe-810a-9eea-e43c5bb21800"),
]


def main() -> int:
    archived = 0
    skipped = 0
    failed = 0

    for name, page_id in BATTLECARD_PAGES:
        # Check current state first so we can no-op on re-runs
        r = requests.get(f"{BASE}/pages/{page_id}", headers=HEADERS, timeout=30)
        if r.status_code == 404:
            logger.info("Battlecard: %s — already deleted permanently, skipping", name)
            skipped += 1
            continue
        if not r.ok:
            logger.error("Battlecard: %s — could not read page: %d %s",
                         name, r.status_code, r.text[:200])
            failed += 1
            continue

        if r.json().get("archived"):
            logger.info("Battlecard: %s — already archived, skipping", name)
            skipped += 1
            continue

        # Archive it
        r = requests.patch(
            f"{BASE}/pages/{page_id}",
            headers=HEADERS,
            json={"archived": True},
            timeout=30,
        )
        if r.ok:
            logger.info("Battlecard: %s — archived ✓", name)
            archived += 1
        else:
            logger.error("Battlecard: %s — archive failed: %d %s",
                         name, r.status_code, r.text[:200])
            failed += 1

    print()
    print(f"Done. Archived: {archived}  |  Already gone: {skipped}  |  Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
