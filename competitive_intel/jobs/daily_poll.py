"""
Daily poll job — collects new competitive changes from Visualping, logs them
to Notion, and immediately scores each one.  High-score changes (>= threshold)
also get an AI summary, a Teams alert, and a battlecard update.

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
    Execute the daily Visualping poll and score every new change inline.

    Returns a summary dict:
      {"new_changes": int, "scored": int, "alerted": int, "errors": int}
    """
    from integrations.visualping_client import get_recent_changes
    from integrations.notion_client import (
        log_change,
        change_already_logged,
        update_change_score,
        update_change_summary,
        mark_alert_sent,
        extract_change_fields,
    )
    from agents.scoring_agent import score_change
    from agents.summariser_agent import summarise_change
    from agents.battlecard_updater import update_battlecard
    from integrations.teams_client import send_competitive_alert
    from config import ALERT_SCORE_THRESHOLD, COMPETITORS

    logger.info("=== Daily poll started ===")

    try:
        changes = get_recent_changes(lookback_hours=25)
    except Exception as e:
        logger.error("Failed to fetch changes from Visualping: %s", e)
        return {"new_changes": 0, "scored": 0, "alerted": 0, "errors": 1}

    logged = 0
    scored = 0
    alerted = 0
    errors = 0

    for change in changes:
        competitor = change["competitor_name"]

        # ── Step 1: Deduplicate and log ────────────────────────────────────
        try:
            if change_already_logged(competitor, change["url"], change.get("detected_at", "")):
                logger.info("Skipping duplicate: %s — %s", competitor, change["url"])
                continue

            page_id = log_change(
                competitor_name=competitor,
                tier=change["tier"],
                url=change["url"],
                raw_change=change["raw_change"],
                category=change["category"],
                source_type=change["source_type"],
                detected_at=change.get("detected_at", ""),
            )
            logged += 1
            logger.info("Logged: %s — %s (%s)", competitor, change["category"], change["url"])
        except Exception as e:
            logger.error("Failed to log change for %s: %s", competitor, e)
            errors += 1
            continue

        # ── Step 2: Score immediately ──────────────────────────────────────
        try:
            score, reasoning, refined_category = score_change(
                competitor_name=competitor,
                tier=change["tier"],
                category=change["category"],
                url=change["url"],
                raw_change=change["raw_change"],
            )
            update_change_score(page_id, score, reasoning)
            scored += 1
            logger.info("  → Score: %d/10 — %s", score, reasoning)
        except Exception as e:
            logger.error("  → Scoring failed for %s: %s", competitor, e)
            errors += 1
            continue

        if score <= ALERT_SCORE_THRESHOLD:
            logger.info("  → Score below threshold (%d) — no further action", ALERT_SCORE_THRESHOLD)
            continue

        # ── Step 3: Summarise ──────────────────────────────────────────────
        try:
            summary = summarise_change(
                competitor_name=competitor,
                tier=change["tier"],
                category=refined_category,
                score=score,
                score_reasoning=reasoning,
                raw_change=change["raw_change"],
                url=change["url"],
            )
            update_change_summary(page_id, summary)
            logger.info("  → Summary written")
        except Exception as e:
            logger.error("  → Summarisation failed for %s: %s", competitor, e)
            summary = reasoning
            errors += 1

        # ── Step 4: Teams alert ────────────────────────────────────────────
        try:
            competitor_slug = COMPETITORS.get(competitor, {}).get("slug", competitor.lower())
            notion_url = f"https://www.notion.so/{page_id.replace('-', '')}"
            sent = send_competitive_alert(
                competitor=competitor,
                tier=change["tier"],
                category=refined_category,
                score=score,
                summary=summary,
                url=change["url"],
                competitor_slug=competitor_slug,
                notion_url=notion_url,
            )
            if sent:
                mark_alert_sent(page_id)
                alerted += 1
        except Exception as e:
            logger.error("  → Teams alert failed for %s: %s", competitor, e)
            errors += 1

        # ── Step 5: Update battlecard ──────────────────────────────────────
        try:
            update_battlecard(
                competitor_name=competitor,
                tier=change["tier"],
                category=refined_category,
                score=score,
                summary=summary,
                url=change["url"],
                change_page_id=page_id,
            )
        except Exception as e:
            logger.error("  → Battlecard update failed for %s: %s", competitor, e)
            errors += 1

    logger.info(
        "=== Daily poll complete: %d logged, %d scored, %d alerted, %d errors ===",
        logged, scored, alerted, errors,
    )
    return {"new_changes": logged, "scored": scored, "alerted": alerted, "errors": errors}


if __name__ == "__main__":
    result = run()
    sys.exit(0 if result["errors"] == 0 else 1)
