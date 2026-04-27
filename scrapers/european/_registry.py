"""
scrapers/european/_registry.py — Site registry loaded from the Excel file.

Each site has:
  scraper       : "jobspy_indeed" | "jobspy_glassdoor" | "stepstone"
                  | "generic" | "skip"
  search_url    : URL template ({keyword} and {location} substituted)
  job_url_substr: substring(s) that identify individual job-page links
  jobspy_country: jobspy country_indeed value (Indeed sites only)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import openpyxl

_EXCEL_PATH = Path(__file__).parent.parent.parent / "European_Job_Search_Websites.xlsx"

# Swiss job-board aggregators — stay in the European boards scraper.
# Every other Switzerland entry in the Excel is a company career page and is
# handled by scrape_swiss_companies() instead.
_SWISS_JOB_BOARDS: frozenset[str] = frozenset({
    "www.jobup.ch",
    "www.jobscout24.ch",
    "www.job-room.ch",
})


@dataclass
class SiteConfig:
    country: str
    name: str
    base_url: str
    description: str
    scraper: str = "generic"
    search_url: str = ""
    job_url_substr: list[str] = field(default_factory=list)
    jobspy_country: str = ""
    keywords_override: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-domain overrides
# ---------------------------------------------------------------------------
_OVERRIDES: dict[str, dict] = {
    # ── jobspy: Indeed locales ──────────────────────────────────────────────
    "fr.indeed.com":              {"scraper": "jobspy_indeed", "jobspy_country": "france"},
    "de.indeed.com":              {"scraper": "jobspy_indeed", "jobspy_country": "germany"},
    "nl.indeed.com":              {"scraper": "jobspy_indeed", "jobspy_country": "netherlands"},
    "ie.indeed.com":              {"scraper": "jobspy_indeed", "jobspy_country": "ireland"},
    "it.indeed.com":              {"scraper": "jobspy_indeed", "jobspy_country": "italy"},
    "es.indeed.com":              {"scraper": "jobspy_indeed", "jobspy_country": "spain"},
    "se.indeed.com":              {"scraper": "jobspy_indeed", "jobspy_country": "sweden"},
    "uk.indeed.com":              {"scraper": "jobspy_indeed", "jobspy_country": "uk"},

    # ── jobspy: Glassdoor ───────────────────────────────────────────────────
    "www.glassdoor.com":          {"scraper": "jobspy_glassdoor"},

    # ── LinkedIn already handled in main pipeline ───────────────────────────
    "www.linkedin.com":           {"scraper": "skip"},

    # ── StepStone family ────────────────────────────────────────────────────
    "www.stepstone.de": {
        "scraper": "stepstone",
        "search_url": "https://www.stepstone.de/jobs/{keyword}?radius=30&sort=2",
        "job_url_substr": ["/stellenangebot--", "/job/"],
    },
    "www.stepstone.at": {
        "scraper": "stepstone",
        "search_url": "https://www.stepstone.at/jobs/{keyword}?radius=30&sort=2",
        "job_url_substr": ["/stellenangebot--", "/job/"],
    },
    "www.stepstone.be": {
        "scraper": "stepstone",
        "search_url": "https://www.stepstone.be/jobs/{keyword}?radius=30&sort=2",
        "job_url_substr": ["/job/", "/offre-emploi/"],
    },

    # ── skip: login-required / heavily-protected government portals ─────────
    "www.xing.com":               {"scraper": "skip"},
    "www.vdab.be":                {"scraper": "skip"},
    "www.leforem.be":             {"scraper": "skip"},
    "www.francetravail.fr":       {"scraper": "skip"},
    "www.apec.fr":                {"scraper": "skip"},
    "www.arbeitsagentur.de":      {"scraper": "skip"},
    "www.werk.nl":                {"scraper": "skip"},
    "arbeidsplassen.nav.no":      {"scraper": "skip"},
    "arbetsformedlingen.se":      {"scraper": "skip"},
    "tyomarkkinatori.fi":         {"scraper": "skip"},
    "tyopaikat.oikotie.fi":       {"scraper": "skip"},
    "www.olx.pl":                 {"scraper": "skip"},

    # ── Swiss company career pages ─────────────────────────────────────────────
    # ─ Dead / redirected domains — no working careers page found ────────────────
    "allocyte.com":       {"scraper": "skip"},   # moved to allocyte-pharmaceuticals.com, no careers page
    "pharmabio.me":       {"scraper": "skip"},   # moved to pharmabiome.com, no careers page
    "stromaltx.com":      {"scraper": "skip"},   # moved to stromaltherapeutics.ch, no careers page
    "sydra.io":           {"scraper": "skip"},   # moved to sydra.bio, no careers page
    # ─ Big pharma — skip: all well-indexed on LinkedIn, only duplicates ───────
    "careers.roche.com":              {"scraper": "skip"},   # Roche + Roche Diagnostics
    "www.careers.jnj.com":           {"scraper": "skip"},   # J&J
    "jobs.sanofi.com":               {"scraper": "skip"},
    "jobs.boehringer-ingelheim.com": {"scraper": "skip"},
    "careers.amgen.com":             {"scraper": "skip"},
    "careers.astrazeneca.com":       {"scraper": "skip"},
    "jobs.takeda.com":               {"scraper": "skip"},
    "careers.abbvie.com":            {"scraper": "skip"},
    "careers.regeneron.com":         {"scraper": "skip"},
    "www.novartis.com":              {"scraper": "skip"},
    "www.pfizer.com":                {"scraper": "skip"},
    "www.bayer.com":                 {"scraper": "skip"},
    "www.biogen.com":                {"scraper": "skip"},
    "careers.bms.com":               {"scraper": "skip"},   # Bristol Myers Squibb
    "jobs.gilead.com":               {"scraper": "skip"},
    "www.gsk.com":                   {"scraper": "skip"},
    "www.modernatx.com":             {"scraper": "skip"},
    "www.sandoz.com":                {"scraper": "skip"},
    "careers.idorsia.com":           {"scraper": "skip"},   # Cornerstone ATS too slow
    # ─ Workday ───────────────────────────────────────────────────────────────
    "beigene.wd3.myworkdayjobs.com": {
        "search_url": "https://beigene.wd3.myworkdayjobs.com/beigene?q={keyword}",
        "job_url_substr": ["/beigene/job/"],
    },
    "siegfried.wd103.myworkdayjobs.com": {
        "search_url": "https://siegfried.wd103.myworkdayjobs.com/external?q={keyword}",
        "job_url_substr": ["/external/job/"],
    },
    # ─ Other ATS ─────────────────────────────────────────────────────────────
    "careers.bachem.com": {"scraper": "skip"},
    "sobi.csod.com": {
        "search_url": "https://sobi.csod.com/ats/careersite/search.aspx?site=2&c=sobi&q={keyword}",
        "job_url_substr": ["/careersite/", "/ats/"],
    },
    "apply.workable.com/debiopharm": {"scraper": "skip"},   # Workable ATS too slow — check manually
    "celonic-ag.jobs.personio.com": {
        "search_url": "https://celonic-ag.jobs.personio.com?search={keyword}",
        "job_url_substr": ["/job/"],
    },
    # ─ Greenhouse boards ─────────────────────────────────────────────────────
    "job-boards.greenhouse.io/blueprintmedicines": {
        "search_url": "https://job-boards.greenhouse.io/blueprintmedicines",
        "job_url_substr": ["/blueprintmedicines/jobs/"],
    },
    "job-boards.greenhouse.io/skyhawktherapeutics": {
        "search_url": "https://job-boards.greenhouse.io/skyhawktherapeutics",
        "job_url_substr": ["/skyhawktherapeutics/jobs/"],
    },
    # ─ Ashby boards (JS-rendered; Playwright handles these) ──────────────────
    "jobs.ashbyhq.com/tandem": {
        "search_url": "https://jobs.ashbyhq.com/tandem?search={keyword}",
        "job_url_substr": ["/tandem/"],
        "keywords_override": ["chemist"],   # Ashby ignores search param; scrape once
    },
    "jobs.ashbyhq.com/roivant": {
        "search_url": "https://jobs.ashbyhq.com/roivant?search={keyword}",
        "job_url_substr": ["/roivant/"],
    },
    "jobs.ashbyhq.com/WindwardBio": {
        "search_url": "https://jobs.ashbyhq.com/WindwardBio?search={keyword}",
        "job_url_substr": ["/WindwardBio/"],
    },
    "jobs.ashbyhq.com/brightpeak": {
        "search_url": "https://jobs.ashbyhq.com/brightpeak?search={keyword}",
        "job_url_substr": ["/brightpeak/"],
    },
    "jobs.ashbyhq.com/MonteRosaTherapeutics": {
        "search_url": "https://jobs.ashbyhq.com/MonteRosaTherapeutics?search={keyword}",
        "job_url_substr": ["/MonteRosaTherapeutics/"],
    },
    "jobs.ashbyhq.com/alentis": {
        "search_url": "https://jobs.ashbyhq.com/alentis?search={keyword}",
        "job_url_substr": ["/alentis/"],
    },
    "jobs.ashbyhq.com/vir": {
        "search_url": "https://jobs.ashbyhq.com/vir?search={keyword}",
        "job_url_substr": ["/vir/"],
    },
    "jobs.ashbyhq.com/immunocore": {
        "search_url": "https://jobs.ashbyhq.com/immunocore?search={keyword}",
        "job_url_substr": ["/immunocore/"],
    },
    "jobs.ashbyhq.com/captor": {
        "search_url": "https://jobs.ashbyhq.com/captor?search={keyword}",
        "job_url_substr": ["/captor/"],
    },
    "jobs.ashbyhq.com/noema": {
        "search_url": "https://jobs.ashbyhq.com/noema?search={keyword}",
        "job_url_substr": ["/noema/"],
    },
    # ─ Simple listing pages (no keyword filter; scrapes all open roles) ───────
    "www.carbogen-amcis.com": {
        "search_url": "https://www.carbogen-amcis.com/careers/open-positions",
        "job_url_substr": ["/open-positions/"],
    },
    "www.philogen.com": {
        "search_url": "https://www.philogen.com/en/careers",
        "job_url_substr": ["/careers/"],
    },
    "oculis.com": {
        "search_url": "https://oculis.com/jobs/",
        "job_url_substr": ["/jobs/"],
    },
    # ─ Skip: LinkedIn-only, email-only, or rebranded ─────────────────────────
    "www.linkedin.com":             {"scraper": "skip"},   # catches Abbmira entry
    "noemapharma.com":              {"scraper": "skip"},   # moved to Ashby board above

    # ── generic: search URL + job-link patterns ─────────────────────────────
    "www.karriere.at": {
        "search_url": "https://www.karriere.at/jobs/{keyword}?location={location}",
        "job_url_substr": ["/jobs/"],
    },
    "www.jobindex.dk": {
        "search_url": "https://www.jobindex.dk/jobsoegning?q={keyword}&maxdate=3",
        "job_url_substr": ["/jobannonce/"],
    },
    "www.workindenmark.dk": {
        "search_url": "https://www.workindenmark.dk/job-seeker/job-search?query={keyword}",
        "job_url_substr": ["/job-view/"],
    },
    "duunitori.fi": {
        "search_url": "https://duunitori.fi/tyopaikat?haku={keyword}",
        "job_url_substr": ["/tyopaikat/haku/"],
    },
    "www.irishjobs.ie": {
        "search_url": "https://www.irishjobs.ie/Jobs/Show-Results.aspx?Keywords={keyword}&Recruiter=Company",
        "job_url_substr": ["/Jobs/Show-Job.aspx", "/job/"],
    },
    "www.jobs.ie": {
        "search_url": "https://www.jobs.ie/SearchJobs/?Keywords={keyword}",
        "job_url_substr": ["/JobDetail/"],
    },
    "www.infojobs.it": {
        "search_url": "https://www.infojobs.it/offerte-lavoro/?field_1={keyword}",
        "job_url_substr": ["/annunci-lavoro/"],
    },
    "www.monster.it": {
        "search_url": "https://www.monster.it/lavoro/cerca/?q={keyword}&where=Italia&sort=newest",
        "job_url_substr": ["/lavoro/l-"],
    },
    "www.nationalevacaturebank.nl": {
        "search_url": "https://www.nationalevacaturebank.nl/vacature/zoeken?query={keyword}&location={location}&distance=50",
        "job_url_substr": ["/vacature/"],
    },
    "www.finn.no": {
        "search_url": "https://www.finn.no/job/fulltime/search.html?q={keyword}&sort=3",
        "job_url_substr": ["/job/fulltime/ad.html", "/job/management/ad.html"],
    },
    "www.jobbnorge.no": {
        "search_url": "https://www.jobbnorge.no/search/en?q={keyword}",
        "job_url_substr": ["/jobs/"],
    },
    "www.pracuj.pl": {
        "search_url": "https://www.pracuj.pl/praca/{keyword};kw?sm=1",
        "job_url_substr": ["/praca/", "/job/"],
    },
    "nofluffjobs.com": {
        "search_url": "https://nofluffjobs.com/jobs?criteria=keyword%3A{keyword}",
        "job_url_substr": ["/job/"],
    },
    "www.net-empregos.com": {
        "search_url": "https://www.net-empregos.com/pesquisa-empregos.asp?s={keyword}&cat=0",
        "job_url_substr": ["/emprego/"],
    },
    "emprego.sapo.pt": {
        "search_url": "https://emprego.sapo.pt/emprego/pesquisa/?q={keyword}",
        "job_url_substr": ["/emprego/"],
    },
    "landing.jobs": {
        "search_url": "https://landing.jobs/jobs?search={keyword}",
        "job_url_substr": ["/job/", "/jobs/"],
    },
    "www.infojobs.net": {
        "search_url": "https://www.infojobs.net/ofertas-trabajo/index.xhtml?keyword={keyword}",
        "job_url_substr": ["/oferta-trabajo/"],
    },
    "www.infoempleo.com": {
        "search_url": "https://www.infoempleo.com/trabajo/{keyword}/",
        "job_url_substr": ["/empleo/oferta/", "/trabajo/oferta/"],
    },
    "www.jobbsafari.se": {
        "search_url": "https://jobbsafari.se/lediga-jobb?q={keyword}",
        "job_url_substr": ["/jobb/"],
    },
    "www.jobup.ch": {
        "search_url": "https://www.jobup.ch/en/jobs/?term={keyword}&location={location}",
        "job_url_substr": ["/en/jobs/detail/"],
    },
    "www.jobscout24.ch": {
        "search_url": "https://www.jobscout24.ch/en/jobs/{keyword}?location={location}",
        "job_url_substr": ["/en/jobs/"],
    },
    "www.job-room.ch": {
        "search_url": "https://www.job-room.ch/home/job-search/results?query={keyword}",
        "job_url_substr": ["/stelleninserat/", "/job/"],
    },
    "www.reed.co.uk": {
        "search_url": "https://www.reed.co.uk/jobs/{keyword}-jobs?proximity=50&datecreatedoffset=3d",
        "job_url_substr": ["/jobs/"],
    },
    "www.totaljobs.com": {
        "search_url": "https://www.totaljobs.com/jobs/{keyword}?postedwithin=3",
        "job_url_substr": ["/job/"],
    },
    "eures.europa.eu": {
        "search_url": "https://eures.europa.eu/en/jobs?keywords={keyword}&page=1",
        "job_url_substr": ["/en/jobs/"],
    },
}


def load_sites(exclude_swiss_companies: bool = False) -> list[SiteConfig]:
    """
    Load all sites from the Excel file, merged with _OVERRIDES.

    exclude_swiss_companies: when True, Switzerland entries whose domain is
        NOT in _SWISS_JOB_BOARDS are skipped (they belong to the dedicated
        Swiss-companies scraper, not the general European boards scraper).
    """
    wb = openpyxl.load_workbook(_EXCEL_PATH)
    ws = wb.active
    sites: list[SiteConfig] = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        country, name, url, description = (row[i] if i < len(row) else "" for i in range(4))
        excel_status = str(row[4] if len(row) > 4 and row[4] else "").strip().lower()
        if not url or not str(url).startswith("http"):
            continue

        parsed   = urlparse(str(url))
        domain   = parsed.netloc
        dom_path = domain + parsed.path.rstrip("/")

        # Skip Switzerland company career pages when loading for the European
        # boards scraper — those are handled by scrape_swiss_companies().
        if exclude_swiss_companies:
            if str(country or "").strip().lower() == "switzerland" \
                    and domain not in _SWISS_JOB_BOARDS:
                continue

        # Domain+path key first (for shared-domain ATS like Ashby/Greenhouse),
        # then plain domain, then empty dict.
        overrides = _OVERRIDES.get(dom_path) or _OVERRIDES.get(domain, {})

        # Excel "Status" column lets the user toggle companies without touching
        # code. "Skip" in the spreadsheet marks the site inactive.
        # _OVERRIDES technical skips (login-walls, big pharma, dead domains)
        # always take precedence.
        scraper = overrides.get("scraper", "generic")
        if excel_status == "skip" and scraper == "generic":
            scraper = "skip"

        base_url   = str(url).rstrip("/")
        search_url = overrides.get("search_url", "")
        # Fallback: use the career-page URL as the listing URL when no explicit
        # search URL is configured (lets Playwright scrape static listing pages).
        if not search_url and scraper == "generic":
            search_url = base_url

        site = SiteConfig(
            country=str(country or ""),
            name=str(name or ""),
            base_url=base_url,
            description=str(description or ""),
            scraper=scraper,
            search_url=search_url,
            job_url_substr=overrides.get("job_url_substr", []),
            jobspy_country=overrides.get("jobspy_country", ""),
            keywords_override=overrides.get("keywords_override", []),
        )
        sites.append(site)

    return sites


def load_swiss_company_sites() -> list[SiteConfig]:
    """Return only Switzerland company career-page entries (not job-board aggregators)."""
    return [
        s for s in load_sites()
        if s.country.strip().lower() == "switzerland"
        and urlparse(s.base_url).netloc not in _SWISS_JOB_BOARDS
    ]
