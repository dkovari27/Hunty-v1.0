"""
scrapers/european/_playwright_scraper.py — Headless-browser fallback for JS-rendered sites.

Used as Strategy 4 inside scrape_generic when both __NEXT_DATA__ JSON and
vacancy-link HTML scanning return 0 results (React/Vue SPA sites that build
the DOM entirely in JavaScript).

Requires:  pip install playwright && playwright install chromium
"""
from __future__ import annotations

import logging
import threading
import time
import urllib.parse

# ---------------------------------------------------------------------------
# Thread-local Playwright browser pool
# ---------------------------------------------------------------------------
# Playwright is not thread-safe — each thread must own its own instance.
# We keep one Browser alive per worker thread so Chromium is launched once
# per thread rather than once per scrape_playwright() call.

_thread_local = threading.local()


def _get_thread_browser():
    """
    Return the Chromium Browser for the calling thread, launching it on
    first use or relaunching if it has crashed/been closed.
    """
    from playwright.sync_api import sync_playwright

    browser = getattr(_thread_local, "browser", None)
    if browser is not None:
        try:
            if browser.is_connected():
                return browser
        except Exception:
            pass

    # Tear down stale playwright instance (if any) before creating a new one
    pw = getattr(_thread_local, "_pw", None)
    if pw is not None:
        try:
            pw.stop()
        except Exception:
            pass

    _thread_local._pw = sync_playwright().__enter__()
    _thread_local.browser = _thread_local._pw.chromium.launch(headless=True)
    logger.debug(
        "Launched thread-local Chromium (thread %s)", threading.current_thread().name
    )
    return _thread_local.browser

from ._generic import _clean_title


def _path_depth(url: str) -> int:
    return len([p for p in urllib.parse.urlparse(url).path.split("/") if p])


def _last_segment(url: str) -> str:
    parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
    return parts[-1] if parts else ""

logger = logging.getLogger(__name__)

# Common GDPR / cookie-banner "accept" button selectors (tried in order)
_COOKIE_SELECTORS = [
    "button#accept-all",
    "button#acceptAll",
    "button#onetrust-accept-btn-handler",
    "button[id*='accept'][id*='cookie']",
    "button[id*='accept'][id*='consent']",
    "button[data-testid*='accept']",
    "button[class*='accept'][class*='cookie']",
    "button[class*='consent'][class*='accept']",
    "[aria-label*='Accept all']",
    "[aria-label*='accept cookies']",
    "button:has-text('Accept all')",
    "button:has-text('Accept All')",
    "button:has-text('Akzeptieren')",
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Akkoord')",
    "button:has-text('Akkoord gaan')",
    "button:has-text('Accepteren')",
    "button:has-text('Accepter')",
    "button:has-text('Godkänn alla')",
    "button:has-text('Godta alle')",
    "button:has-text('Hyväksy kaikki')",
    "button:has-text('Zaakceptuj')",
    "button:has-text('Accetta')",
    "button:has-text('Aceptar')",
    "button:has-text('OK')",
]

# How long to wait for job links to appear after page load (ms)
_WAIT_TIMEOUT = 12_000


