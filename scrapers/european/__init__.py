"""
scrapers/european/ — Multi-country European job scraper.

Entry point:
    from scrapers.european import scrape_european_sites
    jobs = scrape_european_sites(keywords, countries=["Germany", "United Kingdom"])
    # countries=None  →  all enabled sites
"""
from ._coordinator import scrape_european_sites
from .swiss_companies import scrape_swiss_companies

__all__ = ["scrape_european_sites", "scrape_swiss_companies"]
