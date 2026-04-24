"""
scrapers/orgchem_scraper.py — Scrapes organic-chemistry.org/jobs/europe.htm

Single-page curated list of European chemistry job postings.
Each listing links to a PDF, so no description text is available.
Title + company + location are used for pre-filtering and AI scoring.
"""
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_EUROPE_URL = "https://www.organic-chemistry.org/jobs/europe.htm"
_BASE_URL   = "https://www.organic-chemistry.org/jobs/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_orgchem() -> list[dict]:
    """Scrape European chemistry jobs from organic-chemistry.org. Returns job dicts."""
    try:
        resp = requests.get(_EUROPE_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("organic-chemistry.org fetch failed: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    jobs: list[dict] = []

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        # Find the cell that contains the job title link
        title = ""
        url   = ""
        title_cell_idx = -1
        for idx, cell in enumerate(cells):
            a = cell.find("a", href=True)
            if a and a.get_text(strip=True):
                title = " ".join(a.get_text().split())
                href  = a["href"]
                url   = href if href.startswith("http") else _BASE_URL + href.lstrip("/")
                title_cell_idx = idx
                break

        if not title:
            continue

        # Company name: extract from logo filename (e.g. logos/astrazeneca.gif → AstraZeneca)
        company = ""
        img = cells[0].find("img")
        if img:
            company = img.get("alt", "").strip()
            if not company:
                src = img.get("src", "")
                stem = src.split("/")[-1].rsplit(".", 1)[0]   # "astrazeneca"
                company = stem.replace("-", " ").replace("_", " ").title()
        if not company:
            company = cells[0].get_text(strip=True)

        # Remaining cells (excluding company + title) = location, date
        other = [cells[i].get_text(strip=True)
                 for i in range(len(cells))
                 if i != 0 and i != title_cell_idx]
        location    = other[0] if other else ""
        date_posted = other[1] if len(other) > 1 else ""

        jobs.append({
            "job_key":     url,
            "title":       title,
            "company":     company,
            "location":    location,
            "salary":      "",
            "description": "",
            "date_posted": date_posted,
            "url":         url,
            "keyword":     "",
            "source":      "organic-chemistry.org",
        })

    logger.info("organic-chemistry.org: %d jobs scraped from europe.htm", len(jobs))
    return jobs