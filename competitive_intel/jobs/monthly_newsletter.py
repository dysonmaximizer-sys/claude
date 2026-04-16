"""
Monthly newsletter job — generates and distributes the Strategic Synthesis.

Schedule: 1st of each month at 09:00 UTC (runs 1 hour after monthly_score.py)

Pipeline:
  1. Fetch all scored changes from the previous month (score ≥ 1)
  2. Generate Strategic Synthesis newsletter via newsletter_agent
  3. Save to output/
  4. Post announcement to Teams general channel
  5. Email to NEWSLETTER_RECIPIENTS
"""

import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _previous_month(year: int, month: int) -> tuple[int, int]:
    """Return (year, month) for the month before the given one."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def run(target_year: int = None, target_month: int = None) -> dict:
    """
    Generate and distribute the monthly newsletter.

    By default covers the previous calendar month.
    Pass target_year/target_month to generate for a specific month (useful for testing).

    Returns: {"newsletter_generated": bool, "emailed": bool, "teams_posted": bool}
    """
    from integrations.notion_client import get_monthly_changes, extract_change_fields
    from agents.newsletter_agent import generate_newsletter, save_newsletter, email_newsletter
    from integrations.teams_client import send_newsletter_announcement

    now = datetime.now(timezone.utc)
    if target_year and target_month:
        year, month = target_year, target_month
    else:
        year, month = _previous_month(now.year, now.month)

    month_name = datetime(year, month, 1).strftime("%B %Y")
    logger.info("=== Monthly newsletter job started for %s ===", month_name)

    # ── Fetch changes ──────────────────────────────────────────────────────────
    raw_pages = get_monthly_changes(year=year, month=month, min_score=1)
    changes = [extract_change_fields(p) for p in raw_pages]
    logger.info("Found %d scored changes for %s", len(changes), month_name)

    # ── Generate newsletter ────────────────────────────────────────────────────
    try:
        newsletter_text = generate_newsletter(changes, month=month, year=year)
        file_path = save_newsletter(newsletter_text, month=month, year=year)
        logger.info("Newsletter saved: %s", file_path)
        generated = True
    except Exception as e:
        logger.error("Newsletter generation failed: %s", e)
        return {"newsletter_generated": False, "emailed": False, "teams_posted": False}

    # ── Teams announcement ─────────────────────────────────────────────────────
    subject = f"Competitive Intelligence: Monthly Strategic Synthesis — {month_name}"
    preview = newsletter_text[:400]  # First ~400 chars as Teams preview

    try:
        teams_posted = send_newsletter_announcement(
            subject=subject,
            body_preview=preview,
        )
    except Exception as e:
        logger.error("Teams announcement failed: %s", e)
        teams_posted = False

    # ── Email ──────────────────────────────────────────────────────────────────
    try:
        emailed = email_newsletter(newsletter_text, month=month, year=year)
    except Exception as e:
        logger.error("Email delivery failed: %s", e)
        emailed = False

    logger.info(
        "=== Newsletter job complete: generated=%s, emailed=%s, teams_posted=%s ===",
        generated, emailed, teams_posted,
    )
    return {"newsletter_generated": generated, "emailed": emailed, "teams_posted": teams_posted}


if __name__ == "__main__":
    # Support optional CLI args: python monthly_newsletter.py 2025 3
    args = sys.argv[1:]
    kwargs = {}
    if len(args) >= 2:
        kwargs["target_year"] = int(args[0])
        kwargs["target_month"] = int(args[1])

    result = run(**kwargs)
    sys.exit(0 if result["newsletter_generated"] else 1)
