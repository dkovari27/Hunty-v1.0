"""
scrapers/_deadline_utils.py — Shared deadline parsing for academic scrapers.
"""
from __future__ import annotations

import re
from datetime import date, datetime


_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_deadline(text: str) -> date | None:
    """
    Parse a deadline string to a date.  Returns None when the format is
    unrecognised (caller treats unknown deadline as not-expired).

    Handles:
      2026-05-30                         ISO date
      2026-05-30 23:59 (Europe/…)        ISO with time/tz suffix
      31 Jul 2026                        day-month-year
      31 Jul 2026 - 12:00 (Europe/…)    day-month-year with time suffix
      Closing on: 2026-05-18 (Europe/…)  prefixed ISO date
    """
    if not text:
        return None
    text = text.strip()

    # ISO: 2026-05-30 (optionally followed by time / tz noise)
    m = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass

    # "31 Jul 2026" or "1 January 2026"
    m = re.search(r'\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b', text)
    if m:
        day, month_str, year = int(m.group(1)), m.group(2)[:3].lower(), int(m.group(3))
        month = _MONTH_MAP.get(month_str)
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                pass

    return None


def is_expired(deadline: date | None) -> bool:
    """True only when the deadline is known AND already passed."""
    if deadline is None:
        return False
    return deadline < date.today()
