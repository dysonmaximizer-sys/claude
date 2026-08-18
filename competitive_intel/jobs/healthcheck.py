"""
Pipeline health check — the failsafe that shouts when competitive intel stops working.

Why this exists: scoring broke on 2026-08-04 and nobody noticed for two weeks.
Every individual symptom was visible (a red workflow run, a growing pile of
Unscored rows) but nothing actively told anyone, so 183 changes went unscored
and unalerted. Silence is indistinguishable from "no competitor did anything".

This job runs daily and posts a Teams card the moment any of these is true:

  1. KEY      — the Anthropic key cannot run billed inference. This is the exact
                failure that caused the outage, and it is checked BEFORE it has a
                chance to break a run, so it is an early warning rather than a
                post-mortem.
  2. BACKLOG  — more than BACKLOG_LIMIT rows older than a day are still Unscored.
                Scoring is failing even if the workflow reports success.
  3. STALE    — nothing has been detected for STALE_DAYS. Either changedetection.io
                has stopped crawling, its API key has expired, or the poll is not
                reaching it. A pipeline can pass every other check while receiving
                nothing at all.
  4. RUNS     — the daily poll workflow last failed, or has not run for RUN_GAP_DAYS.
                Catches a disabled schedule or a workflow that never starts. Needs
                GITHUB_TOKEN; skipped when running locally without one.

Silent when everything is healthy — a daily "all fine" card would be trained out
of people within a week. Use --always-notify to force a card for testing.

Exit code 0 when healthy, 1 when any check fails, so the workflow goes red too
and you get GitHub's own notification as a second, independent signal.

Failing to DELIVER the report counts as a failure in its own right. The watchdog
speaks through Teams, so when Teams is the broken thing it has no voice — the
non-zero exit hands the job to GitHub's notifications instead.

Usage:
    python3 -m jobs.healthcheck
    python3 -m jobs.healthcheck --always-notify     # send a card even when healthy
"""

import argparse
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

BACKLOG_LIMIT = 5    # Unscored rows older than a day before we call scoring broken
STALE_DAYS = 4       # no detections for this long = nothing is arriving (covers a long weekend)
RUN_GAP_DAYS = 3     # no workflow run for this long = the schedule is not firing


def _now():
    return datetime.now(timezone.utc)


def _parse(iso: str):
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def check_key() -> dict:
    from integrations.anthropic_preflight import check_api_key, diagnosis
    r = check_api_key()
    if r["ok"]:
        return {"name": "Anthropic key", "ok": True, "detail": "can run billed inference"}
    return {
        "name": "Anthropic key", "ok": False,
        "detail": f"{r['error_type'] or 'failed'} at the {r['stage']} stage: {r['message']}",
        "extra": [f"org {r['organization_id'] or 'unknown'}",
                  f"request id {r['request_id'] or 'none'}",
                  diagnosis(r)],
    }


def check_backlog() -> dict:
    from integrations.notion_client import get_unscored_changes, extract_change_fields
    cutoff = (_now() - timedelta(days=1)).isoformat()
    old = [p for p in get_unscored_changes()
           if (extract_change_fields(p)["date_detected"] or "") < cutoff]
    if len(old) <= BACKLOG_LIMIT:
        return {"name": "Scoring backlog", "ok": True,
                "detail": f"{len(old)} row(s) unscored for over a day (limit {BACKLOG_LIMIT})"}
    return {
        "name": "Scoring backlog", "ok": False,
        "detail": f"{len(old)} rows have been Unscored for over a day (limit {BACKLOG_LIMIT}) "
                  f"— scoring is failing even if runs look green",
        "extra": ["Drain with: python3 -m jobs.backfill_rescore --yes"],
    }


def check_freshness() -> dict:
    from integrations.notion_client import get_latest_detection
    latest = get_latest_detection()
    dt = _parse(latest)
    if not dt:
        return {"name": "Detection freshness", "ok": False,
                "detail": "the Changes database is empty or its newest row has no date"}
    age = (_now() - dt).days
    if age < STALE_DAYS:
        return {"name": "Detection freshness", "ok": True,
                "detail": f"newest change detected {age} day(s) ago"}
    return {
        "name": "Detection freshness", "ok": False,
        "detail": f"nothing detected for {age} days (limit {STALE_DAYS}) — changedetection.io "
                  f"may have stopped crawling, or its API key expired",
        "extra": [f"newest row: {latest[:19]}"],
    }


