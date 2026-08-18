"""
One-off backfill — score the rows stranded at Status = "Unscored".

Context: scoring broke mid-run on 2026-08-04 with
`400 invalid_request_error: credit balance too low` and failed on every run
after it. Because dedupe was presence-based rather than status-aware, each of
those rows was treated as an already-logged duplicate on subsequent runs and
never scored, leaving 183 rows unscored between 2026-08-03 and 2026-08-18.

This job drains that backlog. It shares its engine with the daily poll's rescue
sweep (jobs/rescore.py), so behaviour is identical — the only difference is that
this one is unbounded and interactive.

What it does per row:
  • scores it via the existing scoring agent
  • writes Significance Score, Score Reasoning, Tier (re-read from the registry)
    and the refined Category, then flips Status to "Scored"
  • writes an AI Summary for rows above the alert threshold (use
    --summarise-all to summarise every row)
  • sends NO Teams alerts by default. Backlog rows are days or weeks old by the
    time they are scored, so alerting on them means notifying people about stale
    news; they reach the team through the monthly newsletter instead. Pass
    --alerts to override, which batches them into digest cards and ticks Teams
    Alert Sent on each row a digest carried.

Safety:
  • Idempotent — only Unscored rows are read, and each is flipped to Scored as
    soon as it is written, so re-running never re-scores or re-alerts anything.
  • Rate-limited — sleeps between Anthropic calls and between Notion writes.
  • Fails closed — an Anthropic API error (credit/auth/rate) aborts the run
    rather than burning the rest of the backlog against a dead key.
  • Preflight-gated — refuses to start unless a 1-token Anthropic call succeeds.

Usage (from the competitive_intel/ directory):
    python3 -m jobs.backfill_rescore --dry-run          # what would be processed
    python3 -m jobs.backfill_rescore --yes --limit 5    # small live test first
    python3 -m jobs.backfill_rescore --yes --alerts     # opt in to Teams digests
    python3 -m jobs.backfill_rescore --yes              # the whole backlog
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _remaining_unscored_before_today() -> tuple:
    """
    Return (total_unscored, unscored_detected_before_today).

    The second number is the acceptance check: rows detected today may legitimately
    still be Unscored if the poll hasn't reached them, but anything older is backlog.
    """
    from integrations.notion_client import get_unscored_changes, extract_change_fields

    pages = get_unscored_changes()
    today = datetime.now(timezone.utc).date().isoformat()
    older = [
        p for p in pages
        if (extract_change_fields(p)["date_detected"] or "")[:10] < today
    ]
    return len(pages), len(older)


def run(
    limit=None,
    sleep_seconds: float = 1.0,
    alert: bool = True,
    summarise_all: bool = False,
    dry_run: bool = False,
) -> dict:
    from integrations.anthropic_preflight import preflight_or_exit
    from jobs.rescore import rescore_unscored

    logger.info("=== Backfill re-score started%s ===", " (DRY RUN)" if dry_run else "")

    # Same guard as the daily poll: prove the key can pay before touching data.
    preflight_or_exit("backfill re-score", fatal=not dry_run)

    stats = rescore_unscored(
        limit=limit,
        sleep_seconds=sleep_seconds,
        alert=alert,
        digest_title="Competitive Intelligence — Backlog Digest",
        summarise_all=summarise_all,
        dry_run=dry_run,
    )

    if not dry_run:
        total, older = _remaining_unscored_before_today()
        stats["remaining"] = total
        stats["remaining_before_today"] = older
        logger.info(
            "=== Backfill complete: %d processed, %d scored (%d drained empty), "
            "%d alerted, %d errors ===",
            stats["processed"], stats["scored"], stats["drained"],
            stats["alerted"], stats["errors"],
        )
        logger.info(
            "Still Unscored: %d total, %d detected before today%s",
            total, older,
            " — backlog fully drained" if older == 0 else " — re-run to finish",
        )
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill-score stranded Unscored rows.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only the N oldest Unscored rows (default: all)")
    parser.add_argument("--sleep", type=float, default=1.0,
                        help="Seconds to pause after each Anthropic call (default: 1.0)")
    parser.add_argument("--alerts", action="store_true",
                        help="Send Teams digests for above-threshold rows. OFF by default: "
                             "backlog rows are stale by the time they are scored, so they are "
                             "scored silently and reach the team via the monthly newsletter")
    parser.add_argument("--summarise-all", action="store_true",
                        help="Also write an AI Summary for below-threshold rows "
                             "(one extra Anthropic call per row)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be processed; no scoring, writes or alerts")
    parser.add_argument("--yes", action="store_true",
                        help="Required for a live run — guards against an accidental "
                             "backlog-wide Teams digest")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        logger.error(
            "Refusing to run live without --yes. Start with "
            "`python3 -m jobs.backfill_rescore --dry-run`."
        )
        return 2

    stats = run(
        limit=args.limit,
        sleep_seconds=args.sleep,
        alert=args.alerts,
        summarise_all=args.summarise_all,
        dry_run=args.dry_run,
    )
    return 0 if stats["errors"] == 0 and not stats["aborted"] else 1


if __name__ == "__main__":
    sys.exit(main())
