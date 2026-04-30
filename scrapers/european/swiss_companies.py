"""
scrapers/european/swiss_companies.py — Dedicated scraper for Switzerland
company career pages.

Loads the Switzerland company entries from European_Job_Search_Websites.xlsx
(excluding the three Swiss job-board aggregators, which stay in the European
boards scraper).  Uses the same parallel-dispatch engine as the coordinator.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from ._coordinator import _MAX_WORKERS, _dispatch, _effective_keywords
from ._playwright_scraper import cleanup_thread_playwright
from ._registry import load_swiss_company_sites

logger = logging.getLogger(__name__)


def scrape_swiss_companies(
    keywords: list[str],
    location: str,
    progress_callback=None,
) -> list[dict]:
    """
    Scrape all Switzerland company career pages in parallel.

    Args:
        keywords:          search terms
        location:          location anchor (e.g. "Switzerland")
        progress_callback: optional callable(fraction_0_to_1, message)

    Returns:
        Deduplicated list of job dicts.
    """
    sites = load_swiss_company_sites()

    if not sites:
        logger.info("Swiss companies: no sites loaded")
        return []

    active  = [s for s in sites if s.scraper != "skip"]
    skipped = len(sites) - len(active)
    total   = max(len(active), 1)

    logger.info(
        "Swiss companies: %d sites active, %d skipped",
        len(active), skipped,
    )

    all_jobs: list[dict] = []
    seen: set = set()
    lock = threading.Lock()
    completed = 0

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        future_to_site = {
            executor.submit(
                _dispatch, site, _effective_keywords(site, keywords), location
            ): site
            for site in active
        }

        for future in as_completed(future_to_site):
            site = future_to_site[future]
            completed += 1

            if progress_callback:
                progress_callback(
                    completed / total,
                    f"[Swiss co.] {site.name}  ({completed}/{total})",
                )

            try:
                jobs = future.result()
            except Exception as exc:
                logger.error("  Error scraping %s: %s", site.name, exc)
                jobs = []

            if not jobs:
                continue

            added = 0
            with lock:
                for job in jobs:
                    key = job.get("url") or (
                        job.get("title", "").lower(),
                        job.get("company", "").lower(),
                    )
                    if key and key not in seen:
                        seen.add(key)
                        all_jobs.append(job)
                        added += 1

            if added:
                logger.info("  [%s] → %d unique jobs", site.name, added)

        # Close Playwright browsers on every worker thread before the next
        # scraper phase begins — prevents lingering Chromium processes.
        for _ in range(_MAX_WORKERS):
            executor.submit(cleanup_thread_playwright)

    logger.info("Swiss companies: %d total unique jobs", len(all_jobs))
    return all_jobs