def check_runs() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        return {"name": "Workflow runs", "ok": True, "detail": "skipped (no GITHUB_TOKEN)", "skipped": True}
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/daily-poll.yml/runs?per_page=5",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "User-Agent": "ci-healthcheck"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            runs = json.load(r)["workflow_runs"]
    except Exception as e:
        return {"name": "Workflow runs", "ok": False, "detail": f"could not read run history: {e}"}
    if not runs:
        return {"name": "Workflow runs", "ok": False, "detail": "the daily poll has never run"}

    last = runs[0]
    started = _parse(last["created_at"])
    age = (_now() - started).days if started else 99
    if age > RUN_GAP_DAYS:
        return {"name": "Workflow runs", "ok": False,
                "detail": f"the daily poll has not run for {age} days — is the schedule disabled? "
                          f"(GitHub disables cron workflows after 60 days of repo inactivity)"}
    if last["conclusion"] not in ("success", None):
        return {"name": "Workflow runs", "ok": False,
                "detail": f"the last daily poll run ended in {last['conclusion']}",
                "extra": [last["html_url"]]}
    return {"name": "Workflow runs", "ok": True,
            "detail": f"last run {last['conclusion'] or last['status']}, {age} day(s) ago"}


def run(always_notify: bool = False) -> dict:
    from integrations.teams_client import redact, send_status_alert

    logger.info("=== Pipeline health check ===")
    results = []
    for fn in (check_key, check_backlog, check_freshness, check_runs):
        try:
            results.append(fn())
        except Exception as e:
            results.append({"name": fn.__name__, "ok": False, "detail": f"check itself failed: {e}"})

    for r in results:
        logger.info("  %s %s — %s", "OK  " if r["ok"] else "FAIL", r["name"], r["detail"])
        for line in r.get("extra", []):
            logger.info("        %s", line)

    problems = [r for r in results if not r["ok"]]
    if problems or always_notify:
        healthy = not problems
        lines = []
        for r in results:
            if r.get("skipped"):
                continue
            lines.append(f"{'✅' if r['ok'] else '❌'} **{r['name']}** — {r['detail']}")
            lines += [f"    {e}" for e in r.get("extra", [])]
        try:
            delivered = send_status_alert(
                title="Competitive Intel: pipeline is healthy" if healthy
                      else "Competitive Intel: PIPELINE PROBLEM",
                subtitle=("All checks passed."
                          if healthy else
                          f"{len(problems)} of {len(results)} checks failed. "
                          f"Changes may be going undetected or unscored."),
                lines=lines,
                style="good" if healthy else "attention",
            )
        except Exception as e:
            delivered = False
            logger.error("Could not send the health alert to Teams: %s", redact(e))

        if not delivered:
            # The watchdog reports through Teams, so if Teams is the broken thing
            # it has no voice — which is exactly what happened on 2026-08-18, when
            # a deleted Power Automate flow made every post return
            # 400 WorkflowTriggerIsNotEnabled. Counting an undelivered report as a
            # failure turns the red run, and GitHub's own notification, into the
            # fallback channel.
            logger.error(
                "ALERTING CHANNEL IS DOWN — the health report could not be delivered "
                "to Teams, so this run exits non-zero and GitHub's failure "
                "notification is the only remaining signal. Check "
                "TEAMS_GENERAL_WEBHOOK in .env and in the repository secrets."
            )
            problems = problems + [{
                "name": "Teams delivery", "ok": False,
                "detail": "the health report could not be delivered to Teams",
            }]

    logger.info("=== %d problem(s) ===", len(problems))
    return {"problems": len(problems), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Competitive intel pipeline health check.")
    parser.add_argument("--always-notify", action="store_true",
                        help="Send a Teams card even when everything is healthy")
    args = parser.parse_args()
    return 1 if run(always_notify=args.always_notify)["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
