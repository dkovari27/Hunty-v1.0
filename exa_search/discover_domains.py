"""
exa_search/discover_domains.py — Discover biotech/pharma career page domains via Exa.

Runs a set of drug-discovery job queries with no domain restriction, collects all
returned URLs, extracts unique root domains, and prints them ranked by frequency.
You then copy the relevant ones into EXA_DOMAINS in config_exa.py.

Run:
    cd exa_search && python discover_domains.py
 or
    python exa_search/discover_domains.py
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", encoding="utf-8-sig")

EXA_API_KEY = os.getenv("EXA_API_KEY", "")

# Discovery queries — written to surface actual job posting pages at biotech companies
DISCOVERY_QUERIES = [
    "We are hiring a medicinal chemist in Switzerland. Apply now. Drug discovery biotech CRO.",
    "We are hiring a synthetic chemist in Basel. Pharmaceutical biotech vacancy. Full-time.",
    "We are hiring a drug discovery scientist in Europe. Apply now. Small molecule lead optimisation.",
    "We are hiring a cheminformatics scientist in Switzerland UK Europe. Apply now. KNIME RDKit docking.",
    "We are hiring a life sciences consultant with chemistry background in Europe. Apply now.",
    "We are hiring a computational chemist at a biotech in Europe. Apply now. Virtual library design.",
    "Job opening medicinal chemistry project lead Switzerland. Apply now. CRO pharma biotech.",
    "Career opportunity hit-to-lead scientist Europe Switzerland UK. Apply now.",
]

# Domains already in EXA_DOMAINS — filter these out of the results
ALREADY_KNOWN = {
    "roche.com", "novartis.com", "lonza.com", "idorsia.com", "basilea.com", "bachem.com",
    "molecular-partners.com", "adctherapeutics.com", "numab.com", "addextherapeutics.com",
    "ridgelinediscovery.com", "spirochem.com", "synphabase.ch",
    "evotec.com", "charles-river.com", "analyticon-discovery.com",
    "domain-therapeutics.com", "selvita.com",
    "isomorphiclabs.com", "exscientia.ai", "chemify.io", "benevolent.ai",
    "heptares.com", "ensemble.bio",
    "mckinsey.com", "zs.com", "iqvia.com", "l-e-k.com", "simon-kucher.com", "lcp.com",
    # job boards / noise
    "linkedin.com", "jobs.ch", "jobup.ch", "stepstone.de", "stepstone.at",
    "reed.co.uk", "totaljobs.com", "glassdoor.com", "indeed.com",
    "swissbiotech.org", "eures.europa.eu", "biospace.com",
}

# Known noise domains to skip even if returned
NOISE_DOMAINS = {
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "youtube.com",
    "wikipedia.org", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov",
    "researchgate.net", "semanticscholar.org", "nature.com", "science.org",
    "biorxiv.org", "chemrxiv.org", "doi.org", "nih.gov",
    "google.com", "bing.com", "yahoo.com",
}


def _root_domain(url: str) -> str:
    """Extract root domain (e.g. 'careers.roche.com' → 'roche.com')."""
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        parts = host.split(".")
        # Keep last two parts for most domains, three for .co.uk / .com.au etc.
        if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "gov", "net"):
            return ".".join(parts[-3:])
        return ".".join(parts[-2:]) if len(parts) >= 2 else host
    except Exception:
        return ""


def discover(results_per_query: int = 20) -> None:
    if not EXA_API_KEY:
        print("ERROR: EXA_API_KEY not set in .env")
        return

    try:
        from exa_py import Exa
    except ImportError:
        print("ERROR: exa-py not installed — run: pip install exa-py")
        return

    client = Exa(api_key=EXA_API_KEY)
    domain_counter: Counter = Counter()
    domain_to_urls: dict[str, list[str]] = {}

    print(f"Running {len(DISCOVERY_QUERIES)} discovery queries ({results_per_query} results each)...\n")

    for query in DISCOVERY_QUERIES:
        print(f"  Query: {query[:80]}...")
        try:
            response = client.search_and_contents(
                query=query,
                type="neural",
                num_results=results_per_query,
                text=False,   # no full text needed — just URLs
            )
        except Exception as exc:
            print(f"    ERROR: {exc}")
            continue

        for result in response.results:
            url = result.url or ""
            if not url:
                continue
            domain = _root_domain(url)
            if not domain:
                continue
            if domain in NOISE_DOMAINS:
                continue
            domain_counter[domain] += 1
            domain_to_urls.setdefault(domain, []).append(url)

    print("\n" + "=" * 70)
    print("DISCOVERED DOMAINS (sorted by frequency)")
    print("Domains already in EXA_DOMAINS are marked [known]")
    print("=" * 70)

    new_domains = []
    for domain, count in domain_counter.most_common():
        known = "[known]" if domain in ALREADY_KNOWN else "[NEW]  "
        sample_url = domain_to_urls[domain][0]
        print(f"  {known}  {count:2d}x  {domain}")
        print(f"           sample: {sample_url}")
        if domain not in ALREADY_KNOWN:
            new_domains.append(domain)

    print("\n" + "=" * 70)
    print(f"NEW domains not yet in EXA_DOMAINS ({len(new_domains)} total):")
    print("=" * 70)
    for d in new_domains:
        print(f'    "{d}",')

    print("\nCopy the relevant lines above into EXA_DOMAINS in exa_search/config_exa.py")


if __name__ == "__main__":
    discover(results_per_query=25)
