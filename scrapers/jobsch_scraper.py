"""
scrapers/jobsch_scraper.py — Scrapes jobs.ch, the leading Swiss job board.

Parsing strategy (tried in order):
  1. __NEXT_DATA__ JSON blob  (Next.js Pages Router)
  2. /_next/data/{buildId}/en/vacancies.json  (Next.js data endpoint)
  3. Vacancy URL links in HTML  (broad-net fallback, works regardless of framework)

Diagnostic INFO logs show what was found so parsing can be tuned.
"""
import json
import logging
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

from config import MAX_RESULTS_PER_KEYWORD

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.jobs.ch"
_SEARCH_PATH = "/en/vacancies/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.jobs.ch/en/",
}

_PAGE_SIZE = 20

# Regex patterns used to clean titles extracted from HTML
import re as _re
_TIME_PREFIX = _re.compile(
    r"^(?:\d+\s+(?:day|week|month|year)s?\s+ago|last\s+(?:quarter|month|week|year))\s*",
    _re.IGNORECASE,
)
_METADATA_SUFFIX = _re.compile(
    r"\s*(?:place\s+of\s+work|workload|contract\s+type|arbeitsort|pensum)[:\s].*$",
    _re.IGNORECASE | _re.DOTALL,
)


def _clean_title(raw: str) -> str:
    """Strip jobs.ch HTML metadata from link-scraped titles."""
    t = _TIME_PREFIX.sub("", raw.strip())
    t = _METADATA_SUFFIX.sub("", t).strip()
    return t


