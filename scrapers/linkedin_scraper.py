"""
scrapers/linkedin_scraper.py — Scrapes LinkedIn job listings via python-jobspy.

python-jobspy is the only reliable way to scrape LinkedIn without a paid API.
It handles cookies, pagination, and rate-limiting automatically.

Install:  pip install python-jobspy
"""
import logging

from config import (
    HOURS_OLD,
    JOB_TYPE,
    LOCATION,
    MAX_RESULTS_PER_KEYWORD,
    RADIUS_MILES,
    REMOTE_ONLY,
)

logger = logging.getLogger(__name__)

# tls_client.Session leaks a Go goroutine on every scrape_jobs() call because
# jobspy never calls session.close().  With 12 keywords each creating a new
# session the leaked goroutines accumulate and race inside tls-client-64.dll,
# triggering a Go runtime panic (0x80000003) within ~30 seconds.
# Patching __del__ forces cleanup as soon as each session's Python ref-count
# hits zero, which happens immediately after each scrape_jobs() call returns
# (CPython's reference-counting GC, not the cyclic collector).
try:
    import tls_client as _tls_mod
    if not hasattr(_tls_mod.Session, "__del__"):
        def _tls_session_del(self):
            try:
                self.close()
            except Exception:
                pass
        _tls_mod.Session.__del__ = _tls_session_del
        logger.debug("tls_client.Session.__del__ patched to call close()")
except Exception:
    pass

# jobspy job-type mapping
_JOB_TYPE_MAP = {
    "fulltime":   "fulltime",
    "parttime":   "parttime",
    "contract":   "contract",
    "internship": "internship",
}


def _row_to_dict(row, keyword: str) -> dict:
    """Convert a jobspy DataFrame row to the standard job dict format."""
    salary_parts = []
    for field in ("min_amount", "max_amount", "currency", "interval"):
        val = getattr(row, field, None)
        if val and str(val) not in ("nan", "None", ""):
            salary_parts.append(str(val))

    if len(salary_parts) >= 2:
        salary = f"{salary_parts[0]}–{salary_parts[1]} {' '.join(salary_parts[2:])}"
    else:
        salary = ""

    date_posted = str(getattr(row, "date_posted", "") or "")
    if date_posted == "nan":
        date_posted = ""

    description = str(getattr(row, "description", "") or "")
    if description == "nan":
        description = ""

    return {
        "job_key":    str(getattr(row, "id", "") or ""),
        "title":      str(getattr(row, "title", "") or "Unknown"),
        "company":    str(getattr(row, "company", "") or "Unknown"),
        "location":   str(getattr(row, "location", "") or ""),
        "salary":     salary,
        "description": description[:3000],
        "date_posted": date_posted,
        "url":         str(getattr(row, "job_url", "") or ""),
        "keyword":     keyword,
        "source":      "LinkedIn",
    }


def scrape_linkedin(keywords: list[str], location: str = "Europe") -> list[dict]:
    """
    Scrape LinkedIn for job listings matching each keyword.
    Returns a deduplicated list of job dicts.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        logger.error(
            "python-jobspy is not installed. "
            "Run: pip install python-jobspy"
        )
        return []

    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    job_type = _JOB_TYPE_MAP.get(JOB_TYPE, "") if JOB_TYPE else ""

    for keyword in keywords:
        logger.info(f"Scraping LinkedIn for: '{keyword}' in {location}")

        try:
            df = scrape_jobs(
                site_name=["linkedin"],
                search_term=keyword,
                location=location,
                results_wanted=MAX_RESULTS_PER_KEYWORD,
                hours_old=HOURS_OLD,
                job_type=job_type or None,
                is_remote=REMOTE_ONLY,
                linkedin_fetch_description=True,
                verbose=0,
            )
        except Exception as e:
            logger.error(f"jobspy error for '{keyword}': {e}")
            continue

        if df is None or df.empty:
            logger.info(f"No LinkedIn results for '{keyword}'")
            continue

        for row in df.itertuples(index=False):
            job = _row_to_dict(row, keyword)
            url = job["url"]
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_jobs.append(job)

        logger.info(f"  {len(df)} jobs found for '{keyword}' on LinkedIn")

    logger.info(f"LinkedIn scraping complete — {len(all_jobs)} unique jobs")
    return all_jobs
