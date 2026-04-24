"""
exa_search/exa_scraper.py — Job discovery via Exa semantic search.

Instead of crawling job boards one-by-one, Exa searches across all of them
simultaneously using neural/semantic search.  Full page text is retrieved in
the same call, so the AI filter gets rich content without extra scraping.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Domains known to be dead/suspended/parked — Exa indexes stale cache of these.
_EXCLUDED_DOMAINS: set[str] = {
    "flexionis.wuaze.com",
}

# Phrases that appear in suspended/parked-page responses — drop silently.
_DEAD_PAGE_MARKERS = (
    "account suspended",
    "domain for sale",
    "this site can't be reached",
    "parking page",
    "under construction",
)


def _is_dead_result(url: str, text: str) -> bool:
    """Return True if the result is from a dead/suspended site."""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if host in _EXCLUDED_DOMAINS or any(host.endswith("." + d) for d in _EXCLUDED_DOMAINS):
        return True
    text_lower = text.lower()[:500]
    return any(marker in text_lower for marker in _DEAD_PAGE_MARKERS)


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def _build_query(keyword: str, location: str, job_type: str = "") -> str:
    """
    Build a neural-search query optimised for job-posting intent.

    Neural search works best with natural-language sentences that describe
    the ideal document — not keyword lists.  The query reads like a job ad
    title + context so Exa's embeddings land near actual vacancy pages.
    """
    loc_phrase = f" in {location}" if location else " in Switzerland and Europe"
    return (
        f"We are hiring a {keyword}{loc_phrase}. "
        "Apply now. Pharmaceutical biotech CRO drug discovery. "
        "Full-time position, responsibilities, requirements, qualifications."
    )


# ---------------------------------------------------------------------------
# Result normalisation
# ---------------------------------------------------------------------------

_COMPANY_PATTERNS = [
    re.compile(r"(?:at|@|–|-)\s+([A-Z][A-Za-z0-9 &.,'-]{2,40})\s*(?:\||$)", re.MULTILINE),
    re.compile(r"Company[:\s]+([A-Za-z0-9 &.,'-]{2,40})", re.IGNORECASE),
    re.compile(r"Employer[:\s]+([A-Za-z0-9 &.,'-]{2,40})", re.IGNORECASE),
]

_LOCATION_PATTERNS = [
    re.compile(r"Location[:\s]+([A-Za-z0-9 ,/-]{2,50})", re.IGNORECASE),
    re.compile(r"(?:Based in|Office in|Position in)[:\s]+([A-Za-z0-9 ,/-]{2,50})", re.IGNORECASE),
]


def _extract_company(title: str, text: str) -> str:
    """Try to pull a company name from the page title or body."""
    for pat in _COMPANY_PATTERNS:
        m = pat.search(title) or pat.search(text[:1000])
        if m:
            return m.group(1).strip()
    # Fallback: second segment of the title (common pattern: "Job Title | Company")
    for sep in (" | ", " - ", " – ", " — "):
        if sep in title:
            parts = title.split(sep)
            if len(parts) >= 2:
                return parts[-1].strip()
    return ""


def _extract_location(text: str, fallback: str) -> str:
    for pat in _LOCATION_PATTERNS:
        m = pat.search(text[:2000])
        if m:
            return m.group(1).strip()
    return fallback


def _normalise(result, keyword: str) -> dict:
    """Convert an Exa SearchResult to the standard job dict."""
    title    = (result.title or "Unknown").strip()
    url      = result.url or ""
    text     = result.text or ""
    pub_date = ""

    if result.published_date:
        try:
            pub_date = result.published_date[:10]   # keep YYYY-MM-DD
        except Exception:
            pub_date = str(result.published_date)

    # Try to identify company from title / body
    company  = _extract_company(title, text)
    location = _extract_location(text, "")

    # Clean job title: strip company suffix if present
    clean_title = title
    for sep in (" | ", " - ", " – ", " — "):
        if sep in title:
            clean_title = title.split(sep)[0].strip()
            break

    return {
        "job_key":     url,
        "title":       clean_title,
        "company":     company,
        "location":    location,
        "salary":      "",
        "description": text[:3000],
        "date_posted": pub_date,
        "url":         url,
        "keyword":     keyword,
        "source":      "Exa",
        # Exa's own relevance score (0–1), stored for reference
        "exa_score":   getattr(result, "score", None),
    }


# ---------------------------------------------------------------------------
# Public scraper
# ---------------------------------------------------------------------------

def scrape_exa(
    keywords: list[str],
    location: str,
    exa_api_key: str,
    job_type: str = "",
    results_per_keyword: int = 20,
    hours_old: int = 72,
    domains: list[str] | None = None,
    search_type: str = "auto",
    autoprompt: bool = True,   # kept for API compatibility, no longer used
    job_profile: str = "",
) -> list[dict]:
    """
    Use Exa semantic search to find job postings for each keyword.
    Returns a deduplicated list of job dicts with full text included.
    """
    if not exa_api_key:
        logger.error(
            "EXA_API_KEY is not set. "
            "Add EXA_API_KEY=your_key to your .env file."
        )
        return []

    try:
        from exa_py import Exa
    except ImportError:
        logger.error("exa-py not installed — run: pip install exa-py")
        return []

    client = Exa(api_key=exa_api_key)
    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    # Date filter: only pages published/indexed within hours_old
    start_date = (
        datetime.now(timezone.utc) - timedelta(hours=hours_old)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    for keyword in keywords:
        query = _build_query(keyword, location, job_type)
        logger.info(f"[Exa] '{keyword}'  query: {query!r}")

        try:
            kwargs: dict = dict(
                query=query,
                type=search_type,
                num_results=results_per_keyword,
                start_published_date=start_date,
                text=True,
            )
            if domains:
                kwargs["include_domains"] = domains

            response = client.search_and_contents(**kwargs)
            results  = response.results

        except Exception as exc:
            logger.error(f"[Exa] API error for '{keyword}': {exc}")
            continue

        new = 0
        for result in results:
            url = result.url or ""
            if not url or url in seen_urls:
                continue
            text = result.text or ""
            if _is_dead_result(url, text):
                logger.debug("[Exa] Skipping dead/suspended URL: %s", url)
                continue
            seen_urls.add(url)
            job = _normalise(result, keyword)
            all_jobs.append(job)
            new += 1

        logger.info(f"  {new} results")

    logger.info(f"Exa scraping complete — {len(all_jobs)} unique results")
    return all_jobs
