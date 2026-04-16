"""
Local scheduler — alternative to GitHub Actions for running on a dedicated server.

Uses APScheduler to run jobs on cron schedules.
Use this if you prefer a VPS over GitHub Actions.

For GitHub Actions (recommended), use .github/workflows/ instead.

Usage:
  cd competitive_intel
  pip install -r requirements.txt
  python scheduler.py
"""

import logging
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def daily_poll_job():
    from jobs.daily_poll import run
    run()


def monthly_score_job():
    from jobs.monthly_score import run
    run()


def monthly_newsletter_job():
    from jobs.monthly_newsletter import run
    run()


def main():
    scheduler = BlockingScheduler(timezone="UTC")

    # Daily poll — every day at 06:00 UTC
    scheduler.add_job(
        daily_poll_job,
        trigger=CronTrigger(hour=6, minute=0),
        id="daily_poll",
        name="Daily Visualping poll",
        misfire_grace_time=3600,
    )

    # Monthly scoring — 1st of each month at 08:00 UTC
    scheduler.add_job(
        monthly_score_job,
        trigger=CronTrigger(day=1, hour=8, minute=0),
        id="monthly_score",
        name="Monthly AI scoring + alerts",
        misfire_grace_time=3600,
    )

    # Monthly newsletter — 1st of each month at 09:00 UTC (1hr after scoring)
    scheduler.add_job(
        monthly_newsletter_job,
        trigger=CronTrigger(day=1, hour=9, minute=0),
        id="monthly_newsletter",
        name="Monthly Strategic Synthesis newsletter",
        misfire_grace_time=3600,
    )

    logger.info("Scheduler started. Jobs:")
    logger.info("  • Daily poll:         daily at 06:00 UTC")
    logger.info("  • Monthly scoring:    1st of month at 08:00 UTC")
    logger.info("  • Monthly newsletter: 1st of month at 09:00 UTC")
    logger.info("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
