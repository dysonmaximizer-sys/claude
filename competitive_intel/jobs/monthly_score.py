"""
Monthly scoring job — scores all unscored changes in Notion, then triggers
alerts and battlecard updates for high-score changes.

Schedule: 1st of each month at 08:00 UTC

Pipeline per change:
  1. Score it (1–10) via scoring_agent
  2. If score > threshold: generate AI summary via summariser_agent
  3. If score > threshold: post Teams alert via teams_client
  4. If score > threshold: update competitor battlecard via battlecard_updater
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
    Score all unscored changes, then trigger downstream actions for high scores.

    Returns a summary dict:
      {"scored": int, "alerted": int, "battlecards_updated": int, "errors": int}
    """
    from integrations.notion_client import (
        get_unscored_changes,
        update_change_score,
        update_change_summary,
        extract_change_fields,
    )
    from agents.scoring_agent import score_change
    from agents.summariser_agent import summarise_change
    from agents.battlecard_updater import update_battlecard
    from integrations.teams_client import send_competitive_alert
    from integrations.notion_client import mark_alert_sent
    from config import ALERT_SCORE_THRESHOLD, COMPETITORS

    logger.info("=== Monthly scoring job started ===")

    raw_pages = get_unscored_changes()
    logger.info("Found %d unscored changes to process", len(raw_pages))

    scored = 0
    alerted = 0
    battlecards_updated = 0
    errors = 0

    for page in raw_pages:
        change = extract_change_fields(page)
        competitor = change["competitor"]
        page_id = change["page_id"]

        logger.info("Scoring: %s | %s | %s", competitor, change["category"], change["url"])

        # ── Step 1: Score ──────────────────────────────────────────────────
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

        # ── Step 2: Summarise ──────────────────────────────────────────────
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
            summary = reasoning  # Fall back to scoring reasoning
            errors += 1

        # ── Step 3: Teams alert ────────────────────────────────────────────
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

        # ── Step 4: Update battlecard ──────────────────────────────────────
        try:
            updated = update_battlecard(
                competitor_name=competitor,
                tier=change["tier"],
                category=refined_category,
                score=score,
                summary=summary,
                url=change["url"],
                change_page_id=page_id,
            )
            if updated:
                battlecards_updated += 1
        except Exception as e:
            logger.error("  → Battlecard update failed for %s: %s", competitor, e)
            errors += 1

    logger.info(
        "=== Monthly scoring complete: %d scored, %d alerted, %d battlecards updated, %d errors ===",
        scored, alerted, battlecards_updated, errors,
    )
    return {
        "scored": scored,
        "alerted": alerted,
        "battlecards_updated": battlecards_updated,
        "errors": errors,
    }


if __name__ == "__main__":
    result = run()
    sys.exit(0 if result["errors"] == 0 else 1)
