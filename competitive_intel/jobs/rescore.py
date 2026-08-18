"""
Shared re-scoring engine for stranded rows — the rows sitting in the Changes DB
with Status = "Unscored".

Used by two callers:
  • jobs/daily_poll.py       — a bounded rescue sweep at the start of every run
                               (RESCUE_SWEEP_LIMIT rows), so a scoring outage
                               drains itself over the following runs.
  • jobs/backfill_rescore.py — a one-off unbounded pass over the whole backlog.

Why a sweep and not just status-aware dedupe: dedupe only ever sees changes
still inside the poll's 76h lookback window. A row stranded on day 1 of an
outage falls out of that window by day 4 and is never re-fetched at all, so no
dedupe rule can rescue it. Sweeping Unscored rows directly is what makes the
invariant true — a run that dies mid-scoring leaves nothing permanently stuck.

Safety properties:
  • Idempotent. Only rows with Status = "Unscored" are touched, and a scored row
    is flipped to "Scored" immediately, so a re-run never re-scores it.
  • Alert-safe. A row is only queued for alerting if Teams Alert Sent is False,
    and the checkbox is ticked as soon as the digest carrying it is delivered.
  • Rate-limited. Sleeps between Anthropic calls and between Notion writes.
  • Fails closed on billing. An anthropic.APIError (credit / rate / auth) aborts
    the sweep rather than burning the remaining rows against a dead key.
"""

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Notion's API allows ~3 requests/second; this paces the per-row property writes.
NOTION_WRITE_SLEEP = 0.35


