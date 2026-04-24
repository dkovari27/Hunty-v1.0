"""
scrapers/european/_coordinator.py — Dispatches each site to the right scraper.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import HOURS_OLD, MAX_RESULTS_PER_KEYWORD, RADIUS_MILES

from ._registry import SiteConfig, load_sites

logger = logging.getLogger(__name__)

_RADIUS_KM = max(10, round(RADIUS_MILES * 1.609))

# Number of sites scraped in parallel. Higher = faster but more RAM/CPU.
_MAX_WORKERS = 8


def _effective_keywords(site: SiteConfig, keywords: list[str]) -> list[str]:
    """
    For sites whose search URL has no {keyword} placeholder every keyword
    produces the same request.  Only scrape once to avoid N identical
    Playwright launches.
    """
    if "{keyword}" not in site.search_url:
        return keywords[:1]
    return keywords


def _dispatch(site: SiteConfig, keywords: list[str], location: str) -> list[dict]:
    """Run the appropriate scraper for a single site."""

    common = dict(
        keywords=keywords,
        location=location,
        max_results=MAX_RESULTS_PER_KEYWORD,
        hours_old=HOURS_OLD,
        radius=_RADIUS_KM,
    )

    if site.scraper == "skip":
        logger.debug(f"  Skipping {site.name} ({site.base_url})")
        return []

    if site.scraper == "jobspy_indeed":
        from ._jobspy_multi import scrape_indeed_country
        return scrape_indeed_country(
            country_indeed=site.jobspy_country,
            **common,
        )

    if site.scraper == "jobspy_glassdoor":
        from ._jobspy_multi import scrape_glassdoor
        return scrape_glassdoor(**common)

    # "stepstone" and "generic" both use the generic HTML engine
    if site.scraper in ("stepstone", "generic"):
        from ._generic import scrape_generic
        return scrape_generic(
            site_name=site.name,
            base_url=site.base_url,
            search_url_template=site.search_url,
            job_url_substr=site.job_url_substr,
            keywords=_effective_keywords(site, keywords),
            location=location,
            max_results=MAX_RESULTS_PER_KEYWORD,
            hours_old=HOURS_OLD,
        )

    logger.warning(f"Unknown scraper type '{site.scraper}' for {site.name}")
    return []


def scrape_european_sites(
    keywords: list[str],
    location: str,
    countries: list[str] | None = None,
    progress_callback=None,
) -> list[dict]:
    """
    Scrape all enabled European job sites in parallel.

    Args:
        keywords:          search terms
        location:          city/region to anchor the search (e.g. "Basel")
        countries:         if given, only scrape sites from these countries
        progress_callback: optional callable(fraction_0_to_1, message)
                           called after each site completes

    Returns:
        Deduplicated list of job dicts.
    """
    # Exclude Switzerland company career pages — those are scraped by the
    # dedicated swiss_companies scraper, not the general European boards scraper.
    sites = load_sites(exclude_swiss_companies=True)

    if countries:
        normalised = [c.lower().strip() for c in countries]
        sites = [s for s in sites if s.country.lower().strip() in normalised]

    all_jobs: list[dict] = []
    seen: set = set()
    lock = threading.Lock()          # guards all_jobs / seen across worker threads

    skipped = sum(1 for s in sites if s.scraper == "skip")
    active  = [s for s in sites if s.scraper != "skip"]
    total   = max(len(active), 1)

    logger.info(
        "European search: %d sites active, %d skipped (login/gov portal)",
        len(active), skipped,
    )

    completed = 0

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        future_to_site = {
            executor.submit(_dispatch, site, keywords, location): site
            for site in active
        }

        for future in as_completed(future_to_site):
            site = future_to_site[future]
            completed += 1

            if progress_callback:
                progress_callback(
                    completed / total,
                    f"[{site.country}] {site.name}  ({completed}/{total})",
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

    logger.info("European scraping complete — %d total unique jobs", len(all_jobs))
    return all_jobs
