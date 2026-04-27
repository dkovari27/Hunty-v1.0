"""
application_tracker.py — Persistent application status tracker.

Stores {url: {title, company, status, updated}} in outputs/applications.json.
Status values follow the career-ops convention so the two tools stay compatible.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

STATUSES = ["Saved", "Applied", "Interviewing", "Offer", "Rejected", "Accepted", "Withdrawn"]

_FILE = "applications.json"


def load(output_dir: str) -> dict[str, dict]:
    """Return {url: {title, company, status, updated}} from applications.json."""
    path = os.path.join(output_dir, _FILE)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.warning("Could not read applications.json: %s", exc)
    return {}


def save(output_dir: str, apps: dict[str, dict]) -> None:
    """Persist the full applications dict."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, _FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Could not save applications.json: %s", exc)


def set_status(
    output_dir: str,
    url: str,
    status: str,
    title: str = "",
    company: str = "",
) -> None:
    """
    Set (or update) the application status for a single URL.
    Loads, patches, and saves — safe to call from any context.
    """
    if status not in STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {STATUSES}")
    apps = load(output_dir)
    existing = apps.get(url, {})
    apps[url] = {
        "title":   title   or existing.get("title",   ""),
        "company": company or existing.get("company", ""),
        "status":  status,
        "updated": datetime.now().strftime("%Y-%m-%d"),
    }
    save(output_dir, apps)
    logger.info("Tracker: %s → %s (%s)", url[:60], status, apps[url]["company"] or "?")


def remove(output_dir: str, url: str) -> None:
    """Remove a URL from the tracker."""
    apps = load(output_dir)
    if url in apps:
        del apps[url]
        save(output_dir, apps)