# Field names that indicate a dict is a job posting
_JOB_TITLE_KEYS = {"title", "jobTitle", "job_title", "name", "position", "vacancy"}
_JOB_COMPANY_KEYS = {"company", "companyName", "employer", "organisation", "organization"}


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _fetch(url: str, session: requests.Session) -> requests.Response | None:
    try:
        resp = session.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        logger.warning(f"  jobs.ch fetch error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Strategy 1 — __NEXT_DATA__ JSON blob
# ---------------------------------------------------------------------------

def _looks_like_job_list(lst: list) -> bool:
    if not lst or not isinstance(lst[0], dict):
        return False
    first = set(lst[0].keys())
    has_title = bool(_JOB_TITLE_KEYS & first)
    has_company = bool(_JOB_COMPANY_KEYS & first) or "employer" in first
    has_url = bool({"url", "slug", "job_url", "href", "link", "jobUrl"} & first)
    return has_title and (has_company or has_url)


def _find_jobs_in_obj(obj, depth: int = 0) -> list | None:
    if depth > 12:
        return None

    if isinstance(obj, list):
        if _looks_like_job_list(obj):
            return obj
        for item in obj:
            result = _find_jobs_in_obj(item, depth + 1)
            if result:
                return result

    elif isinstance(obj, dict):
        priority_keys = (
            "jobs", "vacancies", "results", "items",
            "jobDocuments", "jobResults", "searchResults",
            "listings", "hits", "documents", "jobAds",
            "offers", "positions", "data",
        )
        for key in priority_keys:
            if key in obj and isinstance(obj[key], list) and obj[key]:
                if _looks_like_job_list(obj[key]):
                    return obj[key]
        for value in obj.values():
            result = _find_jobs_in_obj(value, depth + 1)
            if result:
                return result

    return None


def _extract_next_data(html: str) -> tuple[dict | None, str | None]:
    """
    Parse __NEXT_DATA__ from HTML.
    Returns (data_dict, build_id) — either may be None.
    """
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None, None
    try:
        data = json.loads(tag.string)
        return data, data.get("buildId")
    except json.JSONDecodeError:
        return None, None


def _diagnose(html: str) -> None:
    """Log structural hints so we can tune the parser."""
    soup = BeautifulSoup(html, "lxml")

    next_tag = soup.find("script", id="__NEXT_DATA__")
    if next_tag and next_tag.string:
        try:
            d = json.loads(next_tag.string)
            pp = d.get("props", {}).get("pageProps", {})
            logger.info(
                f"  [diag] __NEXT_DATA__ buildId={d.get('buildId', '?')}  "
                f"pageProps keys: {list(pp.keys())[:12] if isinstance(pp, dict) else type(pp)}"
            )
        except Exception:
            logger.info("  [diag] __NEXT_DATA__ present but unparseable")
    else:
        rsc = soup.find_all("script", string=lambda s: s and "__next_f" in s)
        if rsc:
            logger.info(f"  [diag] Next.js App Router RSC payload ({len(rsc)} chunks) — no __NEXT_DATA__")
        else:
            logger.info("  [diag] No __NEXT_DATA__ and no RSC payload found")

    vacancy_links = [
        a["href"] for a in soup.find_all("a", href=True)
        if "/vacancies/" in a["href"] and a["href"] != _SEARCH_PATH
    ]
    logger.info(f"  [diag] Vacancy links in HTML: {len(vacancy_links)}")
    logger.info(f"  [diag] HTML size: {len(html):,} chars")


# ---------------------------------------------------------------------------
# Strategy 2 — /_next/data/{buildId}/en/vacancies.json
# ---------------------------------------------------------------------------

def _fetch_nextdata_json(keyword: str, page: int, build_id: str,
                         session: requests.Session) -> dict | None:
    params = {
        "term": keyword,
        "page": page,
    }
    url = (
        f"{_BASE_URL}/_next/data/{build_id}/en/vacancies.json?"
        + urllib.parse.urlencode(params)
    )
    resp = _fetch(url, session)
    if not resp:
        return None
    try:
        return resp.json()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Strategy 3 — broad vacancy-URL link scraping
# ---------------------------------------------------------------------------

def _parse_vacancy_links(html: str, keyword: str) -> list[dict]:
    """
    Find jobs by collecting all <a> tags that link to an individual vacancy.
    Works regardless of CSS class names or JS framework version.
    """
    soup = BeautifulSoup(html, "lxml")
    jobs: list[dict] = []
    seen_urls: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href: str = a_tag["href"]
        # Individual vacancy pages have a slug after /en/vacancies/
        if not ("/en/vacancies/" in href and href.rstrip("/") != "/en/vacancies"):
            continue
        full_url = (_BASE_URL + href) if href.startswith("/") else href
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        raw_title = a_tag.get_text(strip=True)
        if not raw_title or len(raw_title) < 3:
            # Title might be in a child heading
            heading = a_tag.find(["h1", "h2", "h3", "h4"])
            raw_title = heading.get_text(strip=True) if heading else ""
        if not raw_title:
            continue
        title = _clean_title(raw_title)

        # Climb up the DOM to find sibling text (company, location)
        container = a_tag.parent
        company = ""
        location = ""
        for _ in range(4):
            if container is None:
                break
            texts = [
                el.get_text(strip=True)
                for el in container.find_all(True, recursive=False)
                if el.get_text(strip=True) and el.get_text(strip=True) != title
            ]
            if texts:
                company = texts[0] if texts else ""
                location = texts[1] if len(texts) > 1 else ""
                break
            container = container.parent

        jobs.append({
            "job_key":     "",
            "title":       title,
            "company":     company,
            "location":    location,
            "salary":      "",
            "description": "",
            "date_posted": "",
            "url":         full_url,
            "keyword":     keyword,
            "source":      "jobs.ch",
        })

    return jobs


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalise_nextdata_job(raw: dict, keyword: str) -> dict:
    title = (
        raw.get("title") or raw.get("jobTitle") or raw.get("name")
        or raw.get("position") or "Unknown"
    )
    employer = raw.get("employer") or {}
    company = (
        raw.get("company") or raw.get("companyName")
        or (employer.get("name") if isinstance(employer, dict) else "")
        or "Unknown"
    )
    location = (
        raw.get("location") or raw.get("city") or raw.get("place")
        or raw.get("workLocation") or ""
    )
    salary = raw.get("salary") or raw.get("salaryRange") or ""
    description = (
        raw.get("description") or raw.get("jobDescription")
        or raw.get("content") or ""
    )
    date_posted = (
        raw.get("date") or raw.get("publishedAt") or raw.get("createdAt")
        or raw.get("datePosted") or raw.get("publicationDate") or ""
    )
    slug = raw.get("slug") or raw.get("url") or raw.get("href") or ""
    if slug and not slug.startswith("http"):
        url = _BASE_URL + "/en/vacancies/" + slug.lstrip("/")
    else:
        url = slug or ""

    return {
        "job_key":     str(raw.get("id") or raw.get("jobId") or raw.get("externalId") or ""),
        "title":       str(title),
        "company":     str(company),
        "location":    str(location),
        "salary":      str(salary),
        "description": str(description)[:3000],
        "date_posted": str(date_posted),
        "url":         url,
        "keyword":     keyword,
        "source":      "jobs.ch",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_jobsch(keywords: list[str]) -> list[dict]:
    """
    Scrape jobs.ch for each keyword.
    Returns a deduplicated list of job dicts.
    """
    session = requests.Session()
    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    max_pages = max(1, (MAX_RESULTS_PER_KEYWORD + _PAGE_SIZE - 1) // _PAGE_SIZE)

    # Attempt to get buildId once from a short first fetch
    build_id: str | None = None

    first_keyword = keywords[0] if keywords else ""
    if first_keyword:
        seed_url = (
            _BASE_URL + _SEARCH_PATH + "?"
            + urllib.parse.urlencode({"term": first_keyword})
        )
        seed_resp = _fetch(seed_url, session)
        if seed_resp:
            _, build_id = _extract_next_data(seed_resp.text)
            if build_id:
                logger.info(f"  jobs.ch buildId: {build_id}")
            else:
                logger.info("  jobs.ch: no buildId found — will use HTML parsing")
            # Run diagnostics on this first page
            _diagnose(seed_resp.text)

    for keyword in keywords:
        logger.info(f"Scraping jobs.ch for: '{keyword}'")
        keyword_count = 0

        for page in range(1, max_pages + 1):
            # --- Strategy 1: __NEXT_DATA__ or /_next/data JSON ---
            json_data: dict | None = None

            if build_id:
                json_data = _fetch_nextdata_json(keyword, page, build_id, session)

            if json_data is None:
                # Try regular page + __NEXT_DATA__
                url = (
                    _BASE_URL + _SEARCH_PATH + "?"
                    + urllib.parse.urlencode({"term": keyword, "page": page})
                )
                resp = _fetch(url, session)
                if resp is None:
                    break
                html = resp.text
                json_data, found_build_id = _extract_next_data(html)
                if found_build_id and not build_id:
                    build_id = found_build_id
            else:
                html = ""

            new_on_page = 0

            if json_data:
                jobs_raw = _find_jobs_in_obj(json_data)
                if jobs_raw:
                    for raw in jobs_raw:
                        job = _normalise_nextdata_job(raw, keyword)
                        dedup_key = job["url"] or (job["title"].lower(), job["company"].lower())
                        if dedup_key and dedup_key not in seen_urls:
                            seen_urls.add(dedup_key)
                            all_jobs.append(job)
                            new_on_page += 1

            if new_on_page == 0 and html:
                # --- Strategy 3: broad vacancy-URL scan ---
                link_jobs = _parse_vacancy_links(html, keyword)
                for job in link_jobs:
                    dedup_key = job["url"] or (job["title"].lower(), job["company"].lower())
                    if dedup_key and dedup_key not in seen_urls:
                        seen_urls.add(dedup_key)
                        all_jobs.append(job)
                        new_on_page += 1
                if new_on_page:
                    logger.debug(f"  Page {page}: {new_on_page} jobs via link scan")

            keyword_count += new_on_page

            if new_on_page == 0:
                break  # No new results — stop paginating

            if keyword_count >= MAX_RESULTS_PER_KEYWORD:
                break

            time.sleep(1)

        logger.info(f"  {keyword_count} jobs found for '{keyword}' on jobs.ch")
        time.sleep(1.5)

    logger.info(f"jobs.ch scraping complete — {len(all_jobs)} unique jobs")
    return all_jobs