def scrape_playwright(
    site_name: str,
    search_url: str,
    job_url_substr: list[str],
    keyword: str,
    base_url: str,
    max_results: int = 20,
) -> list[dict]:
    """
    Load search_url with headless Chromium, dismiss cookie banners,
    wait for DOM to settle, then harvest job links.
    Returns a list of partial job dicts (same schema as _generic._scan_links).

    Uses a thread-local Browser so Chromium is only launched once per worker
    thread instead of once per call.
    """
    try:
        from playwright.sync_api import TimeoutError as PWTimeout
        browser = _get_thread_browser()
    except ImportError:
        logger.warning(f"  [{site_name}] playwright not installed — skipping JS scrape")
        return []
    except Exception as exc:
        logger.warning(f"  [{site_name}] could not get playwright browser: {exc}")
        return []

    matchers = list(job_url_substr) + [
        "/job/", "/jobs/", "/vacancy/", "/vacancies/",
        "/offre", "/stellenangebot", "/annonce", "/lavoro/",
        "/emprego/", "/praca/", "/stilling", "/jobb/",
    ]

    jobs: list[dict] = []
    seen: set[str] = set()
    context = None

    try:
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        # Silence noisy console output from SPAs
        page.on("console", lambda _: None)

        logger.debug(f"    [playwright/{site_name}] navigating to {search_url}")
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=20_000)
        except PWTimeout:
            logger.debug(f"    [playwright/{site_name}] page load timeout — aborting")
            return []

        # Dismiss cookie / consent dialogs (including full-page privacy gates)
        for sel in _COOKIE_SELECTORS:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=800):
                    btn.click(timeout=800)
                    logger.debug(
                        "    [playwright/%s] dismissed consent dialog (%s)",
                        site_name, sel,
                    )
                    # Full-page consent gates (e.g. DPG Media) redirect after
                    # clicking — wait for navigation to the actual search page.
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=8_000)
                    except PWTimeout:
                        pass
                    time.sleep(0.6)
                    break
            except Exception:
                pass

        # Wait for any link whose href matches a job pattern
        job_link_selector = ", ".join(
            f"a[href*='{p.strip('/')}']" for p in job_url_substr[:5]
        ) if job_url_substr else "a[href*='/job']"

        try:
            page.wait_for_selector(job_link_selector, timeout=_WAIT_TIMEOUT)
        except PWTimeout:
            logger.debug(
                f"    [playwright/{site_name}] no job links appeared "
                f"within {_WAIT_TIMEOUT}ms — trying scroll"
            )

        # Scroll down once to trigger lazy-loading
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(1.0)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.8)

        # Harvest links
        anchors = page.locator("a[href]").all()
        for a in anchors:
            try:
                href = a.get_attribute("href") or ""
            except Exception:
                continue

            if not any(pat in href for pat in matchers):
                continue

            clean_path = href.split("?")[0].rstrip("/")
            if not clean_path or clean_path in ("/jobs", "/job", "/vacancies", "/vacancy"):
                continue

            full_url = (base_url + href) if href.startswith("/") else href
            if full_url in seen:
                continue

            # Reject shallow nav links (e.g. /jobs/wien — no digits, depth ≤ 2)
            # but trust site-specific patterns (company pages at depth 2 are real jobs)
            is_site_specific = bool(
                job_url_substr and any(pat in href for pat in job_url_substr)
            )
            if not is_site_specific and _path_depth(full_url) <= 2 and not any(
                c.isdigit() for c in _last_segment(full_url)
            ):
                continue

            seen.add(full_url)

            # Prefer heading child for the title; fall back to first non-empty
            # line of inner_text (job cards pack title + metadata into one link).
            raw = ""
            try:
                h = a.locator("h1, h2, h3, h4").first
                raw = h.inner_text().strip()
            except Exception:
                pass
            if not raw:
                try:
                    full_text = a.inner_text().strip()
                    # Take first non-empty line; avoids salary/location noise
                    raw = next(
                        (ln.strip() for ln in full_text.splitlines() if ln.strip()),
                        full_text,
                    )
                except Exception:
                    raw = ""

            title = _clean_title(raw)
            if len(title) < 3:
                continue

            jobs.append({
                "job_key":     "",
                "title":       title,
                "company":     "",
                "location":    "",
                "salary":      "",
                "description": "",
                "date_posted": "",
                "url":         full_url,
                "keyword":     keyword,
                "source":      site_name,
            })

            if len(jobs) >= max_results:
                break

    except Exception as exc:
        logger.warning(f"  [{site_name}] playwright error: {exc}")
        jobs = []
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass

    logger.debug(f"    [playwright/{site_name}] found {len(jobs)} job links")
    return jobs