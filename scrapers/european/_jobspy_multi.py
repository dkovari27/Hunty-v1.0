"""
scrapers/european/_jobspy_multi.py — Scrapes Indeed (all locales) and Glassdoor
via python-jobspy.  One function handles every country_indeed value.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _jobspy_scrape(
    keywords: list[str],
    location: str,
    site: str,                  # "indeed" or "glassdoor"
    country_indeed: str = "",   # e.g. "germany", "uk"
    max_results: int = 20,
    hours_old: int = 72,
    radius: int = 40,
    source_label: str = "",
) -> list[dict]:
    try:
        from jobspy import scrape_jobs
    except ImportError:
        logger.error("python-jobspy not installed — run: pip install python-jobspy --no-deps")
        return []

    all_jobs: list[dict] = []
    seen_urls: set[str] = set()
    label = source_label or f"{site}/{country_indeed}"

    for keyword in keywords:
        logger.info(f"  [{label}] '{keyword}'")
        try:
            kwargs: dict = dict(
                site_name=[site],
                search_term=keyword,
                location=location,
                results_wanted=max_results,
                hours_old=hours_old,
                distance=radius,
                is_remote=False,
                verbose=0,
            )
            if country_indeed:
                kwargs["country_indeed"] = country_indeed

            df = scrape_jobs(**kwargs)
        except Exception as exc:
            logger.warning(f"  [{label}] jobspy error for '{keyword}': {exc}")
            continue

        if df is None or df.empty:
            continue

        for row in df.itertuples(index=False):
            salary_parts = []
            for field in ("min_amount", "max_amount", "currency", "interval"):
                val = getattr(row, field, None)
                if val and str(val) not in ("nan", "None", ""):
                    salary_parts.append(str(val))
            salary = (
                f"{salary_parts[0]}–{salary_parts[1]} {' '.join(salary_parts[2:])}"
                if len(salary_parts) >= 2 else ""
            )

            url = str(getattr(row, "job_url", "") or "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            date_posted = str(getattr(row, "date_posted", "") or "")
            if date_posted == "nan":
                date_posted = ""

            description = str(getattr(row, "description", "") or "")
            if description == "nan":
                description = ""

            all_jobs.append({
                "job_key":     str(getattr(row, "id", "") or ""),
                "title":       str(getattr(row, "title", "") or "Unknown"),
                "company":     str(getattr(row, "company", "") or "Unknown"),
                "location":    str(getattr(row, "location", "") or ""),
                "salary":      salary,
                "description": description[:3000],
                "date_posted": date_posted,
                "url":         url,
                "keyword":     keyword,
                "source":      label,
            })

        logger.info(f"    {len(df)} jobs")

    return all_jobs


def scrape_indeed_country(
    keywords: list[str],
    location: str,
    country_indeed: str,
    max_results: int = 20,
    hours_old: int = 72,
    radius: int = 40,
) -> list[dict]:
    return _jobspy_scrape(
        keywords=keywords,
        location=location,
        site="indeed",
        country_indeed=country_indeed,
        max_results=max_results,
        hours_old=hours_old,
        radius=radius,
        source_label=f"Indeed/{country_indeed.title()}",
    )


def scrape_glassdoor(
    keywords: list[str],
    location: str,
    max_results: int = 20,
    hours_old: int = 72,
    radius: int = 40,
) -> list[dict]:
    return _jobspy_scrape(
        keywords=keywords,
        location=location,
        site="glassdoor",
        max_results=max_results,
        hours_old=hours_old,
        radius=radius,
        source_label="Glassdoor",
    )
