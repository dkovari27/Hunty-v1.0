"""
consultant_search.py — Standalone pipeline for life-sciences consulting roles.

Searches LinkedIn + Exa for pharma/biotech strategy consulting positions
suited to a PhD chemist background. Runs independently of main.py so
consultant noise doesn't pollute the core drug-discovery search.

Run:
    python consultant_search.py
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Consultant-specific search settings (edit here)
# ---------------------------------------------------------------------------
SEARCH_KEYWORDS = [
    "Life sciences consultant pharma biotech strategy",
    "Junior consultant natural science PhD drug discovery",
    "Scientific consultant medicinal chemistry R&D",
    "Management consultant life sciences chemistry background",
    "Strategy consultant pharma biotech Europe",
    "R&D consultant small molecule drug discovery",
]

# At least one must appear in title or description
PREFILTER_REQUIRED = [
    "consultant",
    "consulting",
    "advisory",
    "strategy",
]

# Drop if any of these appear in the title
PREFILTER_EXCLUDED_TITLE = [
    # IT / software consulting
    "IT consultant", "SAP", "solution consultant", "digital health",
    "technology risk", "software", "ERP", "CRM",
    # Finance / legal
    "tax", "accountant", "solicitor", "lawyer", "wealth",
    "vermögensberatung", "institutionelle",
    # Recruitment / executive search
    "executive search", "talent",
    # Unrelated management
    "projektmanagement", "supply chain", "procurement",
    "nachhaltigkeit",
    # Academic
    "PhD student", "PhD position", "PostDoc", "professor", "lecturer",
]

# Reuse core settings from main config
from config import (
    AI_MODEL,
    ANTHROPIC_API_KEY,
    EXA_API_KEY,
    HOURS_OLD,
    JOB_PROFILE,
    JOB_TYPE,
    MIN_RELEVANCE_SCORE,
    OUTPUT_DIR,
)

MAX_RESULTS_PER_KEYWORD = 20

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_file = os.path.join(OUTPUT_DIR, "consultant_search.log")
    stdout_stream = open(
        sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(stdout_stream),
            logging.FileHandler(log_file, mode="a", encoding="utf-8"),
        ],
    )


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pre-filter
# ---------------------------------------------------------------------------

def _prefilter(jobs: list[dict]) -> list[dict]:
    kept = []
    for job in jobs:
        title = job.get("title", "").lower()
        body = title + " " + job.get("description", "").lower()

        if any(e.lower() in title for e in PREFILTER_EXCLUDED_TITLE):
            continue
        if PREFILTER_REQUIRED and not any(r.lower() in body for r in PREFILTER_REQUIRED):
            continue
        kept.append(job)
    return kept


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run() -> str | None:
    from ai_filter import filter_jobs
    from excel_writer import write_excel

    logger.info("=" * 60)
    logger.info(f"Consultant search started  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    raw_jobs: list[dict] = []

    # --- LinkedIn ---
    from scrapers.linkedin_scraper import scrape_linkedin
    li_jobs = scrape_linkedin(SEARCH_KEYWORDS)
    raw_jobs.extend(li_jobs)
    logger.info(f"LinkedIn: {len(li_jobs)} jobs")

    # --- Exa ---
    if EXA_API_KEY:
        sys.path.insert(0, str(Path(__file__).parent / "exa_search"))
        from exa_scraper import scrape_exa  # type: ignore
        exa_jobs = scrape_exa(
            keywords=SEARCH_KEYWORDS,
            location="Europe",
            exa_api_key=EXA_API_KEY,
            job_type=JOB_TYPE,
            results_per_keyword=MAX_RESULTS_PER_KEYWORD,
            hours_old=HOURS_OLD * 10,
            domains=None,
            search_type="neural",
            job_profile=JOB_PROFILE,
        )
        raw_jobs.extend(exa_jobs)
        logger.info(f"Exa:      {len(exa_jobs)} jobs")
    else:
        logger.warning("EXA_API_KEY not set — skipping Exa source.")

    # --- Dedup: pass 1 by URL, pass 2 by (title, company) ---
    seen_urls: set = set()
    url_deduped: list[dict] = []
    for job in raw_jobs:
        url = job.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(job)

    seen_tc: set = set()
    unique: list[dict] = []
    for job in url_deduped:
        tc = (job.get("title", "").lower().strip(), job.get("company", "").lower().strip())
        if tc[0] and tc in seen_tc:
            continue
        seen_tc.add(tc)
        unique.append(job)

    raw_jobs = unique
    logger.info(f"Total unique: {len(raw_jobs)} ({len(url_deduped) - len(unique)} title+company dupes removed)")

    if not raw_jobs:
        logger.warning("No jobs scraped.")
        return None

    # --- Pre-filter ---
    prefiltered = _prefilter(raw_jobs)
    logger.info(f"Pre-filter: {len(prefiltered)} kept, {len(raw_jobs) - len(prefiltered)} dropped")

    if not prefiltered:
        logger.warning("All jobs dropped by pre-filter.")
        return None

    # --- AI scoring ---
    scored = filter_jobs(prefiltered)
    to_write = scored if scored else prefiltered

    # --- Excel ---
    # Prefix filename so consultant results don't overwrite drug-discovery runs
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = write_excel(to_write, all_jobs=raw_jobs,
                              filename=f"consultant_{timestamp}.xlsx")

    passed = sum(1 for j in to_write if j.get("relevance_score", 0) >= MIN_RELEVANCE_SCORE)
    logger.info(f"Done. {passed} above threshold, {len(to_write)} total — {output_path}")
    logger.info("=" * 60)
    return output_path


if __name__ == "__main__":
    setup_logging()
    run()
