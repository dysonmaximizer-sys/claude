"""
Sync the Notion "Competitor" select options with the COMPETITORS registry.

Run from the competitive_intel/ directory:
    python3 -m scripts.sync_notion_competitor_options            # report only
    python3 -m scripts.sync_notion_competitor_options --apply    # add missing options

Why this exists: whether the Notion API auto-creates a select option when a page
is written with an unknown option name is not something to rely on for a
pipeline that logs unattended — a rejected write would drop a detected change.
This makes the schema explicit and verifiable instead.

Additive only: it never renames, recolours or deletes an existing option, so it
is safe to re-run.
"""

import argparse
import json
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import COMPETITORS  # noqa: E402
from integrations.notion_client import _CHANGES_DB, _HEADERS, _BASE  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Notion Competitor select options.")
    parser.add_argument("--apply", action="store_true", help="Write the missing options")
    args = parser.parse_args()

    r = requests.get(f"{_BASE}/databases/{_CHANGES_DB}", headers=_HEADERS, timeout=30)
    if r.status_code >= 400:
        print(f"Could not read the database schema: {r.status_code} {r.text[:400]}")
        return 1

    prop = r.json()["properties"]["Competitor"]
    existing = [o["name"] for o in prop["select"]["options"]]
    wanted = list(COMPETITORS.keys())
    missing = [name for name in wanted if name not in existing]

    print(f"Competitor select options in Notion ({len(existing)}): {', '.join(existing)}")
    print(f"Competitors in config.py    ({len(wanted)}): {', '.join(wanted)}")
    if not missing:
        print("\nNothing missing — the schema already covers every competitor.")
        return 0

    print(f"\nMissing from Notion ({len(missing)}): {', '.join(missing)}")
    if not args.apply:
        print("Re-run with --apply to add them.")
        return 1

    body = {
        "properties": {
            "Competitor": {
                "select": {
                    "options": [{"name": n} for n in existing] + [{"name": n} for n in missing]
                }
            }
        }
    }
    r = requests.patch(
        f"{_BASE}/databases/{_CHANGES_DB}", headers=_HEADERS, json=body, timeout=30
    )
    if r.status_code >= 400:
        print(f"\nPATCH failed: {r.status_code}\n{r.text[:800]}")
        print("\nAdd these options manually in Notion instead: " + ", ".join(missing))
        return 1

    now = [o["name"] for o in r.json()["properties"]["Competitor"]["select"]["options"]]
    print(f"\nAdded {len(missing)} option(s). Notion now has {len(now)}: {', '.join(now)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
