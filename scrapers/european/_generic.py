"""
scrapers/european/_generic.py — Generic HTML scraper used for all non-jobspy sites.

Identical strategy to the jobs.ch scraper:
  1. Try __NEXT_DATA__ JSON (Next.js Pages Router)
  2. Try /_next/data/{buildId}/ JSON endpoint
  3. Vacancy-URL link scan (broad net — works regardless of framework)

The StepStone family gets routed here too (same Next.js platform).
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse

import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Strip metadata that Swiss job boards (jobup.ch, jobscout24.ch, etc.) embed
# inside job-card links — e.g. "Last weekSenior ScientistPlace of work:Basel..."
_TIME_PREFIX = re.compile(
    r"^(?:\d+\s+(?:day|week|month|year)s?\s+ago|last\s+(?:quarter|month|week|year)"
    r"|yesterday|today|just\s+now)\s*",
    re.IGNORECASE,
)
_METADATA_SUFFIX = re.compile(
    r"\s*(?:place\s+of\s+work|workload|contract\s+type|arbeitsort|pensum"
    r"|employment\s+type|job\s+type|salary|location)[:\s].*$",
    re.IGNORECASE | re.DOTALL,
)


def _clean_title(raw: str) -> str:
    t = _TIME_PREFIX.sub("", raw.strip())
    t = _METADATA_SUFFIX.sub("", t).strip()
    return t

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_JOB_TITLE_KEYS = {"title", "jobTitle", "job_title", "name", "position", "vacancy", "heading"}
_JOB_COMPANY_KEYS = {"company", "companyName", "employer", "organisation", "organization"}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _fetch(url: str, session: requests.Session, referer: str = "") -> requests.Response | None:
    headers = dict(_HEADERS)
    if referer:
        headers["Referer"] = referer
    try:
        resp = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        logger.debug(f"    fetch error {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# __NEXT_DATA__ helpers
# ---------------------------------------------------------------------------

def _looks_like_job_list(lst: list) -> bool:
    if not lst or not isinstance(lst[0], dict):
        return False
    first = set(lst[0].keys())
    return bool(_JOB_TITLE_KEYS & first) and bool(
        (_JOB_COMPANY_KEYS & first) or {"url", "slug", "href", "link", "jobUrl", "id"} & first
    )


def _find_jobs(obj, depth: int = 0) -> list | None:
    if depth > 12:
        return None
    if isinstance(obj, list):
        if _looks_like_job_list(obj):
            return obj
        for item in obj:
            r = _find_jobs(item, depth + 1)
            if r:
                return r
    elif isinstance(obj, dict):
        for key in ("jobs", "vacancies", "results", "items", "jobDocuments",
                    "jobResults", "searchResults", "listings", "hits",
                    "documents", "jobAds", "offers", "positions", "data",
                    "adsData", "adList"):
            if key in obj and isinstance(obj[key], list) and obj[key]:
                if _looks_like_job_list(obj[key]):
                    return obj[key]
        for v in obj.values():
            r = _find_jobs(v, depth + 1)
            if r:
                return r
    return None


def _extract_next_data(html: str) -> tuple[dict | None, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None, None
    try:
        data = json.loads(tag.string)
        return data, data.get("buildId")
    except json.JSONDecodeError:
        return None, None


def _normalise(raw: dict, keyword: str, source: str, base_url: str) -> dict:
    title = (
        raw.get("title") or raw.get("jobTitle") or raw.get("heading")
        or raw.get("name") or raw.get("position") or "Unknown"
    )
    employer = raw.get("employer") or {}
    company = (
        raw.get("company") or raw.get("companyName")
        or (employer.get("name") if isinstance(employer, dict) else "")
        or "Unknown"
    )
    location = (
        raw.get("location") or raw.get("city") or raw.get("place")
        or raw.get("workLocation") or raw.get("workPlace") or ""
    )
    salary = raw.get("salary") or raw.get("salaryRange") or ""
    description = (
        raw.get("description") or raw.get("jobDescription")
        or raw.get("content") or raw.get("text") or ""
    )
    date_posted = (
        raw.get("date") or raw.get("publishedAt") or raw.get("createdAt")
        or raw.get("datePosted") or raw.get("publicationDate") or ""
    )
    slug = raw.get("slug") or raw.get("url") or raw.get("href") or ""
    if slug and not str(slug).startswith("http"):
        url = base_url + "/" + str(slug).lstrip("/")
    else:
        url = str(slug or "")

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
        "source":      source,
    }


# ---------------------------------------------------------------------------
# Vacancy-URL link scan (fallback)
# ---------------------------------------------------------------------------

def _scan_links(html: str, keyword: str, source: str,
                base_url: str, job_url_substr: list[str]) -> list[dict]:
    """Find job postings by scanning for links whose href matches job_url_substr."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[dict] = []
    seen: set[str] = set()

    # Build matchers: site-specific patterns + common generic ones
    matchers = list(job_url_substr) + [
        "/job/", "/jobs/", "/vacancy/", "/vacancies/",
        "/offre", "/stellenangebot", "/annonce", "/lavoro/",
        "/emprego/", "/praca/", "/stilling", "/jobb/",
    ]

    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        # Must match at least one pattern and not be just the listing root
        if not any(pat in href for pat in matchers):
            continue
        # Exclude root search pages
        clean_path = href.split("?")[0].rstrip("/")
        if not clean_path or clean_path in ("/jobs", "/job", "/vacancies", "/vacancy"):
            continue

        full_url = (base_url + href) if href.startswith("/") else href
        if full_url in seen:
            continue
        seen.add(full_url)

        raw = a.get_text(strip=True)
        if not raw:
            h = a.find(["h1", "h2", "h3", "h4"])
            raw = h.get_text(strip=True) if h else ""
        title = _clean_title(raw)
        if len(title) < 3:
            continue

        # Try to pick up company / location from nearby elements
        company, location = "", ""
        container = a.parent
        for _ in range(4):
            if container is None:
                break
            texts = [
                el.get_text(strip=True)
                for el in container.find_all(True, recursive=False)
                if el.get_text(strip=True) and el.get_text(strip=True) != title
            ]
            if texts:
                company  = texts[0] if texts else ""
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
            "source":      source,
        })

    return jobs


