"""
scrapers/academicpositions_scraper.py — Scrapes academicpositions.com

JavaScript-rendered (Laravel Livewire SPA), so this scraper uses the
thread-local Playwright browser already set up in _playwright_scraper.py.

Search URL pattern:
  https://academicpositions.com/find-jobs?keywords={keyword}&sort=recent&page={n}

Card structure (div.list-group-item):
  a[href*='/ad/']          — job URL; first text line = title, second = summary
  a.job-link               — employer name
  div.job-locations a      — location parts
  text "Published …"       — posting date

Deadline check:
  After collecting from search pages, each detail page is fetched with plain
  requests to read "Application deadline YYYY-MM-DD …" from the sidebar.
  Jobs whose deadline has already passed are dropped.
"""
from __future__ import annotations

import logging
import time

import requests as _requests
from bs4 import BeautifulSoup

from scrapers._deadline_utils import is_expired, parse_deadline

logger = logging.getLogger(__name__)

_BASE        = "https://academicpositions.com"
_SEARCH_URL  = _BASE + "/find-jobs?keywords={keyword}&sort=recent&page={page}"
_MAX_PAGES   = 3

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _parse_html(html: str, keyword: str) -> list[dict]:
    """Parse rendered HTML and return job dicts."""
    soup  = BeautifulSoup(html, "lxml")
    cards = soup.find_all("div", class_="list-group-item")
    jobs: list[dict] = []

    for card in cards:
        # ── Job URL + title + description ────────────────────────────────
        job_a = card.find("a", href=lambda h: h and "/ad/" in h)
        if not job_a:
            continue
        url = job_a["href"]
        if not url.startswith("http"):
            url = _BASE + url

        lines = [ln.strip() for ln in job_a.get_text(separator="\n").splitlines() if ln.strip()]
        title       = lines[0] if lines else ""
        description = lines[1] if len(lines) > 1 else ""

        if not title:
            continue

        # ── Company ──────────────────────────────────────────────────────
        company_a = card.find("a", class_="job-link")
        company   = company_a.get_text(strip=True) if company_a else ""

        # ── Location ─────────────────────────────────────────────────────
        loc_div = card.find("div", class_="job-locations")
        if loc_div:
            parts    = [a.get_text(strip=True).rstrip(",") for a in loc_div.find_all("a")]
            location = ", ".join(p for p in parts if p)
        else:
            location = ""

        # ── Date posted ──────────────────────────────────────────────────
        date_posted = ""
        for text_node in card.stripped_strings:
            if text_node.lower().startswith("published"):
                date_posted = text_node.replace("Published", "").strip()
                break

        jobs.append({
            "title":       title,
            "company":     company,
            "location":    location,
            "url":         url,
            "description": description,
            "date_posted": date_posted,
            "salary":      "",
            "source":      "academicpositions.com",
            "keyword":     keyword,
        })

    return jobs


def _fetch_deadline(url: str, session: _requests.Session) -> str:
    """
    Fetch the AP job detail page and return the raw deadline string,
    or "" if not found / on error.
    Detail page is plain HTML — no Playwright needed.
    """
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for row in soup.find_all("div", class_="row"):
            if "mb-3" not in row.get("class", []):
                continue
            label = row.find("div", class_="font-weight-bold")
            if label and "application deadline" in label.get_text(strip=True).lower():
                value_div = row.find("div", class_=lambda c: c and "col-auto" in c)
                if value_div:
                    return value_div.get_text(separator=" ", strip=True)
    except Exception as exc:
        logger.debug("  [academicpositions] deadline fetch error for %s: %s", url, exc)
    return ""


def scrape_academicpositions(
    keywords: list[str],
    max_results: int = 20,
    countries: list[str] | None = None,
) -> list[dict]:
    """
    Scrape academicpositions.com for each keyword.
    Uses Playwright (headless Chromium) — JS-rendered site.
    After collecting, fetches each detail page to check the application
    deadline and drops any jobs whose deadline has already passed.
    If `countries` is provided, jobs whose location doesn't contain any
    of the listed country names are dropped.
    Returns deduplicated job dicts.
    """
    try:
        from scrapers.european._playwright_scraper import _get_thread_browser
        from playwright.sync_api import TimeoutError as PWTimeout
    except ImportError:
        logger.warning("academicpositions: playwright not installed — skipping")
        return []

    all_jobs: list[dict]  = []
    seen_urls: set[str]   = set()

    for keyword in keywords:
        kw_count = 0

        for page_num in range(1, _MAX_PAGES + 1):
            url = _SEARCH_URL.format(
                keyword=keyword.replace(" ", "+"),
                page=page_num,
            )
            logger.debug("  [academicpositions] %s page %d", keyword, page_num)

            try:
                browser = _get_thread_browser()
                context = browser.new_context(
                    user_agent=_HEADERS["User-Agent"],
                    locale="en-US",
                    viewport={"width": 1280, "height": 900},
                )
                pw_page = context.new_page()
                pw_page.on("console", lambda _: None)

                try:
                    pw_page.goto(url, wait_until="networkidle", timeout=25_000)
                except PWTimeout:
                    logger.debug("  [academicpositions] timeout on page %d", page_num)
                    context.close()
                    break

                # Dismiss cookie banner if present
                try:
                    btn = pw_page.locator("button:has-text('Accept')").first
                    if btn.is_visible(timeout=1500):
                        btn.click()
                        time.sleep(0.5)
                except Exception:
                    pass

                html = pw_page.content()
                context.close()

            except Exception as exc:
                logger.warning("  [academicpositions] browser error: %s", exc)
                break

            jobs = _parse_html(html, keyword)

            if not jobs:
                logger.debug("  [academicpositions] no cards on page %d — stopping", page_num)
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

        logger.debug("  [academicpositions] '%s': %d jobs collected", keyword, kw_count)

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
            "  [academicpositions] country filter: %d → %d jobs",
            before, len(all_jobs),
        )

    # ── Deadline filter ───────────────────────────────────────────────────────
    session = _requests.Session()
    session.headers.update(_HEADERS)

    active: list[dict] = []
    expired_count = 0

    for job in all_jobs:
        raw = _fetch_deadline(job["url"], session)
        deadline = parse_deadline(raw)
        if is_expired(deadline):
            logger.debug(
                "  [academicpositions] expired (%s): %s",
                deadline, job["title"],
            )
            expired_count += 1
        else:
            job["deadline"] = str(deadline) if deadline else ""
            active.append(job)
        time.sleep(0.3)

    logger.info(
        "academicpositions.com: %d jobs (%d expired / no-deadline dropped)",
        len(active), expired_count,
    )
    return active
