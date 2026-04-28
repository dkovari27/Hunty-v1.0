"""
config.py — Central configuration for the job scraper agent.

Personal profile and keywords live in config_personal.py (gitignored).
Copy config_personal.example.py → config_personal.py and fill in your values.
"""
import os
from dotenv import load_dotenv

# utf-8-sig strips BOM added by Windows tools
load_dotenv(encoding="utf-8-sig")

# ---------------------------------------------------------------------------
# Personal profile — imported from config_personal.py (gitignored)
# Falls back to neutral placeholders if that file does not exist.
# ---------------------------------------------------------------------------
try:
    from config_personal import (
        JOB_PROFILE,
        SEARCH_KEYWORDS,
        SWISS_SEARCH_KEYWORDS,
        PREFILTER_REQUIRED,
        PREFILTER_EXCLUDED_TITLE,
    )
except ImportError:
    # Neutral defaults — copy config_personal.example.py to config_personal.py
    JOB_PROFILE = ""               # describe your background & target roles
    SEARCH_KEYWORDS = ["job title"]    # phrases for LinkedIn / Exa
    SWISS_SEARCH_KEYWORDS = ["job title"]    # short terms for jobs.ch
    PREFILTER_REQUIRED = []               # [] = no filter, every job goes to AI
    PREFILTER_EXCLUDED_TITLE = []

# ---------------------------------------------------------------------------
# Which job boards to scrape (toggle True / False)
# ---------------------------------------------------------------------------
ENABLE_INDEED = False
ENABLE_LINKEDIN = True
ENABLE_JOBSCH = True
# Exa semantic search (no domain restriction = company career pages)
ENABLE_EXA = True
ENABLE_ORGCHEM = True   # organic-chemistry.org/jobs/europe.htm
# academicpositions.com and scholarshipdb.net are toggled via the
# Excel Status column in European_Job_Search_Websites.xlsx

# ---------------------------------------------------------------------------
# Search preferences (apply to all enabled sources)
# ---------------------------------------------------------------------------
LOCATION = "Basel"
RADIUS_MILES = 25
JOB_TYPE = "fulltime"   # fulltime | parttime | contract | internship | ""
REMOTE_ONLY = False
MAX_RESULTS_PER_KEYWORD = 20
HOURS_OLD = 72           # only jobs posted within this many hours

# ---------------------------------------------------------------------------
# Pre-filter (applied before AI to save API calls)
# ---------------------------------------------------------------------------
# Location substrings to exclude (case-insensitive match against location field)
PREFILTER_EXCLUDED_LOCATIONS: list[str] = []

# ---------------------------------------------------------------------------
# Swiss company career pages
# ---------------------------------------------------------------------------
ENABLE_SWISS_COMPANIES = True    # scrape individual Swiss company career pages

# ---------------------------------------------------------------------------
# European multi-country search
# ---------------------------------------------------------------------------
ENABLE_EUROPEAN = False   # Set True to search across European job boards

# Which countries to search. Use exact names from the Excel file, or [] for ALL.
EUROPEAN_COUNTRIES = ["Switzerland"]

# Location anchor used for European searches (can differ from LOCATION above)
EUROPEAN_LOCATION = LOCATION

# ---------------------------------------------------------------------------
# AI filter settings
# ---------------------------------------------------------------------------
# True = score with Claude (API cost); False = free run
ENABLE_AI_SCORING = False
MIN_RELEVANCE_SCORE = 6
AI_MODEL = "claude-opus-4-6"

# ---------------------------------------------------------------------------
# Scheduler settings
# ---------------------------------------------------------------------------
SCHEDULE_HOUR = 8
SCHEDULE_MINUTE = 0
SCHEDULE_TIMEZONE = "Europe/Zurich"

# ---------------------------------------------------------------------------
# Output settings
# ---------------------------------------------------------------------------
OUTPUT_DIR = "outputs"

# ---------------------------------------------------------------------------
# API keys (from .env or environment)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
EXA_API_KEY = os.getenv("EXA_API_KEY", "")
