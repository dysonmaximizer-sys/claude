"""
Smoke test: send a sample competitive alert to Teams to verify the webhook
and Adaptive Card pipeline end-to-end.

Run from the competitive_intel/ directory:
    python3 -m scripts.test_teams_alert

Expected outcome:
  - Terminal prints "Teams alert sent for Cloven (score 9)"
  - An Adaptive Card with a red header appears in the Competitive Intel
    Teams chat within ~5 seconds, showing competitor, tier, category,
    significance, summary, and an "Open Source" button.

If you see "Teams not configured" in the log, TEAMS_GENERAL_WEBHOOK isn't
set in .env (it is the only webhook now — per-competitor routing was removed
on 2026-08-18). If the call succeeds but no card lands in Teams, check the
flow's run history in Power Automate for the actual error.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# Configure logging before importing the client so its log lines appear
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Importing after dotenv load so the client sees env vars
sys.path.insert(0, str(Path(__file__).parent.parent))
from integrations.teams_client import send_competitive_alert  # noqa: E402


def main() -> int:
    ok = send_competitive_alert(
        competitor="Cloven",
        tier="Tier 1",
        category="Pricing",
        score=9,
        summary=(
            "Sample alert from smoke test. Cloven added a new enterprise "
            "pricing tier with workflow automation bundled in, undercutting "
            "our mid-market positioning. Source: Cloven pricing page."
        ),
        url="https://cloven.io/pricing",
        notion_url=(
            "https://www.notion.so/Competitive-Intelligence-Hub-"
            "34474af315fe809883bce99ab29a31ff"
        ),
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
