"""
run_ci.py — CI entry point for GitHub Actions.

Modes (set via HUNTY_MODE env var):
  switzerland        Daily Mon/Wed/Fri — LinkedIn (Europe-wide) + jobs.ch +
                     Exa (Switzerland).  Fast (~10 min).
  switzerland-weekly Manual trigger — same PLUS Swiss company career pages,
                     1.5-week lookback window.  Slow (~1.5 h).
  eu                 Manual trigger — full 14-country EU search.  Very slow (~4 h).

Keywords and filters are read from settings/last_used.json when present,
falling back to config_personal.py defaults.
"""
import json
import logging
import os
import pathlib
import sys

# ---------------------------------------------------------------------------
# Resolve mode and set config env vars BEFORE any config-dependent import
# ---------------------------------------------------------------------------
_mode = os.getenv("HUNTY_MODE", "switzerland").lower().strip()

# ---------------------------------------------------------------------------
# Load settings override from settings/last_used.json (committed to git)
# Provides keywords, filters, and excluded_locations set via the desktop GUI.
# Falls back to config_personal.py defaults if the file is absent.
# ---------------------------------------------------------------------------
_settings: dict = {}
try:
    _settings_path = pathlib.Path(__file__).parent / "settings" / "last_used.json"
    with open(_settings_path, encoding="utf-8") as _f:
        _settings = json.load(_f)
except Exception:
    pass

_EU_COUNTRIES = [
    "Switzerland", "Germany", "United Kingdom", "Netherlands", "France",
    "Austria", "Belgium", "Denmark", "Sweden", "Norway", "Spain",
    "Italy", "Ireland", "Finland",
]

if _mode == "switzerland-weekly":
    _countries = ["Switzerland"]
    _linkedin_location = "Europe"
    os.environ["HUNTY_SWISS"]      = "true"
    os.environ["HUNTY_HOURS_OLD"]  = "252"   # 1.5 weeks
elif _mode == "eu":
    _countries = _EU_COUNTRIES
    _linkedin_location = "Europe"
    os.environ["HUNTY_SWISS"]      = "false"
    os.environ["HUNTY_HOURS_OLD"]  = "168"
else:  # switzerland (default) — LinkedIn searches Europe, other sources Switzerland only
    _countries = ["Switzerland"]
    _linkedin_location = "Europe"
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

    result = run_job_scraper(
        countries_override=_countries,
        linkedin_location_override=_linkedin_location,
        keywords_override=_settings.get("keywords") or None,
        swiss_keywords_override=_settings.get("swiss_keywords") or None,
        prefilter_required_override=_settings.get("prefilter_required") or None,
        prefilter_excluded_override=_settings.get("prefilter_excluded") or None,
        prefilter_excluded_locations_override=_settings.get("excluded_locations") or None,
        prefilter_bypass_keywords_override=_settings.get("prefilter_bypass_keywords") or None,
    )
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
