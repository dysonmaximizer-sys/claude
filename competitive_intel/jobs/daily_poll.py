"""
Daily poll job — collects new competitive changes from changedetection.io, logs
them to Notion, and immediately scores each one.  High-score changes
(>= threshold) also get an AI summary and a Teams alert.

Schedule: business days at 15:00 UTC (configured in GitHub Actions /
scheduler.py), which lands at 08:00 Pacific (PDT) / 07:00 (PST). No weekend
alerts. This runs before the day's cd.io crawl, so each morning's alert covers
the prior day's detections; the 76h lookback bridges the weekend so Friday's
crawl is alerted Monday morning.

Teams alerts are deferred until every change is logged, scored, and summarised,
then grouped by underlying insight so one announcement spread across several of
a competitor's pages fires a single alert instead of one per page. Every alert
goes to the single general webhook, with the competitor as the card headline.

Order of operations, and why (all three guards were added 2026-08-18 after a
credit outage stranded 183 rows as permanently-"Unscored"):

  0. PREFLIGHT — one 1-token Anthropic call before anything is fetched or
     written. If the key can't run billed inference the job exits non-zero with
     nothing touched, instead of filling Notion with rows it cannot score.
  1. RESCUE SWEEP — score up to RESCUE_SWEEP_LIMIT rows still sitting at
     Status = Unscored from earlier failed runs. Dedupe alone can't reach these:
     once a row's detection date falls outside the 76h lookback it is never
     re-fetched, so the backlog has to be drained from the database side.
     Swept rows are scored SILENTLY (RESCUE_SWEEP_ALERTS = False): they are
     old news by then, and alerting on them buries the fresh signal.
  2. POLL — fetch, then dedupe status-aware: an existing Scored/Distributed row
     means skip, an existing Unscored row means re-score that row IN PLACE
     rather than skipping it or creating a duplicate.

Usage:
  python -m jobs.daily_poll
  python -m jobs.daily_poll --dry-run     # preflight + fetch + report, no writes
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run(dry_run: bool = False) -> dict:
    """
    Execute the daily changedetection.io poll and score every new change inline.

    Returns a summary dict:
      {"new_changes": int, "resumed": int, "scored": int, "alerted": int,
       "errors": int, "swept": int}
    """
    from integrations.anthropic_preflight import preflight_or_exit
    from integrations.changedetection_client import get_recent_changes
    from integrations.notion_client import (
        log_change,
        find_existing_change,
        update_change_score,
        update_change_summary,
        update_change_meta,
        mark_alert_sent,
    )
    from agents.scoring_agent import score_change
    from agents.summariser_agent import summarise_change
    from agents.dedup_agent import cluster_changes_by_insight
    from integrations.teams_client import redact, send_competitive_alert
    from jobs.rescore import rescore_unscored
    from config import ALERT_SCORE_THRESHOLD, RESCUE_SWEEP_LIMIT, RESCUE_SWEEP_ALERTS

    logger.info("=== Daily poll started%s ===", " (DRY RUN)" if dry_run else "")

    # ── Step 0: preflight ──────────────────────────────────────────────────────
    # Before any fetch and before any write. Exits non-zero on failure.
    preflight_or_exit("daily poll", fatal=not dry_run)

    # ── Step 1: rescue sweep of previously stranded rows ───────────────────────
    logger.info("--- Rescue sweep: re-scoring stranded Unscored rows ---")
    sweep = rescore_unscored(
        limit=RESCUE_SWEEP_LIMIT,
        alert=RESCUE_SWEEP_ALERTS,  # backlog is scored silently — see config
        digest_title="Competitive Intelligence — Backlog Catch-up",
        dry_run=dry_run,
    )
    if sweep["remaining"] and not dry_run:
        logger.warning(
            "%d row(s) still Unscored after the sweep — they drain on following "
            "runs, or in one pass via `python -m jobs.backfill_rescore`.",
            sweep["remaining"],
        )

    try:
        # 76h, not 24h: the poll runs business days only (see daily-poll.yml),
        # so Monday's run must reach back across the weekend to catch Friday's
        # crawl (~72h). Re-fetched changes already SCORED in Notion are skipped
        # by find_existing_change(), so the wide window never double-alerts.
        changes = get_recent_changes(lookback_hours=76)
    except Exception as e:
        logger.error("Failed to fetch changes from changedetection.io: %s", e)
        return {
            "new_changes": 0, "resumed": 0, "scored": sweep["scored"],
            "alerted": sweep["alerted"], "errors": sweep["errors"] + 1,
            "swept": sweep["processed"],
        }

    logged = 0
    resumed = 0
    scored = 0
    alerted = 0
    errors = 0
    pending_alerts: list[dict] = []  # alert-worthy changes, alerted after the loop

    for change in changes:
        competitor = change["competitor_name"]

        # ── Step 2: status-aware dedupe, then log or resume ────────────────
        try:
            existing = find_existing_change(
                competitor, change["url"], change.get("detected_at", "")
            )
            if existing and existing["status"] in ("Scored", "Distributed"):
                logger.info(
                    "Skipping duplicate (%s): %s — %s",
                    existing["status"], competitor, change["url"],
                )
                continue

            if existing:
                # Status is Unscored — a row stranded by an earlier failure.
                # Re-score it in place; never create a second row for it.
                page_id = existing["page_id"]
                resumed += 1
                logger.info(
                    "Resuming stranded row (Status=%s): %s — %s",
                    existing["status"] or "Unscored", competitor, change["url"],
                )
            elif dry_run:
                logger.info(
                    "[dry run] Would log new change: %s — %s", competitor, change["url"]
                )
                continue
            else:
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

        if dry_run:
            logger.info("[dry run] Would re-score existing row %s", page_id)
            continue

        # ── Step 3: Score immediately ──────────────────────────────────────
        try:
            score, reasoning, refined_category = score_change(
                competitor_name=competitor,
                tier=change["tier"],
                category=change["category"],
                url=change["url"],
                raw_change=change["raw_change"],
            )
            update_change_score(page_id, score, reasoning)
            update_change_meta(page_id, tier=change["tier"], category=refined_category)
            scored += 1
            logger.info("  → Score: %d/10 — %s", score, reasoning)
        except Exception as e:
            logger.error("  → Scoring failed for %s: %s", competitor, e)
            errors += 1
            continue

        if score <= ALERT_SCORE_THRESHOLD:
            logger.info("  → Score below threshold (%d) — no further action", ALERT_SCORE_THRESHOLD)
            continue

        # ── Step 4: Summarise ──────────────────────────────────────────────
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

        # ── Step 5: Queue for alerting (deferred until after the loop) ─────
        # Don't alert inline. Collect alert-worthy changes so we can group a
        # competitor's pages by insight first and alert once per insight.
        notion_url = f"https://www.notion.so/{page_id.replace('-', '')}"
        pending_alerts.append({
            "competitor": competitor,
            "tier": change["tier"],
            "category": refined_category,
            "score": score,
            "summary": summary,
            "url": change["url"],
            "page_id": page_id,
            "notion_url": notion_url,
            "raw_change": change["raw_change"],
        })

    # ── Step 6: De-duplicate by insight, then alert ────────────────────────
    # One competitor's announcement often lands on several monitored pages in
    # the same crawl. Group those by underlying insight and alert once per
    # insight — a single normal alert card, picked from the cluster. Suppressed
    # pages stay logged in Notion and still feed the monthly newsletter.
    by_competitor: dict[str, list[dict]] = {}
    for item in pending_alerts:
        by_competitor.setdefault(item["competitor"], []).append(item)

    for competitor, items in by_competitor.items():
        try:
            clusters = cluster_changes_by_insight(competitor, items)
        except Exception as e:
            logger.error("  → Clustering failed for %s (alerting each): %s", competitor, e)
            clusters = [[i] for i in range(len(items))]

        for cluster in clusters:
            # Representative = highest score, then longest summary, then earliest.
            rep = max(
                (items[i] for i in cluster),
                key=lambda it: (it["score"], len(it["summary"] or "")),
            )
            if len(cluster) > 1:
                logger.info(
                    "  → %s: %d pages share one insight — alerting 1, suppressing %d duplicate(s)",
                    competitor, len(cluster), len(cluster) - 1,
                )
            try:
                sent = send_competitive_alert(
                    competitor=rep["competitor"],
                    tier=rep["tier"],
                    category=rep["category"],
                    score=rep["score"],
                    summary=rep["summary"],
                    url=rep["url"],
                    notion_url=rep["notion_url"],
                )
                if sent:
                    mark_alert_sent(rep["page_id"])
                    alerted += 1
            except Exception as e:
                logger.error("  → Teams alert failed for %s: %s", competitor, redact(e))
                errors += 1

    total_scored = scored + sweep["scored"]
    total_alerted = alerted + sweep["alerted"]
    total_errors = errors + sweep["errors"]
    logger.info(
        "=== Daily poll complete: %d logged, %d resumed, %d swept, %d scored, "
        "%d alerted, %d errors ===",
        logged, resumed, sweep["processed"], total_scored, total_alerted, total_errors,
    )
    return {
        "new_changes": logged,
        "resumed": resumed,
        "swept": sweep["processed"],
        "scored": total_scored,
        "alerted": total_alerted,
        "errors": total_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily competitive change poll.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preflight and fetch, then report what would happen. No Notion "
             "writes, no Teams posts, no scoring calls.",
    )
    args = parser.parse_args()
    result = run(dry_run=args.dry_run)
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
