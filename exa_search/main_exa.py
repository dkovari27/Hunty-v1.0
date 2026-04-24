"""
exa_search/main_exa.py — Exa-powered job search pipeline.

Pipeline:
  Exa semantic search  ┐
  LinkedIn (jobspy)    ┘→ merge & dedup → keyword pre-filter → Claude AI scoring → Excel output

Run:  python exa_search/main_exa.py
  or: cd exa_search && python main_exa.py
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure parent directory is on the path for shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_exa import (
    ANTHROPIC_API_KEY,
    EXA_API_KEY,
    EXA_DOMAINS,
    EXA_HOURS_OLD,
    EXA_RESULTS_PER_KEYWORD,
    EXA_SEARCH_TYPE,
    JOB_PROFILE,
    JOB_TYPE,
    LOCATION,
    MAX_RESULTS_PER_KEYWORD,
    MIN_RELEVANCE_SCORE,
    OUTPUT_DIR,
    PREFILTER_EXCLUDED_TITLE,
    PREFILTER_REQUIRED,
    RADIUS_MILES,
    SEARCH_KEYWORDS,
)

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_file = os.path.join(OUTPUT_DIR, "scraper_exa.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(
                open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)
            ),
            logging.FileHandler(log_file, mode="a", encoding="utf-8"),
        ],
    )


# ---------------------------------------------------------------------------
# LinkedIn scrape via jobspy
# ---------------------------------------------------------------------------

def _scrape_linkedin() -> list[dict]:
    """Scrape LinkedIn using python-jobspy. Returns normalised job dicts."""
    try:
        from jobspy import scrape_jobs
    except ImportError:
        logger.warning("python-jobspy not installed — skipping LinkedIn. Run: pip install python-jobspy")
        return []

    import pandas as pd

    all_jobs: list[dict] = []
    for keyword in SEARCH_KEYWORDS:
        logger.info(f"[LinkedIn] '{keyword}'")
        try:
            df: pd.DataFrame = scrape_jobs(
                site_name=["linkedin"],
                search_term=keyword,
                location="Switzerland",
                distance=RADIUS_MILES,
                job_type=JOB_TYPE or None,
                results_wanted=MAX_RESULTS_PER_KEYWORD,
                hours_old=EXA_HOURS_OLD,
                linkedin_fetch_description=True,
                is_remote=False,
            )
        except Exception as exc:
            logger.error(f"[LinkedIn] Error for '{keyword}': {exc}")
            continue

        if df is None or df.empty:
            logger.info("  0 results")
            continue

        new = 0
        for _, row in df.iterrows():
            url = str(row.get("job_url") or "")
            job: dict = {
                "job_key":     url,
                "title":       str(row.get("title") or ""),
                "company":     str(row.get("company") or ""),
                "location":    str(row.get("location") or ""),
                "salary":      str(row.get("min_amount") or ""),
                "description": str(row.get("description") or "")[:3000],
                "date_posted": str(row.get("date_posted") or ""),
                "url":         url,
                "keyword":     keyword,
                "source":      "LinkedIn",
                "exa_score":   None,
            }
            all_jobs.append(job)
            new += 1
        logger.info(f"  {new} results")

    logger.info(f"LinkedIn scraping complete — {len(all_jobs)} results (before dedup)")
    return all_jobs


# ---------------------------------------------------------------------------
# Pre-filter (same as main pipeline)
# ---------------------------------------------------------------------------

def _prefilter(jobs: list[dict]) -> list[dict]:
    kept = []
    for job in jobs:
        title = job.get("title", "").lower()
        body  = title + " " + job.get("description", "").lower()
        if any(excl.lower() in title for excl in PREFILTER_EXCLUDED_TITLE):
            continue
        if PREFILTER_REQUIRED and not any(req.lower() in body for req in PREFILTER_REQUIRED):
            continue
        kept.append(job)
    return kept


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_exa_job_search() -> str | None:
    from ai_filter import filter_jobs
    from excel_writer import write_excel
    from exa_scraper import scrape_exa

    logger.info("=" * 60)
    logger.info(f"Exa run started  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Keywords:  {SEARCH_KEYWORDS}")
    logger.info(f"Location:  {LOCATION}")
    logger.info(f"Domains:   {len(EXA_DOMAINS)} job boards targeted")
    logger.info(f"Window:    {EXA_HOURS_OLD}h ({EXA_HOURS_OLD // 24}d)")

    # Step 1a — Exa semantic search
    exa_jobs = scrape_exa(
        keywords=SEARCH_KEYWORDS,
        location="Switzerland",    # broad; distance from Basel shown in Excel
        exa_api_key=EXA_API_KEY,
        job_type=JOB_TYPE,
        results_per_keyword=EXA_RESULTS_PER_KEYWORD,
        hours_old=EXA_HOURS_OLD,
        domains=EXA_DOMAINS or None,
        search_type=EXA_SEARCH_TYPE,
        job_profile=JOB_PROFILE,
    )
    logger.info(f"Exa results: {len(exa_jobs)} raw")

    # Step 1b — LinkedIn scrape
    linkedin_jobs = _scrape_linkedin()
    logger.info(f"LinkedIn results: {len(linkedin_jobs)} raw")

    raw_jobs = exa_jobs + linkedin_jobs

    if not raw_jobs:
        logger.warning("No results from either source. Check API keys and query settings.")
        return None

    # Step 2 — Deduplicate by URL
    seen: set[str] = set()
    unique: list[dict] = []
    for job in raw_jobs:
        key = job.get("url") or (job.get("title", "").lower(), job.get("company", "").lower())
        if key and key not in seen:
            seen.add(key)
            unique.append(job)
    raw_jobs = unique
    logger.info(f"After dedup: {len(raw_jobs)}")

    # Step 3 — Keyword pre-filter
    prefiltered = _prefilter(raw_jobs)
    logger.info(
        f"Pre-filter: {len(prefiltered)} kept, "
        f"{len(raw_jobs) - len(prefiltered)} dropped"
    )

    if not prefiltered:
        logger.warning("All results dropped by pre-filter.")
        return None

    # Step 4 — Claude AI scoring
    scored = filter_jobs(prefiltered)
    to_write = scored if scored else prefiltered

    # Step 5 — Always export to Excel
    output_path = write_excel(to_write, all_jobs=raw_jobs)

    passed = sum(1 for j in to_write if j.get("relevance_score", 0) >= MIN_RELEVANCE_SCORE)
    logger.info(f"Done. {passed} above threshold, {len(to_write)} total written")
    logger.info(f"Output: {output_path}")
    logger.info("=" * 60)

    return output_path


if __name__ == "__main__":
    setup_logging()
    run_exa_job_search()
