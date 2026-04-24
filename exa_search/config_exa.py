"""
exa_search/config_exa.py — Configuration for the Exa-powered job search.

Exa replaces the individual site scrapers: instead of crawling job boards
directly, it uses semantic search across the entire web (optionally focused
on specific job board domains) and returns pages with full text included.

Get a free API key at: https://exa.ai
"""
import os
import sys
from pathlib import Path

# Allow imports from the parent directory (ai_filter, excel_writer, etc.)
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", encoding="utf-8-sig")

# ---------------------------------------------------------------------------
# Inherit core settings from parent config
# ---------------------------------------------------------------------------
from config import (          # noqa: E402 (after sys.path fix)
    AI_MODEL,
    HOURS_OLD,
    JOB_PROFILE,
    JOB_TYPE,
    LOCATION,
    MAX_RESULTS_PER_KEYWORD,
    MIN_RELEVANCE_SCORE,
    OUTPUT_DIR,
    PREFILTER_EXCLUDED_TITLE,
    PREFILTER_REQUIRED,
    RADIUS_MILES,
    SEARCH_KEYWORDS,
    ANTHROPIC_API_KEY,
)

# ---------------------------------------------------------------------------
# Exa settings
# ---------------------------------------------------------------------------
EXA_API_KEY = os.getenv("EXA_API_KEY", "")

# Number of Exa results to request per keyword
EXA_RESULTS_PER_KEYWORD = 25

# Exa search type: "neural" uses pure semantic embedding search (best for
# natural-language job queries); "auto" lets Exa decide.
EXA_SEARCH_TYPE = "neural"

# How far back to search (in hours). Job postings stay live for weeks —
# 72 h was too tight; 30 days (720 h) captures a much larger pool.
EXA_HOURS_OLD = 720   # 30 days

# Restrict search to these domains (leave empty [] to search the whole web).
# A small whitelist of high-signal job-posting domains helps precision.
EXA_DOMAINS: list[str] = [
    # ── ATS platforms used by hundreds of biotechs (BIG COVERAGE MULTIPLIER) ──
    "greenhouse.io",        # Isomorphic Labs, many AI biotech startups
    "lever.co",             # Aqemia (FR), and many EU/UK drug discovery startups
    "personio.com",         # Tubulis, many European biotechs
    "breezy.hr",            # Deep Apple Therapeutics and others

    # ── Swiss pharma & biotech career pages ──
    "roche.com/careers", "novartis.com/careers", "lonza.com/careers",
    "idorsia.com", "basilea.com", "bachem.com",
    "molecular-partners.com", "adctherapeutics.com",
    "numab.com", "addextherapeutics.com",
    "ridgelinediscovery.com",        # Basel CRO / drug design (reference company)
    "spirochem.com", "synphabase.ch",
    "serengen.com",                  # Swiss DEL / medicinal chemistry

    # ── EU CROs & drug discovery ──
    "evotec.com", "charles-river.com",
    "analyticon-discovery.com",
    "domain-therapeutics.com",       # France
    "selvita.com",                   # Poland (EU CRO)
    "astrazeneca.com",               # found Basel & Oss positions
    "vib.be",                        # VIB (Flanders Institute for Biotechnology)

    # ── UK AI drug discovery ──
    "isomorphiclabs.com", "exscientia.ai",
    "chemify.io", "benevolent.ai",
    "heptares.com", "ensemble.bio",

    # ── European pharma job boards (high signal) ──
    "europharmajobs.com",            # Europe-focused pharma/biotech jobs
    "datarockstars.ai",              # found InterAx Biotech CH role
    "jobly.fi",                      # found Chemistry Lead bivalent modalities
    "xing.com",                      # German-speaking professional network (DE/AT/CH)
    "adzuna.ch",                     # Swiss jobs aggregator

    # ── Scientific recruitment agencies (EU / UK) ──
    "nextphaserecruitment.com",      # chemistry/pharma specialist recruiter
    "ckgroup.co.uk",                 # CK Group — scientific recruitment UK
    "proclinical.com",               # found Basel role
    "hbanet.org",                    # found Basel hit-to-lead scientist role

    # ── Life sciences consulting (with scientific content) ──
    "zs.com",                        # ZS Associates — pharma/biotech consulting
    "iqvia.com", "l-e-k.com",
    "simon-kucher.com",
    "mckinsey.com",
]

# ---------------------------------------------------------------------------
# Scheduler (inherited from parent, can override here)
# ---------------------------------------------------------------------------
SCHEDULE_HOUR     = 8
SCHEDULE_MINUTE   = 0
SCHEDULE_TIMEZONE = "Europe/Zurich"
