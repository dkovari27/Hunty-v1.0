"""
config.py — Central configuration for the job scraper agent.
Edit this file to change search preferences, AI settings, and schedule.
"""
import os
from dotenv import load_dotenv

# utf-8-sig strips BOM added by Windows tools
load_dotenv(encoding="utf-8-sig")

# ---------------------------------------------------------------------------
# Which job boards to scrape (toggle True / False)
# ---------------------------------------------------------------------------
ENABLE_INDEED   = False
ENABLE_LINKEDIN = True
ENABLE_JOBSCH   = True
ENABLE_EXA      = True   # Exa semantic search (no domain restriction = company career pages)
ENABLE_ORGCHEM  = True   # organic-chemistry.org/jobs/europe.htm

# ---------------------------------------------------------------------------
# Search preferences (apply to all enabled sources)
# ---------------------------------------------------------------------------
# Used for LinkedIn, Exa, organic-chemistry.org — specific phrases work best here
SEARCH_KEYWORDS = [
    "Medicinal chemist drug discovery",
    "Synthetic medicinal chemist hit-to-lead",
    "Drug design scientist pharmaceutical",
    "Cheminformatics scientist KNIME RDKit",
    "Computational medicinal chemist",
    "Research scientist medicinal chemistry CRO",
    "AI drug discovery chemist",
    "Small molecule drug discovery scientist",
]

# Used for jobs.ch and Swiss company career pages — short terms work better
SWISS_SEARCH_KEYWORDS = [
    "medicinal chemist",
    "synthetic chemist",
    "drug discovery",
    "Chemiker",
    "medicinal chemistry",
    "organic chemist",
]
LOCATION = "Basel"
RADIUS_MILES = 25
JOB_TYPE = "fulltime"   # fulltime | parttime | contract | internship | ""
REMOTE_ONLY = False
MAX_RESULTS_PER_KEYWORD = 20
HOURS_OLD = 72           # only jobs posted within this many hours

# ---------------------------------------------------------------------------
# Your ideal job profile — Claude reads this to score relevance
# ---------------------------------------------------------------------------
JOB_PROFILE = """
Candidate: Daniel Kovari, PhD — Synthetic & Medicinal Chemist, Basel, Switzerland

CURRENT ROLE: Project Lead / Research Chemist at SpiroChem AG (CRO), Basel (Feb 2023–present)
- Leads a team of 4 chemists delivering 3D-rich small molecules (spirocycles, heterocycles, covalent probes) for pharma clients
- Primary client-facing liaison, contributed to >1M CHF contract renewal
- Designs and optimises complex multistep synthetic routes, scale-up to 50 g
- Resolved low-yielding bottlenecks achieving up to 80% yield improvement

PREVIOUS: Synthetic Chemist / PhD Candidate at AnalytiCon Discovery GmbH, Germany (2020–2022)
- Built virtual compound libraries (500+ cpds), descriptor calc, Tanimoto clustering, MaxMin diversity
- Structure-based design support: docking evaluation, ligand preparation
- KNIME data integration for design hypothesis generation

EDUCATION: PhD Medicinal Organic Chemistry (University of Birmingham, 2018–2022) | MSc Pharmaceutical Engineering (Summa Cum Laude) | BSc Organic Chemistry
PUBLICATIONS: 2 peer-reviewed papers (J. Org. Chem. 2025)

CORE SKILLS:
- Chemistry: complex multistep synthesis | route design & optimisation | spirocycles, 3D-rich scaffolds, heterocycles | scale-up mg–50 g
- Computational: KNIME | RDKit | DataWarrior | virtual library design | docking support | Python (developing)
- Leadership: project lead | client-facing | cross-functional | mentoring

TARGET ROLES: Senior Scientist / Project Lead in medicinal chemistry, drug discovery (hit-to-lead, lead optimisation), cheminformatics, OR life sciences consulting with scientific content
TARGET SECTORS: Pharma, biotech, CRO — equally open to both
LOCATION: Basel / Switzerland strongly preferred, open to EU or UK
LANGUAGES: English (fluent), Hungarian (native), German (B1 — cannot take roles requiring B2+)
NOT INTERESTED IN: Pure bench roles with no strategic component | purely business-facing roles | academia | postdocs
"""

