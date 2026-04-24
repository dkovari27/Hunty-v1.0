"""
scheduler.py — Runs the job scraper daily at the time set in config.py.

Usage:
    python scheduler.py

The scheduler runs in the foreground. Press Ctrl+C to stop.
The first run happens at the next occurrence of SCHEDULE_HOUR:SCHEDULE_MINUTE.
To run immediately as well, set run_now=True below.
"""
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import SCHEDULE_HOUR, SCHEDULE_MINUTE, SCHEDULE_TIMEZONE

logger = logging.getLogger(__name__)


def start_scheduler(run_now: bool = False) -> None:
    """
    Start the blocking scheduler.

    Args:
        run_now: If True, trigger one immediate run before the daily schedule kicks in.
    """
    from main import run_job_scraper, setup_logging

    setup_logging()

    if run_now:
        logger.info("Running an immediate scrape before starting the schedule...")
        run_job_scraper()

    scheduler = BlockingScheduler(timezone=SCHEDULE_TIMEZONE)

    scheduler.add_job(
        func=run_job_scraper,
        trigger=CronTrigger(
            hour=SCHEDULE_HOUR,
            minute=SCHEDULE_MINUTE,
            timezone=SCHEDULE_TIMEZONE,
        ),
        id="daily_job_scraper",
        name="Daily Job Scraper",
        replace_existing=True,
        misfire_grace_time=3600,   # fire up to 1 h late if the machine was asleep
    )

    logger.info(
        f"Scheduler active — next run at "
        f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} {SCHEDULE_TIMEZONE} daily"
    )
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user.")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Change run_now=True to trigger an immediate scrape on startup
    start_scheduler(run_now=False)
