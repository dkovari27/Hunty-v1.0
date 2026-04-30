"""
run_ci.py — CI entry point for GitHub Actions.

Runs the full scraper pipeline, generates a PDF of new jobs,
and emails it.  Exits 0 on success or when there is nothing to send.
"""
import logging
import sys

from email_sender import send_report
from main import run_job_scraper, setup_logging
from pdf_writer import generate_pdf, load_jobs_from_excel

setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the full scrape → PDF → email pipeline for CI/scheduled execution."""
    logger.info("CI run starting")

    result = run_job_scraper(countries_override=["Switzerland"])
    if result is None:
        logger.info("No jobs scraped — nothing to send.")
        sys.exit(0)

    excel_path, new_count, stats = result

    if new_count == 0:
        logger.info("No new jobs this run — skipping email.")
        sys.exit(0)

    # Build PDF from new jobs only
    pdf_path = excel_path.replace(".xlsx", ".pdf")
    jobs = load_jobs_from_excel(excel_path, new_only=True)
    if not jobs:
        logger.info("No NEW-flagged rows in Excel — skipping email.")
        sys.exit(0)
    generate_pdf(jobs, pdf_path, stats=stats)

    # Email it
    send_report(pdf_path, new_count)
    logger.info("Done — %d new jobs emailed.", new_count)


if __name__ == "__main__":
    main()
