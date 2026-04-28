"""
main.py — Unified job scraper pipeline.

Sources (toggle in config.py):
  LinkedIn (jobspy)  — Europe-wide (distance column shows Basel proximity)
  jobs.ch scraper    — Switzerland-wide
  Exa semantic search— whole web, no domain restriction (finds company career pages)
  organic-chemistry.org — European chemistry listings

Run directly:   python main.py
Run scheduled:  python scheduler.py
"""
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from config import (
    EUROPEAN_COUNTRIES,
    EUROPEAN_LOCATION,
    JOB_PROFILE,
    JOB_TYPE,
    MAX_RESULTS_PER_KEYWORD,
    MIN_RELEVANCE_SCORE,
    OUTPUT_DIR,
    PREFILTER_EXCLUDED_LOCATIONS,
    PREFILTER_EXCLUDED_TITLE,
    PREFILTER_REQUIRED,
    SEARCH_KEYWORDS,
    SWISS_SEARCH_KEYWORDS,
    ENABLE_SWISS_COMPANIES,
)

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging to stdout (UTF-8, replace bad chars) and a rolling log file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_file = os.path.join(OUTPUT_DIR, "scraper.log")

    stdout_stream = open(
        sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(stdout_stream),
            logging.FileHandler(log_file, mode="a", encoding="utf-8"),
        ],
    )


def _prefilter(
    jobs: list[dict],
    required: list[str] | None = None,
    excluded: list[str] | None = None,
    excluded_locations: list[str] | None = None,
) -> list[dict]:
    """
    Fast keyword pre-filter — runs before the AI to cut API costs.
    Drops jobs that:
      - contain any excluded term in the title, OR
      - contain none of the required terms in title+description
        (only when required list is non-empty), OR
      - contain any excluded location term in the location field.
    Falls back to config values when override lists are None.
    """
    if required is None:
        required = PREFILTER_REQUIRED
    if excluded is None:
        excluded = PREFILTER_EXCLUDED_TITLE
    if excluded_locations is None:
        excluded_locations = PREFILTER_EXCLUDED_LOCATIONS

    kept = []
    for job in jobs:
        title    = job.get("title", "").lower()
        body     = title + " " + job.get("description", "").lower()
        location = job.get("location", "").lower()

        if any(excl.lower() in title for excl in excluded):
            continue

        if required and not any(req.lower() in body for req in required):
            continue

        if excluded_locations and any(excl.lower() in location for excl in excluded_locations):
            continue

        kept.append(job)
    return kept


