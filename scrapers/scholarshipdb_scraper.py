"""
scrapers/scholarshipdb_scraper.py — Scrapes scholarshipdb.net

Server-rendered HTML site (Ruby on Rails), so plain requests + BeautifulSoup
works fine — no Playwright needed.

Search URL pattern:
  https://scholarshipdb.net/scholarships?page={n}&q={keyword}&st=listed

Card structure (ul.list-unstyled > li):
  h4 > a[href*='/jobs-in-']       — job URL + title
  second div:
    a[href*='/scholarships-at-']  — institution / employer
    span.text-success             — city (optional)
    a.text-success                — country
    span.text-muted               — relative date ("about 3 hours ago")
  third div > p                   — description snippet

Deadline check:
  After collecting from search pages, each detail page is fetched to read
  "Deadline: DD Mon YYYY" from div.summary.  Jobs whose deadline has already
  passed are dropped.
"""
from __future__ import annotations

import logging
import time

import requests
from bs4 import BeautifulSoup

from scrapers._deadline_utils import is_expired, parse_deadline

logger = logging.getLogger(__name__)

_BASE       = "https://scholarshipdb.net"
_SEARCH_URL = _BASE + "/scholarships?page={page}&q={keyword}&st=listed"
_MAX_PAGES  = 3

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _parse_html(html: str, keyword: str) -> list[dict]:
    """Parse rendered HTML and return job dicts."""
    soup = BeautifulSoup(html, "lxml")

    # Results are in the 9-column right-hand panel
    col = soup.find("div", class_=lambda c: c and "col-sm-9" in (c if isinstance(c, str) else " ".join(c)))
    if not col:
        col = soup  # fallback: search the whole page

    results_ul = col.find("ul", class_="list-unstyled")
    if not results_ul:
        return []

    jobs: list[dict] = []

    for li in results_ul.find_all("li", recursive=False):
        # ── Title + URL ───────────────────────────────────────────────────
        title_a = li.find("a", href=lambda h: h and "/jobs-in-" in h)
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        if not title:
            continue
        url = _BASE + title_a["href"]

        # ── Meta row: institution | [city |] country | date ───────────────
        divs = li.find_all("div", recursive=False)
        company   = ""
        location  = ""
        date_posted = ""

        if len(divs) > 1:
            meta = divs[1]
            inst_a = meta.find("a", href=lambda h: h and "/scholarships-at-" in h)
            company = inst_a.get_text(strip=True) if inst_a else ""

            city_span   = meta.find("span", class_="text-success")
            country_a   = meta.find("a",    class_="text-success")
            loc_parts = []
            if city_span:
                loc_parts.append(city_span.get_text(strip=True))
            if country_a:
                loc_parts.append(country_a.get_text(strip=True))
            location = ", ".join(loc_parts)

            date_span = meta.find("span", class_="text-muted")
            date_posted = date_span.get_text(strip=True) if date_span else ""

        # ── Description snippet ────────────────────────────────────────────
        description = ""
        if len(divs) > 2:
            p = divs[2].find("p")
            description = p.get_text(strip=True) if p else ""

        jobs.append({
            "title":       title,
            "company":     company,
            "location":    location,
            "url":         url,
            "description": description,
            "date_posted": date_posted,
            "salary":      "",
            "source":      "scholarshipdb.net",
            "keyword":     keyword,
        })

    return jobs


def _fetch_deadline(url: str, session: requests.Session) -> str:
    """
    Fetch the SDB job detail page and return the raw deadline string,
    or "" if not found / on error.
    Primary:  dt 'Application Deadline' → dd text
    Fallback: div.summary text matching 'Deadline: …'
    """
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # dt / dd structure (most reliable)
        for dt in soup.find_all("dt"):
            if "deadline" in dt.get_text(strip=True).lower():
                dd = dt.find_next_sibling("dd")
                if dd:
                    return dd.get_text(strip=True)

        # summary div fallback
        summary = soup.find("div", class_="summary")
        if summary:
            import re
            m = re.search(r"deadline:\s*(.+?)(?:\s*job\s|\s*$)", summary.get_text(strip=True), re.IGNORECASE)
            if m:
                return m.group(1).strip()

    except Exception as exc:
        logger.debug("  [scholarshipdb] deadline fetch error for %s: %s", url, exc)
    return ""


def scrape_scholarshipdb(
    keywords: list[str],
    max_results: int = 20,
    countries: list[str] | None = None,
) -> list[dict]:
    """
    Scrape scholarshipdb.net for each keyword.
    Uses plain HTTP requests — server-rendered HTML, no JS needed.
    After collecting, fetches each detail page to check the application
    deadline and drops any jobs whose deadline has already passed.
    If `countries` is provided, jobs whose location doesn't contain any
    of the listed country names are dropped.
    Returns deduplicated job dicts.
    """
    session = requests.Session()
    session.headers.update(_HEADERS)

    all_jobs: list[dict] = []
    seen_urls: set[str]  = set()

    for keyword in keywords:
        kw_count = 0

        for page_num in range(1, _MAX_PAGES + 1):
            url = _SEARCH_URL.format(
                keyword=keyword.replace(" ", "+"),
                page=page_num,
            )
            logger.debug("  [scholarshipdb] %s page %d", keyword, page_num)

            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("  [scholarshipdb] request error: %s", exc)
                break

            jobs = _parse_html(resp.text, keyword)

            if not jobs:
                logger.debug("  [scholarshipdb] no cards on page %d — stopping", page_num)
                break

            added = 0
            for job in jobs:
                if job["url"] not in seen_urls:
                    seen_urls.add(job["url"])
                    all_jobs.append(job)
                    added += 1
                    kw_count += 1
                    if kw_count >= max_results:
                        break

            if kw_count >= max_results:
                break

            time.sleep(0.5)

        logger.debug("  [scholarshipdb] '%s': %d jobs collected", keyword, kw_count)

    # ── Country filter ────────────────────────────────────────────────────────
    if countries:
        _country_lower = {c.lower() for c in countries}
        before = len(all_jobs)
        all_jobs = [
            j for j in all_jobs
            if not j.get("location")
            or any(c in j["location"].lower() for c in _country_lower)
        ]
        logger.debug(
            "  [scholarshipdb] country filter: %d → %d jobs",
            before, len(all_jobs),
        )

    # ── Deadline filter ───────────────────────────────────────────────────────
    active: list[dict] = []
    expired_count = 0

    for job in all_jobs:
        raw = _fetch_deadline(job["url"], session)
        deadline = parse_deadline(raw)
        if is_expired(deadline):
            logger.debug(
                "  [scholarshipdb] expired (%s): %s",
                deadline, job["title"],
            )
            expired_count += 1
        else:
            job["deadline"] = str(deadline) if deadline else ""
            active.append(job)
        time.sleep(0.3)

    logger.info(
        "scholarshipdb.net: %d jobs (%d expired dropped)",
        len(active), expired_count,
    )
    return active