# ---------------------------------------------------------------------------
# Public scraper
# ---------------------------------------------------------------------------

def scrape_generic(
    site_name: str,
    base_url: str,
    search_url_template: str,
    job_url_substr: list[str],
    keywords: list[str],
    location: str,
    max_results: int = 20,
    hours_old: int = 72,
) -> list[dict]:
    """
    Scrape a single site using the generic strategy.
    search_url_template may contain {keyword} and {location}.
    """
    if not search_url_template:
        logger.debug(f"  [{site_name}] no search URL configured — skipping")
        return []

    session = requests.Session()
    all_jobs: list[dict] = []
    seen_urls: set[str] = set()
    build_id: str | None = None

    page_size = 20
    max_pages = max(1, (max_results + page_size - 1) // page_size)

    for keyword in keywords:
        logger.info(f"  [{site_name}] '{keyword}'")
        keyword_count = 0
        playwright_tried = False  # only attempt once per keyword

        for page in range(1, max_pages + 1):
            loc_enc = urllib.parse.quote_plus(location)
            kw_enc  = urllib.parse.quote_plus(keyword)
            url = (
                search_url_template
                .replace("{keyword}",  kw_enc)
                .replace("{location}", loc_enc)
            )
            # Append page param if the template doesn't already include it
            if page > 1 and "page=" not in url and "from=" not in url:
                sep = "&" if "?" in url else "?"
                url += f"{sep}page={page}"

            # --- Strategy 1: /_next/data JSON ---
            json_data: dict | None = None
            if build_id:
                path = urllib.parse.urlparse(url).path
                params = urllib.parse.urlparse(url).query
                next_url = f"{base_url}/_next/data/{build_id}{path}.json"
                if params:
                    next_url += "?" + params
                resp2 = _fetch(next_url, session, referer=url)
                if resp2:
                    try:
                        json_data = resp2.json()
                    except Exception:
                        pass

            # --- Fetch HTML ---
            resp = _fetch(url, session, referer=base_url + "/")
            if resp is None:
                # Site blocked requests-based fetch (403/timeout) — try Playwright
                if page == 1 and not playwright_tried:
                    playwright_tried = True
                    from ._playwright_scraper import scrape_playwright
                    pw_jobs = scrape_playwright(
                        site_name, url, job_url_substr, keyword, base_url, max_results
                    )
                    for job in pw_jobs:
                        key = job["url"] or (job["title"].lower(), job["company"].lower())
                        if key and key not in seen_urls:
                            seen_urls.add(key)
                            all_jobs.append(job)
                            keyword_count += 1
                    if pw_jobs:
                        logger.info("  [%s] playwright found %d jobs for '%s' (after HTTP block)",
                                    site_name, len(pw_jobs), keyword)
                break
            html = resp.text

            # --- Strategy 2: __NEXT_DATA__ ---
            if json_data is None:
                nd, found_bid = _extract_next_data(html)
                if nd:
                    json_data = nd
                if found_bid and not build_id:
                    build_id = found_bid

            new_on_page = 0

            if json_data:
                raw_jobs = _find_jobs(json_data)
                if raw_jobs:
                    for raw in raw_jobs:
                        if new_on_page >= max_results:
                            break
                        job = _normalise(raw, keyword, site_name, base_url)
                        key = job["url"] or (job["title"].lower(), job["company"].lower())
                        if key and key not in seen_urls:
                            seen_urls.add(key)
                            all_jobs.append(job)
                            new_on_page += 1

            # --- Strategy 3: vacancy link scan ---
            if new_on_page == 0:
                link_jobs = _scan_links(html, keyword, site_name, base_url, job_url_substr)
                # Quality filter: discard shallow nav links (e.g. /jobs/wien).
                # Real job post paths have ≥ 3 segments or a digit in the last one.
                def _path_parts(u: str) -> list[str]:
                    return [p for p in urllib.parse.urlparse(u).path.split("/") if p]

                real_link_jobs = [
                    j for j in link_jobs
                    if len(_path_parts(j["url"])) >= 3
                    or any(c.isdigit() for c in (_path_parts(j["url"]) or [""])[-1])
                    # Site-specific patterns always trusted (depth filter targets
                    # generic nav links like karriere.at /jobs/wien, not company pages)
                    or (job_url_substr and any(pat in j["url"] for pat in job_url_substr))
                ]
                for job in real_link_jobs:
                    if new_on_page >= max_results:
                        break
                    key = job["url"] or (job["title"].lower(), job["company"].lower())
                    if key and key not in seen_urls:
                        seen_urls.add(key)
                        all_jobs.append(job)
                        new_on_page += 1

            # --- Strategy 4: Playwright headless browser (JS-rendered SPAs) ---
            # Only on first page, only once per keyword, only when all else fails
            if new_on_page == 0 and page == 1 and not playwright_tried:
                playwright_tried = True
                from ._playwright_scraper import scrape_playwright
                pw_jobs = scrape_playwright(
                    site_name, url, job_url_substr, keyword, base_url, max_results
                )
                for job in pw_jobs:
                    key = job["url"] or (job["title"].lower(), job["company"].lower())
                    if key and key not in seen_urls:
                        seen_urls.add(key)
                        all_jobs.append(job)
                        new_on_page += 1
                if new_on_page:
                    logger.info("  [%s] playwright found %d jobs for '%s'",
                                site_name, new_on_page, keyword)

            keyword_count += new_on_page

            if new_on_page == 0 or keyword_count >= max_results:
                break

            time.sleep(1)

        logger.info(f"    {keyword_count} jobs")
        time.sleep(1.5)

    return all_jobs
