"""
output/export_portals_yml.py — Export Swiss company career pages to portals.yml
for the career-ops-plugin watchlist.

Reads European_Job_Search_Websites.xlsx, filters to Switzerland company entries
(skipping job-board aggregators), auto-detects the ATS platform from each URL,
and writes a portals.yml file ready to drop into the career-ops-plugin's
config/ directory.

Usage:
    python output/export_portals_yml.py
    python output/export_portals_yml.py --output ../career-ops-plugin/config/portals.yml
    python output/export_portals_yml.py --all-countries   # include European boards too
"""
from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

import openpyxl

_EXCEL_PATH = Path(__file__).parent.parent / "European_Job_Search_Websites.xlsx"
_DEFAULT_OUT = Path(__file__).parent.parent / "outputs" / "portals.yml"

# Job-board aggregators — not company career pages, skip for career-ops
_JOB_BOARDS = frozenset({
    "www.jobup.ch", "www.jobscout24.ch", "www.job-room.ch",
    "fr.indeed.com", "de.indeed.com", "nl.indeed.com", "ie.indeed.com",
    "it.indeed.com", "es.indeed.com", "se.indeed.com", "uk.indeed.com",
    "www.glassdoor.com", "www.linkedin.com",
    "www.stepstone.de", "www.stepstone.at", "www.stepstone.be",
    "www.karriere.at", "www.jobindex.dk", "www.workindenmark.dk",
    "duunitori.fi", "www.irishjobs.ie", "www.jobs.ie",
    "www.infojobs.it", "www.monster.it", "www.nationalevacaturebank.nl",
    "www.finn.no", "www.jobbnorge.no", "www.pracuj.pl", "nofluffjobs.com",
    "www.net-empregos.com", "emprego.sapo.pt", "landing.jobs",
    "www.infojobs.net", "www.infoempleo.com", "www.jobbsafari.se",
    "www.reed.co.uk", "www.totaljobs.com", "eures.europa.eu",
})


def detect_ats(url: str) -> tuple[str, str]:
    """
    Return (ats_type, slug) inferred from a careers page URL.

    ats_type is one of: greenhouse, lever, ashby, smartrecruiters,
                        workday, personio, cornerstone, generic
    slug is the company identifier used in ATS API/search URLs.
    For generic sites the slug is left empty — career-ops falls back
    to a plain web search using the company name.
    """
    parsed = urlparse(url.lower())
    host   = parsed.netloc
    path   = parsed.path.strip("/")
    first  = path.split("/")[0] if path else ""

    if host in ("job-boards.greenhouse.io", "boards.greenhouse.io"):
        return "greenhouse", first

    if host == "jobs.lever.co":
        return "lever", first

    if host == "jobs.ashbyhq.com":
        return "ashby", first

    if host == "jobs.smartrecruiters.com":
        return "smartrecruiters", first

    if host.endswith(".myworkdayjobs.com"):
        return "workday", host.split(".")[0]

    if ".jobs.personio.com" in host or host.endswith(".personio.de"):
        return "personio", host.split(".")[0]

    if host.endswith(".csod.com"):
        return "cornerstone", host.split(".")[0]

    return "generic", ""


def _yaml_str(s: str) -> str:
    """Quote a string for YAML if it contains special characters."""
    if any(c in s for c in (": ", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|", ">", "'")):
        return f'"{s}"'
    return s


def export(excel_path: Path, output_path: Path, all_countries: bool = False) -> None:
    wb = openpyxl.load_workbook(excel_path, read_only=True)
    ws = wb.active

    entries: list[dict] = []
    skipped_boards = 0
    skipped_disabled = 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        country     = str(row[0] or "").strip()
        name        = str(row[1] or "").strip()
        url         = str(row[2] or "").strip()
        status      = str(row[4] or "Active").strip().lower() if len(row) > 4 else "active"

        if not url.startswith("http") or not name:
            continue

        parsed = urlparse(url)
        host   = parsed.netloc.lower()

        # Skip generic job boards — career-ops scan is for company career pages
        if host in _JOB_BOARDS:
            skipped_boards += 1
            continue

        # Unless --all-countries, only include Switzerland company pages
        if not all_countries and country.lower() != "switzerland":
            continue

        ats_type, slug = detect_ats(url)
        enabled = status != "skip"

        if not enabled:
            skipped_disabled += 1

        entries.append({
            "name":        name,
            "country":     country,
            "ats":         ats_type,
            "slug":        slug,
            "careers_url": url,
            "enabled":     enabled,
        })

    wb.close()

    # Sort: enabled first, then alphabetical by name
    entries.sort(key=lambda e: (not e["enabled"], e["name"].lower()))

    # Count by ATS type for the header comment
    ats_counts: dict[str, int] = {}
    for e in entries:
        ats_counts[e["ats"]] = ats_counts.get(e["ats"], 0) + 1

    ats_summary = ", ".join(f"{v} {k}" for k, v in sorted(ats_counts.items()))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# portals.yml — Company career-page watchlist for career-ops-plugin",
        "# Generated from European_Job_Search_Websites.xlsx by export_portals_yml.py",
        "#",
        f"# {len(entries)} companies  ({ats_summary})",
        f"# {skipped_disabled} disabled (Status=Skip in Excel)",
        f"# {skipped_boards} job-board aggregators excluded",
        "#",
        "# ATS types: greenhouse | lever | ashby | smartrecruiters |",
        "#            workday | personio | cornerstone | generic",
        "# For 'generic' entries career-ops uses a plain web search with",
        "# the company name — no slug needed.",
        "",
    ]

    prev_country = None
    for e in entries:
        # Country group comment
        if e["country"] != prev_country:
            if prev_country is not None:
                lines.append("")
            lines.append(f"# ── {e['country']} {'─' * max(0, 50 - len(e['country']))}")
            prev_country = e["country"]

        lines.append(f"- name:        {_yaml_str(e['name'])}")
        lines.append(f"  ats:         {e['ats']}")
        if e["slug"]:
            lines.append(f"  slug:        {e['slug']}")
        lines.append(f"  careers_url: {e['careers_url']}")
        lines.append(f"  enabled:     {'true' if e['enabled'] else 'false'}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    enabled = sum(1 for e in entries if e["enabled"])
    print(f"Written: {output_path}")
    print(f"  {len(entries)} companies total — {enabled} enabled, {len(entries)-enabled} disabled")
    print(f"  ATS breakdown: {ats_summary}")
    print(f"  {skipped_boards} job-board aggregators excluded")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export company watchlist to portals.yml")
    parser.add_argument("--output",        default=str(_DEFAULT_OUT), help="Output path for portals.yml")
    parser.add_argument("--excel",         default=str(_EXCEL_PATH),  help="Path to the Excel file")
    parser.add_argument("--all-countries", action="store_true",        help="Include all countries, not just Switzerland")
    args = parser.parse_args()

    export(Path(args.excel), Path(args.output), all_countries=args.all_countries)


if __name__ == "__main__":
    main()
