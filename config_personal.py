"""
config_personal.py — Your job-search profile and keyword preferences.

This file is gitignored so your personal details never appear in version
control.  Copy config_personal.example.py to get started; fill in your own
values below.

On GitHub Actions, the CI workflow writes this file from the secret
CONFIG_PERSONAL before running — see .github/workflows/hunty.yml.
"""

# ---------------------------------------------------------------------------
# Search keywords
# ---------------------------------------------------------------------------
# Used for LinkedIn, Exa, organic-chemistry.org — specific phrases work best
SEARCH_KEYWORDS = [
    "AI drug discovery chemist",
    "Cheminformatics scientist KNIME RDKit",
    "Computational medicinal chemist",
    "Drug design scientist pharmaceutical",
    "Medicinal chemist drug discovery",
    "Research scientist medicinal chemistry CRO",
    "Small molecule drug discovery scientist",
    "Synthetic medicinal chemist hit-to-lead",
]

# Used for jobs.ch and Swiss company career pages — short terms work better
SWISS_SEARCH_KEYWORDS = [
    "Chemiker",
    "drug discovery",
    "medicinal chemist",
    "medicinal chemistry",
    "organic chemist",
    "synthetic chemist",
]

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

TARGET ROLES: Senior Scientist / Project Lead in medicinal chemistry or drug discovery (hit-to-lead, lead optimisation) | PostDoc in medicinal chemistry / cheminformatics (must have synthesis component, not pure computational) | industry PostDoc at big pharma (Roche, Novartis, etc.) especially welcome | life sciences consulting with scientific content
TARGET SECTORS: Pharma, biotech, CRO, universities — equally open to all. Permanent academic positions (lecturer, PI) are fine too.
LOCATION: Basel / Switzerland strongly preferred for PostDoc and industry roles; open to broader Europe / UK for PostDoc
LANGUAGES: English (fluent), Hungarian (native), German (B1 — cannot take roles requiring C1 or above)
NOT INTERESTED IN: professorship | purely business-facing roles with no scientific content | pure bench roles with no strategic or intellectual component
"""

# ---------------------------------------------------------------------------
# Pre-filter keyword lists
# ---------------------------------------------------------------------------
# At least one of these must appear in title OR description (case-insensitive).
# Set to [] to disable and send every scraped job to the AI.
PREFILTER_REQUIRED = [
    "chem",           # chemistry, chemist, cheminformatics, biochem, medicinal chem
    "pharma",         # pharmaceutical, pharmacology
    "drug",           # drug discovery, drug design
    "molec",          # molecule, molecular design
    "synth",          # synthesis, synthetic
    "medicinal",
    "computational",
    "cheminformatics",
    "docking",
    "organic",
    "biotech",
]

# Jobs whose TITLE contains any of these terms are dropped before AI scoring.
PREFILTER_EXCLUDED_TITLE = [
    # Engineering (non-chemistry)
    "electrical engineer", "mechanical engineer", "civil engineer",
    "software engineer", "process engineer",
    # Finance / legal / admin
    "accountant", "solicitor", "lawyer", "procurement", "supply chain",
    "tax manager", "wealth", "vermögensberatung",
    # Other professions
    "nurse", "driver", "cleaner", "chef", "teacher",
    # Academic roles — block PhD and associate; allow "fellow" (PostDocs often use that title)
    "PhD candidate", "PhD course", "PhD position", "PhD programme", "PhD student",
    "faculty position", "lecturer", "professor", "research associate",
    "trainee", "laborant", "Chemikant",
    # Medical / clinical / nursing
    "administrative coordinator", "aprn",
    "clinical research coordinator",
    "medical technologist",
    "occupational safety",
    "registered nurse", "rn -",
    "rehab therapy", "therapy aide",
    # IT / non-pharma consulting
    "executive search", "IT consultant", "IT project",
    "digital health", "institutionelle", "nachhaltigkeit",
    "projektmanagement", "SAP", "solution consultant", "technology risk",
    # Marketing / admin
    "chancellor", "marketing",
    # Wrong biology sub-disciplines
    "biologics",
    "cell biology", "cell culture",
    "clinical pharmacolog",
    "computational biology", "biology",
    "flow cytometry",
    "immunoinformatics",
    "microbiolog",
    "pharmacist",
    "pharmacodynam", "pharmacokinet",
    "protein purification",
    "proteomics", "single cell",
    # Manufacturing / process / quality
    "drug delivery", "drug product", "drug substance",
    "lab technician", "laboratory technician",
    "manufacturing scientist", "MSAT", "process development",
    "quality assurance", "quality control", "QA scientist", "QC scientist",
    # Seniority mismatch
    "director",
    # Wrong sub-discipline — analytical / materials / coatings
    "analytical", "bitumen", "coating", "material science", "material scientist",
    "materials scientist", "paint",
    # Other sciences (non-chemistry)
    "atmospheric", "environmental scientist", "semiconductor",
    # Courses / non-jobs
    "non-credit",
    # German operations roles
    "Fachmitarbeiter",
]
