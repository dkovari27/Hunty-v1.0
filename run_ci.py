"""
run_ci.py — CI entry point for GitHub Actions.

Modes (set via HUNTY_MODE env var):
  switzerland        Daily Mon/Wed/Thu/Fri — LinkedIn + jobs.ch + Exa, no Swiss
                     company career pages.  Fast (~10 min).
  switzerland-weekly Tuesday — same sources PLUS Swiss company career pages,
                     1.5-week lookback window.  Slow (~1.5 h).
  eu                 Manual trigger — full 14-country EU search.  Very slow (~4 h).
"""
import logging
import os
import sys

# ---------------------------------------------------------------------------
# Resolve mode and set config env vars BEFORE any config-dependent import
# ---------------------------------------------------------------------------
_mode = os.getenv("HUNTY_MODE", "switzerland").lower().strip()

_EU_COUNTRIES = [
    "Switzerland", "Germany", "United Kingdom", "Netherlands", "France",
    "Austria", "Belgium", "Denmark", "Sweden", "Norway", "Spain",
    "Italy", "Ireland", "Finland",
]

if _mode == "switzerland-weekly":
    _countries = ["Switzerland"]
    os.environ["HUNTY_SWISS"]      = "true"
    os.environ["HUNTY_HOURS_OLD"]  = "252"   # 1.5 weeks
elif _mode == "eu":
    _countries = _EU_COUNTRIES
    os.environ["HUNTY_SWISS"]      = "false"
    os.environ["HUNTY_HOURS_OLD"]  = "168"
else:  # switzerland (default)
    _countries = ["Switzerland"]
    os.environ["HUNTY_SWISS"]      = "false"
    os.environ["HUNTY_HOURS_OLD"]  = "168"

# ---------------------------------------------------------------------------
# Now safe to import config-dependent modules
# ---------------------------------------------------------------------------
from email_sender import send_report
from main import run_job_scraper, setup_logging
from pdf_writer import generate_pdf, load_jobs_from_excel

setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the full scrape → PDF → email pipeline for CI/scheduled execution."""
    logger.info(
        "CI run starting — mode=%s, countries=%d, swiss_companies=%s, hours_old=%s",
        _mode, len(_countries),
        os.environ["HUNTY_SWISS"], os.environ["HUNTY_HOURS_OLD"],
    )

    result = run_job_scraper(countries_override=_countries)
    if result is None:
        logger.info("No jobs scraped — nothing to send.")
        sys.exit(0)

    excel_path, new_count, stats = result

    if new_count == 0:
        logger.info("No new jobs this run — skipping email.")
        sys.exit(0)

    pdf_path = excel_path.replace(".xlsx", ".pdf")
    jobs = load_jobs_from_excel(excel_path, new_only=True)
    if not jobs:
        logger.info("No NEW-flagged rows in Excel — skipping email.")
        sys.exit(0)
    generate_pdf(jobs, pdf_path, stats=stats)

    send_report(pdf_path, new_count)
    logger.info("Done — %d new jobs emailed.", new_count)


if __name__ == "__main__":
    main()