def run_job_scraper(
    progress_callback=None,
    enable_ai_scoring: bool | None = None,
    keywords_override: list[str] | None = None,
    swiss_keywords_override: list[str] | None = None,
    location_override: str | None = None,
    countries_override: list[str] | None = None,
    prefilter_required_override: list[str] | None = None,
    prefilter_excluded_override: list[str] | None = None,
    prefilter_excluded_locations_override: list[str] | None = None,
    cancel_event=None,
) -> tuple[str, int] | None:
    """
    Full pipeline: scrape → AI filter → Excel export.
    Returns (output_path, new_job_count), or None if nothing was saved.

    progress_callback(pct, message) — optional, called throughout.
    keywords_override  — replaces config.SEARCH_KEYWORDS when provided.
    location_override  — overrides the Exa search location.
    countries_override — list of countries; enables the European scraper
                         with exactly those countries when provided.
    """
    from ai_filter import filter_jobs
    import application_tracker
    from excel_writer import export_jobs_json, load_previous_urls, write_excel

    from config import (
        ENABLE_ACADEMICPOSITIONS,
        ENABLE_AI_SCORING,
        ENABLE_EXA,
        ENABLE_EUROPEAN,
        ENABLE_INDEED,
        ENABLE_JOBSCH,
        ENABLE_LINKEDIN,
        ENABLE_ORGCHEM,
        EXA_API_KEY,
        HOURS_OLD,
    )

    if enable_ai_scoring is None:
        enable_ai_scoring = ENABLE_AI_SCORING

    keywords       = keywords_override       if keywords_override       is not None else SEARCH_KEYWORDS
    swiss_keywords = swiss_keywords_override if swiss_keywords_override is not None else SWISS_SEARCH_KEYWORDS
    exa_location   = location_override or "Switzerland"

    # European scraper: use countries_override when GUI provides it,
    # otherwise fall back to config flags.
    if countries_override is not None:
        run_european     = bool(countries_override)
        run_eu_countries = countries_override
    else:
        run_european     = ENABLE_EUROPEAN
        run_eu_countries = EUROPEAN_COUNTRIES
    # Swiss company scraping is always driven by ENABLE_SWISS_COMPANIES — never
    # implicitly triggered by the countries selector so it doesn't slow down
    # European-wide runs.
    run_swiss = ENABLE_SWISS_COMPANIES

    # Count how many sources will actually run so the GUI can show "2/5" etc.
    _total_sources = sum([
        bool(ENABLE_INDEED),
        bool(ENABLE_LINKEDIN),
        bool(ENABLE_JOBSCH and True),
        bool(ENABLE_EXA and EXA_API_KEY),
        bool(ENABLE_ORGCHEM),
        bool(ENABLE_ACADEMICPOSITIONS),
        bool(run_swiss),
        bool(run_european),
    ])
    _step = 0

    def _progress(pct: float, msg: str) -> None:
        logger.info("[%.0f%%] %s", pct, msg)
        if progress_callback:
            progress_callback(pct, msg)

    _run_start = time.time()
    _source_counts: dict[str, int] = {}
    _source_times:  dict[str, float] = {}

    logger.info("=" * 60)
    logger.info("Run started  %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("Keywords (global): %s", keywords)
    logger.info("Keywords (Swiss):  %s", swiss_keywords)
    logger.info("Location:          %s", exa_location)
    _progress(0, "Starting scrape…")

    raw_jobs: list[dict] = []
    _cancelled = False

    def _is_cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    # ------------------------------------------------------------------ #
    # Source 1 — Indeed
    # ------------------------------------------------------------------ #
    if ENABLE_INDEED and not _is_cancelled():
        _step += 1
        _t0 = time.time()
        _progress(2, f"[{_step}/{_total_sources}] Scraping Indeed…")
        from scrapers.indeed_scraper import scrape_indeed
        indeed_jobs = scrape_indeed(keywords)
        for j in indeed_jobs:
            j.setdefault("source", "Indeed")
        raw_jobs.extend(indeed_jobs)
        logger.info("Indeed:   %d jobs", len(indeed_jobs))
        _progress(4, f"[{_step}/{_total_sources}] Indeed: {len(indeed_jobs)} jobs found")
        _source_counts["Indeed"] = len(indeed_jobs)
        _source_times["Indeed"]  = time.time() - _t0

    # ------------------------------------------------------------------ #
    # Source 2 — LinkedIn (Europe-wide; distance column shows Basel proximity)
    # ------------------------------------------------------------------ #
    if ENABLE_LINKEDIN and not _is_cancelled():
        _step += 1
        _t0 = time.time()
        _progress(5, f"[{_step}/{_total_sources}] Scraping LinkedIn…")
        from scrapers.linkedin_scraper import scrape_linkedin
        linkedin_jobs = scrape_linkedin(keywords)
        raw_jobs.extend(linkedin_jobs)
        logger.info("LinkedIn: %d jobs", len(linkedin_jobs))
        _progress(15, f"[{_step}/{_total_sources}] LinkedIn: {len(linkedin_jobs)} jobs found")
        _source_counts["LinkedIn"] = len(linkedin_jobs)
        _source_times["LinkedIn"]  = time.time() - _t0

    # ------------------------------------------------------------------ #
    # Source 3 — jobs.ch (Switzerland-wide, no location filter)
    # ------------------------------------------------------------------ #
    if ENABLE_JOBSCH and not _is_cancelled():
        _step += 1
        _t0 = time.time()
        _progress(16, f"[{_step}/{_total_sources}] Scraping jobs.ch…")
        from scrapers.jobsch_scraper import scrape_jobsch
        jobsch_jobs = scrape_jobsch(swiss_keywords)
        raw_jobs.extend(jobsch_jobs)
        logger.info("jobs.ch:  %d jobs", len(jobsch_jobs))
        _progress(27, f"[{_step}/{_total_sources}] jobs.ch: {len(jobsch_jobs)} jobs found")
        _source_counts["jobs.ch"] = len(jobsch_jobs)
        _source_times["jobs.ch"]  = time.time() - _t0

    # ------------------------------------------------------------------ #
    # Source 4 — Exa semantic search (no domain restriction)
    # ------------------------------------------------------------------ #
    if ENABLE_EXA and not _is_cancelled():
        if not EXA_API_KEY:
            logger.warning("EXA_API_KEY not set — skipping Exa source.")
        else:
            _step += 1
            _t0 = time.time()
            _progress(28, f"[{_step}/{_total_sources}] Searching via Exa…")
            sys.path.insert(0, str(Path(__file__).parent / "exa_search"))
            from exa_scraper import scrape_exa  # type: ignore

            exa_jobs = scrape_exa(
                keywords=keywords,
                location=exa_location,
                exa_api_key=EXA_API_KEY,
                job_type=JOB_TYPE,
                results_per_keyword=MAX_RESULTS_PER_KEYWORD,
                hours_old=HOURS_OLD * 10,
                domains=None,
                search_type="neural",
                job_profile=JOB_PROFILE,
            )
            raw_jobs.extend(exa_jobs)
            logger.info("Exa:      %d jobs", len(exa_jobs))
            _progress(38, f"[{_step}/{_total_sources}] Exa: {len(exa_jobs)} jobs found")
            _source_counts["Exa"] = len(exa_jobs)
            _source_times["Exa"]  = time.time() - _t0

    # ------------------------------------------------------------------ #
    # Source 5 — organic-chemistry.org (European chemistry listings)
    # ------------------------------------------------------------------ #
    if ENABLE_ORGCHEM and not _is_cancelled():
        _step += 1
        _t0 = time.time()
        _progress(39, f"[{_step}/{_total_sources}] Scraping organic-chemistry.org…")
        from scrapers.orgchem_scraper import scrape_orgchem
        orgchem_jobs = scrape_orgchem()
        raw_jobs.extend(orgchem_jobs)
        logger.info("organic-chemistry.org: %d jobs", len(orgchem_jobs))
        _progress(42, f"[{_step}/{_total_sources}] organic-chemistry.org: {len(orgchem_jobs)} jobs found")
        _source_counts["organic-chemistry.org"] = len(orgchem_jobs)
        _source_times["organic-chemistry.org"]  = time.time() - _t0

    # ------------------------------------------------------------------ #
    # Source 6 — Academic Positions (academicpositions.com)
    # ------------------------------------------------------------------ #
    if ENABLE_ACADEMICPOSITIONS and not _is_cancelled():
        _step += 1
        _t0 = time.time()
        _progress(43, f"[{_step}/{_total_sources}] Scraping academicpositions.com…")
        from scrapers.academicpositions_scraper import scrape_academicpositions
        ap_jobs = scrape_academicpositions(
            keywords=keywords,
            max_results=MAX_RESULTS_PER_KEYWORD,
        )
        raw_jobs.extend(ap_jobs)
        logger.info("academicpositions.com: %d jobs", len(ap_jobs))
        _progress(46, f"[{_step}/{_total_sources}] academicpositions.com: {len(ap_jobs)} jobs found")
        _source_counts["academicpositions.com"] = len(ap_jobs)
        _source_times["academicpositions.com"]  = time.time() - _t0

    # ------------------------------------------------------------------ #
    # Source 7 — Swiss company career pages
    # ------------------------------------------------------------------ #
    if run_swiss and not _is_cancelled():
        _step += 1
        _t0 = time.time()
        _progress(43, f"[{_step}/{_total_sources}] Scraping Swiss company career pages…")
        from scrapers.european import scrape_swiss_companies

        def _swiss_progress(frac: float, msg: str) -> None:
            _progress(43 + frac * 14, f"[{_step}/{_total_sources}] {msg}")  # 43 % → 57 %

        swiss_jobs = scrape_swiss_companies(
            keywords=swiss_keywords,
            location=exa_location,
            progress_callback=_swiss_progress,
        )
        raw_jobs.extend(swiss_jobs)
        logger.info("Swiss companies: %d jobs", len(swiss_jobs))
        _progress(57, f"[{_step}/{_total_sources}] Swiss companies: {len(swiss_jobs)} jobs found")
        _source_counts["Swiss Companies"] = len(swiss_jobs)
        _source_times["Swiss Companies"]  = time.time() - _t0

    # ------------------------------------------------------------------ #
    # Source 7 — European multi-country job boards
    # ------------------------------------------------------------------ #
    if run_european and not _is_cancelled():
        _step += 1
        _t0 = time.time()
        _progress(57, f"[{_step}/{_total_sources}] Scraping European job boards…")
        from scrapers.european import scrape_european_sites

        def _eu_progress(frac: float, msg: str) -> None:
            _progress(57 + frac * 7, f"[{_step}/{_total_sources}] {msg}")  # 57 % → 64 %

        eu_jobs = scrape_european_sites(
            keywords=keywords,
            location=exa_location,
            countries=run_eu_countries or None,
            progress_callback=_eu_progress,
        )
        raw_jobs.extend(eu_jobs)
        logger.info("European: %d jobs", len(eu_jobs))
        _progress(64, f"[{_step}/{_total_sources}] European: {len(eu_jobs)} jobs found")
        _source_counts["European boards"] = len(eu_jobs)
        _source_times["European boards"]  = time.time() - _t0

    if _is_cancelled():
        logger.info("Run cancelled — exporting %d collected jobs", len(raw_jobs))

    # ------------------------------------------------------------------ #
    # Deduplicate — two passes:
    #   1. By URL (catches exact same link from multiple keyword searches)
    #   2. By (title, company) (catches same job with different tracking URLs)
    # ------------------------------------------------------------------ #
    seen_urls: set = set()
    url_deduped: list[dict] = []
    for job in raw_jobs:
        url = job.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(job)

    seen_tc: set = set()
    unique_jobs: list[dict] = []
    for job in url_deduped:
        tc = (job.get("title", "").lower().strip(), job.get("company", "").lower().strip())
        if tc[0] and tc in seen_tc:
            continue
        seen_tc.add(tc)
        unique_jobs.append(job)

    dropped_dupes = len(raw_jobs) - len(unique_jobs)
    raw_jobs = unique_jobs
    logger.info("Total unique jobs: %d (%d duplicates removed)", len(raw_jobs), dropped_dupes)

    if not raw_jobs:
        logger.warning("No jobs scraped. Check your keywords, location, or network.")
        return None

    # ------------------------------------------------------------------ #
    # Keyword pre-filter (cheap, no API calls)
    # ------------------------------------------------------------------ #
    _progress(52, f"Filtering {len(raw_jobs)} unique jobs…")
    prefiltered = _prefilter(
        raw_jobs,
        required=prefilter_required_override,
        excluded=prefilter_excluded_override,
        excluded_locations=prefilter_excluded_locations_override,
    )
    logger.info(
        "Pre-filter: %d kept, %d dropped",
        len(prefiltered), len(raw_jobs) - len(prefiltered),
    )
    _progress(54, f"{len(prefiltered)} jobs passed pre-filter")

    if not prefiltered:
        logger.warning("All jobs dropped by pre-filter. Widen PREFILTER_REQUIRED in config.py.")
        return None

    # ------------------------------------------------------------------ #
    # AI scoring (optional — set ENABLE_AI_SCORING = False in config.py
    # to skip and export pre-filtered jobs directly)
    # ------------------------------------------------------------------ #
    if enable_ai_scoring:
        def _ai_progress(current: int, total_jobs: int) -> None:
            pct = 54 + (current / total_jobs) * 41   # 54% → 95%
            _progress(pct, f"Scoring job {current}/{total_jobs}…")

        scored_jobs = filter_jobs(prefiltered, progress_callback=_ai_progress)
        to_write = scored_jobs if scored_jobs else prefiltered
    else:
        logger.info("AI scoring disabled — exporting pre-filtered jobs without scores.")
        to_write = prefiltered

    # ------------------------------------------------------------------ #
    # Export to Excel (scored sheet + raw all-jobs sheet)
    # ------------------------------------------------------------------ #
    _progress(96, "Writing Excel file…")
    previous_urls = load_previous_urls(OUTPUT_DIR)
    applications  = application_tracker.load(OUTPUT_DIR)
    output_path, new_count = write_excel(
        to_write, all_jobs=raw_jobs,
        previous_urls=previous_urls, applications=applications,
    )
    export_jobs_json(to_write, output_path.replace(".xlsx", ".json"))

    if enable_ai_scoring:
        passed = sum(1 for j in to_write if j.get("relevance_score", 0) >= MIN_RELEVANCE_SCORE)
        logger.info("Done. %d above threshold, %d total written to Excel", passed, len(to_write))
    else:
        logger.info("Done. %d jobs written to Excel (unscored)", len(to_write))
    logger.info("New jobs (not seen in previous run): %d", new_count)
    _progress(100, f"Done! {new_count} new jobs found.")
    logger.info("Output: %s", output_path)
    logger.info("=" * 60)

    _run_time    = time.time() - _run_start
    _slowest_src = max(_source_times, key=_source_times.get) if _source_times else None
    _n_unique    = len(raw_jobs)   # raw_jobs is the deduped list at this point

    stats = {
        "sources":            [(n, _source_counts[n], _source_times[n]) for n in _source_counts],
        "total_scraped":      sum(_source_counts.values()),
        "duplicates_removed": dropped_dupes,
        "unique_jobs":        _n_unique,
        "dropped_by_filter":  _n_unique - len(prefiltered),
        "passed_to_export":   len(to_write),
        "new_count":          new_count,
        "run_time_s":         _run_time,
        "slowest_source":     _slowest_src,
        "slowest_source_time_s": _source_times.get(_slowest_src, 0) if _slowest_src else 0,
    }

    return output_path, new_count, stats


if __name__ == "__main__":
    setup_logging()
    run_job_scraper()