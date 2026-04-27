"""
config_personal.example.py — Template for your personal job-search config.

Copy this file to config_personal.py and fill in your details.
config_personal.py is gitignored so your data stays local.

For GitHub Actions: paste the contents of your config_personal.py into a
repository secret named CONFIG_PERSONAL (Settings → Secrets → Actions).
The CI workflow will recreate the file before each run.
"""

# ---------------------------------------------------------------------------
# Search keywords
# ---------------------------------------------------------------------------
# Used for LinkedIn, Exa — multi-word phrases work best
SEARCH_KEYWORDS = [
    "your job title here",
    "another search phrase",
]

# Used for jobs.ch and Swiss company career pages — short single terms work better
SWISS_SEARCH_KEYWORDS = [
    "short term",
    "another term",
]

# ---------------------------------------------------------------------------
# Your ideal job profile — Claude reads this to score relevance
# ---------------------------------------------------------------------------
JOB_PROFILE = """
Candidate: Your Name — Your Title

CURRENT ROLE: ...
EDUCATION: ...
CORE SKILLS: ...
TARGET ROLES: ...
TARGET SECTORS: ...
LOCATION: ...
NOT INTERESTED IN: ...
"""

# ---------------------------------------------------------------------------
# Pre-filter keyword lists
# ---------------------------------------------------------------------------
# At least one required term must appear in title or description.
# Set to [] to send everything to AI scoring.
PREFILTER_REQUIRED = [
    "your field keyword",
]

# Jobs whose TITLE contains any of these are dropped before AI scoring.
PREFILTER_EXCLUDED_TITLE = [
    "irrelevant role",
    "another role to exclude",
]
