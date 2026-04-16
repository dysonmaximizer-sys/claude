"""
Daily poll job — runs every day to collect new competitive changes from Visualping
and log them to the Notion Changes database.

Schedule: daily at 06:00 UTC (configured in GitHub Actions / scheduler.py)
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run() -> dict:
    """
    Execute the daily Visualping poll.

    Returns a summary dict: {"new_changes": int, "errors": int}
    """
    from integrations.visualping_client import get_recent_changes
    from integrations.notion_client import log_change

    logger.info("=== Daily poll started ===")

    try:
        changes = get_recent_changes(lookback_hours=25)
    except Exception as e:
        logger.error("Failed to fetch changes from Visualping: %s", e)
        return {"new_changes": 0, "errors": 1}

    logged = 0
    errors = 0

    for change in changes:
        try:
            log_change(
                competitor_name=change["competitor_name"],
                tier=change["tier"],
                url=change["url"],
                raw_change=change["raw_change"],
                category=change["category"],
                source_type=change["source_type"],
            )
            logged += 1
            logger.info(
                "Logged: %s — %s (%s)",
                change["competitor_name"],
                change["category"],
                change["url"],
            )
        except Exception as e:
            logger.error(
                "Failed to log change for %s: %s",
                change.get("competitor_name", "unknown"),
                e,
            )
            errors += 1

    logger.info(
        "=== Daily poll complete: %d changes logged, %d errors ===",
        logged,
        errors,
    )
    return {"new_changes": logged, "errors": errors}


if __name__ == "__main__":
    result = run()
    sys.exit(0 if result["errors"] == 0 else 1)
