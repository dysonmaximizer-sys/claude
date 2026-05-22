"""
Smoke test: send a sample monthly newsletter announcement card to Teams to
verify the newsletter Adaptive Card path before the real run on 2026-06-01.

Run from the competitive_intel/ directory:
    python3 -m scripts.test_newsletter_announcement

Expected outcome:
  - Terminal prints "Newsletter announcement sent to Teams".
  - An Adaptive Card with an accent-tinted header appears in the
    Competitive Intel Teams chat within ~5 seconds, showing the subject,
    a preview snippet, and a "Read Full Newsletter" button.

If the call succeeds but no card lands in Teams, check the flow's run
history in Power Automate for the actual error (look for
InvalidBotAdaptiveCard, which means the JSON shape was rejected).
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

sys.path.insert(0, str(Path(__file__).parent.parent))
from integrations.teams_client import send_newsletter_announcement  # noqa: E402


def main() -> int:
    ok = send_newsletter_announcement(
        subject="Competitive Intelligence Brief: April 2026 (smoke test)",
        body_preview=(
            "Three Tier 1 competitors made significant moves last month. "
            "Cloven launched bundled workflow automation in their enterprise "
            "tier, putting pricing pressure on our mid-market positioning. "
            "Equisoft refreshed their advisor onboarding flow. HubSpot rolled "
            "out a new AI feature for sales prospecting. Full breakdown and "
            "recommended responses inside."
        ),
        notion_url=(
            "https://www.notion.so/Competitive-Intelligence-Hub-"
            "34474af315fe809883bce99ab29a31ff"
        ),
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
