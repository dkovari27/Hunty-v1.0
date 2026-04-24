"""
scrapers/indeed_scraper.py — Scrapes job listings from Indeed.

NOTE: Indeed actively blocks automated scrapers. This implementation uses
realistic headers and rate-limiting delays. If you get 403 responses,
try again later or consider using residential proxies.
"""
import logging
import random
import time
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from config import (
    JOB_TYPE,
    LOCATION,
    MAX_RESULTS_PER_KEYWORD,
    RADIUS_MILES,
    REMOTE_ONLY,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.indeed.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.indeed.com/",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

_JOB_TYPE_MAP = {
    "fulltime": "fulltime",
    "parttime": "parttime",
    "contract": "contract",
    "internship": "internship",
}


def _build_search_url(keyword: str, start: int = 0) -> str:
    params = [
        f"q={quote_plus(keyword)}",
        f"l={quote_plus(LOCATION)}",
        f"radius={RADIUS_MILES}",
        f"start={start}",
    ]
    if JOB_TYPE and JOB_TYPE in _JOB_TYPE_MAP:
        params.append(f"jt={_JOB_TYPE_MAP[JOB_TYPE]}")
    if REMOTE_ONLY:
        params.append("remotejob=032b3047-a818-43d2-b9e1-e7ef27c2e54e")
    return f"{BASE_URL}/jobs?" + "&".join(params)


def _extract_job(card, keyword: str) -> dict | None:
    """Extract structured job data from a single card element."""
    job_key = card.get("data-jk", "")
    if not job_key:
        return None

    # Title — Indeed wraps it in <h2 class="jobTitle ...">
    title_el = (
        card.find("h2", class_=lambda c: c and "jobTitle" in c)
        or card.find("a", attrs={"data-jk": True})
    )
    title = title_el.get_text(" ", strip=True) if title_el else "Unknown"
    # Remove "new" prefix that Indeed sometimes injects
    title = title.removeprefix("new").strip()

    # Company
    company_el = (
        card.find("span", attrs={"data-testid": "company-name"})
        or card.find("span", class_=lambda c: c and "companyName" in c)
    )
    company = company_el.get_text(strip=True) if company_el else "Unknown"

    # Location
    location_el = (
        card.find("div", attrs={"data-testid": "text-location"})
        or card.find("div", class_=lambda c: c and "companyLocation" in c)
    )
    location = location_el.get_text(strip=True) if location_el else ""

    # Salary (not always present)
    salary_el = card.find(
        attrs={"data-testid": "attribute_snippet_testid"}
    ) or card.find("div", class_=lambda c: c and "salary" in (c or "").lower())
    salary = salary_el.get_text(strip=True) if salary_el else ""

    # Description snippet
    snippet_el = (
        card.find("div", class_=lambda c: c and "job-snippet" in (c or ""))
        or card.find("ul", class_=lambda c: c and "jobCardShelfContainer" in (c or ""))
    )
    description = snippet_el.get_text(" ", strip=True) if snippet_el else ""

    # Date posted
    date_el = card.find("span", class_=lambda c: c and "date" in (c or "").lower())
    date_posted = date_el.get_text(strip=True) if date_el else ""

    return {
        "job_key": job_key,
        "title": title,
        "company": company,
        "location": location,
        "salary": salary,
        "description": description,
        "date_posted": date_posted,
        "url": f"{BASE_URL}/viewjob?jk={job_key}",
        "keyword": keyword,
    }


def _fetch_full_description(job_key: str, session: requests.Session) -> str:
    """Fetch the full description from the job detail page."""
    try:
        time.sleep(random.uniform(1.5, 3.0))
        resp = session.get(
            f"{BASE_URL}/viewjob?jk={job_key}",
            headers=_HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        desc_el = soup.find("div", id="jobDescriptionText") or soup.find(
            "div", class_=lambda c: c and "jobsearch-jobDescriptionText" in (c or "")
        )
        if not desc_el:
            return ""
        return desc_el.get_text("\n", strip=True)[:3000]
    except requests.RequestException as e:
        logger.debug(f"Could not fetch description for {job_key}: {e}")
        return ""


def scrape_indeed(keywords: list[str]) -> list[dict]:
    """
    Scrape Indeed for job listings matching each keyword.
    Returns a deduplicated list of job dicts.
    """
    all_jobs: list[dict] = []
    seen_keys: set[str] = set()
    session = requests.Session()
    session.headers.update(_HEADERS)

    for keyword in keywords:
        logger.info(f"Scraping Indeed for: '{keyword}'")
        collected = 0
        start = 0

        while collected < MAX_RESULTS_PER_KEYWORD:
            url = _build_search_url(keyword, start)

            try:
                time.sleep(random.uniform(2.5, 4.5))
                resp = session.get(url, timeout=20)
            except requests.RequestException as e:
                logger.error(f"Network error for '{keyword}': {e}")
                break

            if resp.status_code == 403:
                logger.warning(
                    "Indeed returned 403 — rate-limited or bot-detected. "
                    "Try again later or use a proxy."
                )
                break
            if resp.status_code != 200:
                logger.warning(f"Unexpected status {resp.status_code} for '{keyword}'")
                break

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.find_all("div", attrs={"data-jk": True})

            if not cards:
                logger.info(f"No more results for '{keyword}' at offset {start}")
                break

            for card in cards:
                job = _extract_job(card, keyword)
                if not job or job["job_key"] in seen_keys:
                    continue

                seen_keys.add(job["job_key"])

                # Enrich with full description if the snippet is thin
                if len(job["description"]) < 100:
                    job["description"] = _fetch_full_description(
                        job["job_key"], session
                    )

                all_jobs.append(job)
                collected += 1

                if collected >= MAX_RESULTS_PER_KEYWORD:
                    break

            logger.info(f"  Collected {collected} jobs for '{keyword}' so far")
            start += 10  # Indeed paginates in steps of 10

    logger.info(f"Scraping complete — {len(all_jobs)} unique jobs found")
    return all_jobs
