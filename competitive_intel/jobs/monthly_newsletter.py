"""
Monthly newsletter job — generates and distributes the Strategic Synthesis.

Schedule: 1st of each month at 09:00 UTC (draft path only)

Pipeline:
  1. Fetch all scored changes from the previous month (score ≥ 1)
  2. Generate Strategic Synthesis newsletter via newsletter_agent
  3. Save to output/
  4. Send via Resend, branching on --mode:
       --mode draft     → single-recipient review email to DRAFT_REVIEWER
       --mode broadcast → broadcast to the RESEND_AUDIENCE_ID audience
                          (manual workflow, after the draft is approved)

The Teams Adaptive Card announcement has been removed from this monthly
path. Daily Teams alerts in jobs/daily_poll.py are unaffected.
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

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


def run(mode: str, year: int, month: int) -> dict:
    """
    Generate and distribute the monthly newsletter.

    mode:
      "draft"     → send to DRAFT_REVIEWER via Resend /emails for review.
      "broadcast" → send to RESEND_AUDIENCE_ID via Resend /broadcasts.

    Returns: {"newsletter_generated": bool, "mode": str, "sent": bool}
    """
    from integrations.notion_client import get_monthly_changes, extract_change_fields
    from agents.newsletter_agent import (
        generate_newsletter,
        save_newsletter,
        send_draft_email,
        send_broadcast,
        _render_html,
    )
    from config import DRAFT_REVIEWER, RESEND_AUDIENCE_ID

    month_name = datetime(year, month, 1).strftime("%B %Y")
    logger.info("=== Monthly newsletter job started for %s (mode=%s) ===", month_name, mode)

    # ── Fetch changes ──────────────────────────────────────────────────────────
    raw_pages = get_monthly_changes(year=year, month=month, min_score=1)
    changes = [extract_change_fields(p) for p in raw_pages]
    logger.info("Found %d scored changes for %s", len(changes), month_name)

    # ── Generate newsletter ────────────────────────────────────────────────────
    try:
        newsletter_text = generate_newsletter(changes, month=month, year=year)
        file_path = save_newsletter(newsletter_text, month=month, year=year)
        logger.info("Newsletter saved: %s", file_path)
    except Exception as e:
        logger.error("Newsletter generation failed: %s", e)
        return {"newsletter_generated": False, "mode": mode, "sent": False}

    html = _render_html(newsletter_text, month_name)

    # ── Distribute ─────────────────────────────────────────────────────────────
    if mode == "draft":
        subject = f"[DRAFT — review and approve] Competitive Intel Newsletter {year}-{month:02d}"
        ok = send_draft_email(html, subject, recipient=DRAFT_REVIEWER)
        logger.info("Draft sent to %s: %s", DRAFT_REVIEWER, ok)
    elif mode == "broadcast":
        if not RESEND_AUDIENCE_ID:
            logger.error("RESEND_AUDIENCE_ID not set — cannot broadcast.")
            ok = False
        else:
            subject = f"Competitive Intel Newsletter {year}-{month:02d}"
            ok = send_broadcast(
                html,
                subject,
                audience_id=RESEND_AUDIENCE_ID,
                internal_name=f"CI Newsletter {year}-{month:02d}",
            )
        logger.info("Broadcast result: %s", ok)
    else:
        logger.error("Unknown mode: %s", mode)
        ok = False

    logger.info(
        "=== Newsletter job complete: generated=True, mode=%s, sent=%s ===",
        mode, ok,
    )
    return {"newsletter_generated": True, "mode": mode, "sent": ok}


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    """Parse CLI args. --year/--month default to the previous calendar month."""
    parser = argparse.ArgumentParser(
        description="Generate and distribute the monthly CI newsletter."
    )
    parser.add_argument(
        "--mode",
        choices=["draft", "broadcast"],
        required=True,
        help="draft = review email to DRAFT_REVIEWER; broadcast = send to Resend audience.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Target year. Defaults to the previous month's year.",
    )
    parser.add_argument(
        "--month",
        type=int,
        default=None,
        help="Target month 1-12. Defaults to the previous month.",
    )
    args = parser.parse_args(argv)

    if (args.year is None) ^ (args.month is None):
        parser.error("--year and --month must be provided together.")

    if args.year is None and args.month is None:
        now = datetime.now(timezone.utc)
        args.year, args.month = _previous_month(now.year, now.month)

    return args


if __name__ == "__main__":
    args = parse_args()
    result = run(mode=args.mode, year=args.year, month=args.month)
    # Deliberate change from prior behaviour: exit 1 when the send fails so
    # GitHub Actions surfaces the failure (previously exited 0 on email error).
    sys.exit(0 if result["newsletter_generated"] and result.get("sent") else 1)