def rescore_unscored(
    limit: Optional[int] = None,
    sleep_seconds: float = 1.0,
    alert: bool = True,
    digest_title: str = "Competitive Intelligence — Backlog Digest",
    summarise_all: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Score every (or the first `limit`) Unscored row in the Changes DB.

    Args:
      limit:         max rows to process. None = the whole backlog.
      sleep_seconds: pause after each Anthropic call.
      alert:         send Teams digests for rows above ALERT_SCORE_THRESHOLD.
      digest_title:  headline on the digest card.
      summarise_all: also write an AI Summary for below-threshold rows. Off by
                     default — that mirrors the daily poll, which only
                     summarises what it alerts on, and avoids one extra
                     Anthropic call per row nobody reads.
      dry_run:       report what would be processed; no Anthropic calls, no
                     Notion writes, no Teams posts.

    Returns:
      {"candidates", "processed", "scored", "drained", "alerted", "errors",
       "remaining", "aborted"}
    """
    import anthropic

    from config import ALERT_SCORE_THRESHOLD, COMPETITORS, DIGEST_CHUNK_SIZE
    from integrations.notion_client import (
        extract_change_fields,
        get_unscored_changes,
        mark_alert_sent,
        update_change_meta,
        update_change_score,
        update_change_summary,
    )
    from integrations.teams_client import redact, send_digest_alert
    from agents.scoring_agent import score_change
    from agents.summariser_agent import summarise_change

    pages = get_unscored_changes()
    candidates = len(pages)
    logger.info("Rescore: %d row(s) with Status = Unscored", candidates)

    if limit is not None and candidates > limit:
        logger.info("Rescore: processing the %d oldest (limit=%d)", limit, limit)
        pages = pages[:limit]

    stats = {
        "candidates": candidates,
        "processed": 0,
        "scored": 0,
        "drained": 0,
        "alerted": 0,
        "errors": 0,
        "remaining": candidates,
        "aborted": False,
    }

    if dry_run:
        by_competitor: dict = {}
        for page in pages:
            fields = extract_change_fields(page)
            by_competitor.setdefault(fields["competitor"] or "(none)", []).append(fields)
        logger.info("Rescore DRY RUN — would process %d row(s):", len(pages))
        for competitor, rows in sorted(by_competitor.items(), key=lambda kv: -len(kv[1])):
            dates = sorted((r["date_detected"] or "")[:10] for r in rows)
            logger.info(
                "  %-20s %3d row(s)  %s → %s", competitor, len(rows),
                dates[0] if dates else "?", dates[-1] if dates else "?",
            )
        stats["processed"] = len(pages)
        return stats

    pending: list = []  # alert-worthy rows awaiting a digest flush

    def _flush(final: bool = False) -> None:
        """
        Send buffered alert-worthy rows as digest card(s) and tick Teams Alert
        Sent on everything that actually went out. Flushing in chunks as we go
        (rather than once at the end) bounds what a mid-run crash loses.
        """
        if not alert or not pending:
            return
        if not final and len(pending) < DIGEST_CHUNK_SIZE:
            return
        while pending and (final or len(pending) >= DIGEST_CHUNK_SIZE):
            chunk = pending[:DIGEST_CHUNK_SIZE]
            dates = sorted((i["date_detected"] or "")[:10] for i in chunk if i["date_detected"])
            span = f"{dates[0]} → {dates[-1]}" if dates else ""
            subtitle = (
                f"{len(chunk)} change(s) scoring above {ALERT_SCORE_THRESHOLD}"
                + (f" · detected {span}" if span else "")
            )
            try:
                sent = send_digest_alert(chunk, digest_title, subtitle)
            except Exception as e:
                logger.error("  → Teams digest failed (%d row(s) left unalerted): %s",
                             len(chunk), redact(e))
                stats["errors"] += 1
                # break, not continue: the chunk stays in `pending` so the
                # end-of-run tally is honest, and continuing here would spin
                # forever on an undrained buffer.
                break
            if not sent:
                break  # Teams unconfigured — same reasoning
            del pending[:DIGEST_CHUNK_SIZE]
            stats["alerted"] += len(chunk)
            for item in chunk:
                try:
                    mark_alert_sent(item["page_id"])
                    time.sleep(NOTION_WRITE_SLEEP)
                except Exception as e:
                    logger.error("  → Could not tick Teams Alert Sent on %s: %s", item["page_id"], e)
                    stats["errors"] += 1

    for page in pages:
        fields = extract_change_fields(page)
        page_id = fields["page_id"]
        competitor = fields["competitor"] or "(unknown)"
        # Tier is re-read from the registry: it is authoritative and may have
        # changed since the row was logged.
        tier = COMPETITORS.get(competitor, {}).get("tier") or fields["tier"] or "Tier 2"
        stats["processed"] += 1

        raw_change = (fields["raw_change"] or "").strip()
        if not raw_change:
            # Nothing to score. Drain it to Scored with a minimum score rather
            # than leaving it Unscored, or every future sweep retries it forever.
            try:
                update_change_score(page_id, 1, "No diff captured for this row — nothing to score.")
                time.sleep(NOTION_WRITE_SLEEP)
                stats["scored"] += 1
                stats["drained"] += 1
                logger.info("  %s — empty Raw Change, drained at 1/10", competitor)
            except Exception as e:
                logger.error("  %s — could not drain empty row %s: %s", competitor, page_id, e)
                stats["errors"] += 1
            continue

        try:
            score, reasoning, refined_category = score_change(
                competitor_name=competitor,
                tier=tier,
                category=fields["category"] or "Other",
                url=fields["url"],
                raw_change=raw_change,
            )
        except anthropic.APIError as e:
            # Credit, auth and rate errors will hit every remaining row
            # identically. Stop instead of burning the backlog against them.
            logger.error(
                "  Anthropic API error on %s (%s) — ABORTING sweep after %d row(s): %s",
                competitor, page_id, stats["processed"] - 1, e,
            )
            stats["errors"] += 1
            stats["aborted"] = True
            break
        except Exception as e:
            logger.error("  Scoring failed for %s (%s): %s", competitor, page_id, e)
            stats["errors"] += 1
            continue
        time.sleep(sleep_seconds)

        try:
            update_change_score(page_id, score, reasoning)
            time.sleep(NOTION_WRITE_SLEEP)
            update_change_meta(page_id, tier=tier, category=refined_category)
            time.sleep(NOTION_WRITE_SLEEP)
            stats["scored"] += 1
        except Exception as e:
            logger.error("  Notion write failed for %s (%s): %s", competitor, page_id, e)
            stats["errors"] += 1
            continue
        logger.info("  %s — %d/10 (%s) — %s", competitor, score, refined_category, reasoning)

        above_threshold = score > ALERT_SCORE_THRESHOLD
        summary = ""
        if above_threshold or summarise_all:
            try:
                summary = summarise_change(
                    competitor_name=competitor,
                    tier=tier,
                    category=refined_category,
                    score=score,
                    score_reasoning=reasoning,
                    raw_change=raw_change,
                    url=fields["url"],
                )
                time.sleep(sleep_seconds)
                update_change_summary(page_id, summary)
                time.sleep(NOTION_WRITE_SLEEP)
            except anthropic.APIError as e:
                logger.error("  Summarisation hit an API error for %s — ABORTING sweep: %s", competitor, e)
                stats["errors"] += 1
                stats["aborted"] = True
                break
            except Exception as e:
                logger.error("  Summarisation failed for %s: %s", competitor, e)
                summary = reasoning
                stats["errors"] += 1

        if above_threshold and not fields["teams_alert_sent"]:
            pending.append({
                "page_id": page_id,
                "competitor": competitor,
                "tier": tier,
                "category": refined_category,
                "score": score,
                "summary": summary or reasoning,
                "url": fields["url"],
                "date_detected": fields["date_detected"],
            })
            _flush()

    _flush(final=True)

    if pending:
        # Three different situations used to share one warning that guessed at the
        # cause. Deliberately running with alerting off is not a fault, and a
        # warning that cries wolf on an intended choice teaches people to ignore it.
        if not alert:
            logger.info(
                "%d row(s) scored above the alert threshold. Alerting was disabled "
                "for this run, so no Teams card was sent and Teams Alert Sent stays "
                "unticked on them. They are Scored, so nothing will re-visit them.",
                len(pending),
            )
        elif not os.environ.get("TEAMS_GENERAL_WEBHOOK", ""):
            logger.warning(
                "%d alert-worthy row(s) were scored but not alerted: "
                "TEAMS_GENERAL_WEBHOOK is not set. Teams Alert Sent left unticked.",
                len(pending),
            )
        else:
            logger.warning(
                "%d alert-worthy row(s) were scored but the Teams digest did not "
                "send. Teams Alert Sent left unticked. These rows are now Scored, "
                "so a re-run will NOT retry them — alert them by hand if they matter.",
                len(pending),
            )

    stats["remaining"] = max(0, candidates - stats["scored"])
    logger.info(
        "Rescore complete: %d processed, %d scored (%d drained empty), %d alerted, "
        "%d errors, ~%d still Unscored%s",
        stats["processed"], stats["scored"], stats["drained"], stats["alerted"],
        stats["errors"], stats["remaining"], " (ABORTED)" if stats["aborted"] else "",
    )
    return stats