# ---------------------------------------------------------------------------
# Pre-filter (applied before AI to save API calls)
# ---------------------------------------------------------------------------
# At least one of these must appear in title OR description (case-insensitive).
# Set to [] to disable and send every scraped job to the AI.
PREFILTER_REQUIRED = [
    # Core chemistry discipline
    "chem",           # chemistry, chemist, cheminformatics, biochem, medicinal chem
    "pharma",         # pharmaceutical, pharmacology
    "drug",           # drug discovery, drug design
    # molecule, molecular design ("molecule" != substring of "molecular")
    "molec",
    # synthesis, synthetic ("synthesis" != substring of "synthetic")
    "synth",
    "medicinal",      # medicinal chemistry (explicit)
    # Computational chemistry tools / methods
    "computational",  # computational chemistry/science
    "cheminformatics",
    "docking",        # molecular docking
    "organic",
    # Target sectors
    "biotech",        # biotechnology
]

# Jobs whose TITLE contains any of these terms are dropped before AI scoring.
PREFILTER_EXCLUDED_LOCATIONS: list[str] = [
    # Add location substrings to exclude, e.g. "wales", "united states", ", ca,"
    # Matching is case-insensitive substring against the job's location field.
]

PREFILTER_EXCLUDED_TITLE = [
    # Engineering (non-chemistry)
    "electrical engineer", "mechanical engineer", "civil engineer",
    "software engineer", "process engineer",
    # Finance / legal / admin
    "accountant", "solicitor", "lawyer", "procurement", "supply chain",
    "tax manager", "wealth", "vermögensberatung",
    # Other professions
    "nurse", "driver", "cleaner", "chef", "teacher",
    # Academic roles
    "PhD student", "PhD position", "PhD candidate",
    "professor", "lecturer", "research fellow", "research associate",
    "trainee", "laborant", "Chemikant",
    # IT / non-pharma consulting
    "IT consultant", "SAP", "solution consultant", "digital health",
    "executive search", "technology risk", "nachhaltigkeit",
    "projektmanagement", "institutionelle", "IT project",
    # Wrong biology sub-disciplines
    "microbiolog", "flow cytometry", "protein purification",
    "pharmacokinet", "pharmacodynam", "clinical pharmacolog",
    "cell biology", "cell culture", "pharmacist",
    "computational biology", "biology",
    # Manufacturing / process / quality
    "drug delivery", "drug product", "drug substance",
    "lab technician", "laboratory technician",
    "quality assurance", "quality control", "QC scientist", "QA scientist",
    "manufacturing scientist", "MSAT", "process development",
    # Seniority mismatch
    "director",
    # Wrong sub-discipline — analytical / materials
    "analytical", "material science", "material scientist",
    # Other sciences (non-chemistry)
    "atmospheric", "semiconductor", "environmental scientist",
    "bitumen", "materials scientist",
]

# ---------------------------------------------------------------------------
# Swiss company career pages (113 individual company sites in Basel / Zurich / Zug / Bern / Lausanne)
# ---------------------------------------------------------------------------
ENABLE_SWISS_COMPANIES = True    # Set True to scrape individual Swiss company career pages

# ---------------------------------------------------------------------------
# European multi-country search
# ---------------------------------------------------------------------------
ENABLE_EUROPEAN = False   # Set True to search across European job boards

# Which countries to search. Use exact names from the Excel file, or [] for ALL.
# Examples: ["Germany", "United Kingdom", "Netherlands", "Austria"]
EUROPEAN_COUNTRIES = ["Switzerland"]

# Location anchor used for European searches (can differ from LOCATION above)
EUROPEAN_LOCATION = LOCATION

# ---------------------------------------------------------------------------
# AI filter settings
# ---------------------------------------------------------------------------
# Set False to skip Claude scoring entirely and just export the pre-filtered
# jobs to Excel as-is (no API cost). Useful for reviewing raw results first.
ENABLE_AI_SCORING = False  # True - runs API .... False - no API = free run

# Jobs with score < this are still written to Excel (shown in red)
MIN_RELEVANCE_SCORE = 6
AI_MODEL = "claude-opus-4-6"

# ---------------------------------------------------------------------------
# Scheduler settings
# ---------------------------------------------------------------------------
SCHEDULE_HOUR = 8           # 24-hour clock
SCHEDULE_MINUTE = 0
SCHEDULE_TIMEZONE = "Europe/Zurich"

# ---------------------------------------------------------------------------
# Output settings
# ---------------------------------------------------------------------------
OUTPUT_DIR = "outputs"

# ---------------------------------------------------------------------------
# Anthropic API key (loaded from .env or environment)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
EXA_API_KEY = os.getenv("EXA_API_KEY", "")
