"""cv_extractor.py — Extract text and suggest search keywords from a CV (.docx or .pdf)."""
from __future__ import annotations
import logging
import re

logger = logging.getLogger(__name__)

# Terms that indicate a CV line is worth turning into a search keyword
_RELEVANT_TERMS = {
    "medicinal", "chemist", "chemistry", "synthesis", "synthetic",
    "pharmaceutical", "drug", "discovery", "organic", "computational",
    "cheminformatics", "docking", "rdkit", "knime", "scaffold",
    "heterocycle", "spirocycle", "lead", "optimis", "hit-to-lead",
    "biotech", "cro", "pharma", "molecule", "ligand",
    "scientist", "researcher", "principal", "senior", "project lead",
    "biology", "biochem", "assay", "structure", "design",
}


def extract_text(filepath: str) -> str:
    """Extract plain text from a .docx or .pdf file."""
    ext = filepath.rsplit(".", 1)[-1].lower()
    if ext == "docx":
        return _from_docx(filepath)
    if ext == "pdf":
        return _from_pdf(filepath)
    raise ValueError(f"Unsupported file type: .{ext}  (use .pdf or .docx)")


def _from_docx(path: str) -> str:
    try:
        import docx
    except ImportError:
        raise ImportError("python-docx not installed. Run: pip install python-docx")
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _from_pdf(path: str) -> str:
    # Try pypdf first (lightweight), fall back to pdfminer
    try:
        import pypdf
        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        pass
    try:
        from pdfminer.high_level import extract_text as _pe
        return _pe(path)
    except ImportError:
        raise ImportError(
            "pypdf not installed. Run: pip install pypdf"
        )


def suggest_keywords(text: str, max_suggestions: int = 12) -> list[str]:
    """
    Heuristically extract search-worthy phrases from CV text.
    Returns short lines (bullet points / headings) that contain
    chemistry/pharma terminology.
    """
    seen: set[str] = set()
    results: list[str] = []

    for line in text.splitlines():
        line = line.strip()
        # Skip blank, very short, or paragraph-length lines
        if len(line) < 12 or len(line) > 100:
            continue
        if not any(term in line.lower() for term in _RELEVANT_TERMS):
            continue
        # Strip leading bullet/dash characters
        clean = re.sub(r"^[\s•\-–—*•‣◦]+", "", line).strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            results.append(clean)
        if len(results) >= max_suggestions:
            break

    return results