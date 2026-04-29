"""Strip journal / publisher / affiliation identifiers from blinded text.

Returns (stripped_text, list_of_redactions). Any redaction that matches a
journal/publisher name is logged — 10% random manual QA uses this log.
"""

from __future__ import annotations

import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# Curated lists ---------------------------------------------------------------

ONCOLOGY_JOURNALS = [
    # Distinctive multi-word only. Dropped: "Cancer Cell" / "Cancer Research" / "Cancer Reports" /
    # "Cancer Medicine" / "Clinical Cancer Research" / "Cancer Biomarkers" — these collide with
    # normal medical prose ("cancer cell lines", "clinical cancer research", etc.). Journal-name
    # leakage from self-citation is rare; the strip list is defense-in-depth only.
    "Nature Cancer", "Nat Cancer",
    "Nature Medicine", "Nat Med",
    "Journal of Clinical Oncology", "J Clin Oncol",
    "Lancet Oncology", "Lancet Oncol", "The Lancet. Oncology",
    "JAMA Oncology", "JAMA Oncol",
    "Cancer Discovery", "Cancer Discov",
    "New England Journal of Medicine", "N Engl J Med",
    "The Lancet",
    "Nature Communications", "Nat Commun",
    "ESMO Open",
    "JCO Precision Oncology", "JCO Precis Oncol",
    "Annals of Oncology", "Ann Oncol",
    "Journal of the National Cancer Institute", "J Natl Cancer Inst",
    "Journal for ImmunoTherapy of Cancer", "J Immunother Cancer",
    "Molecular Cancer",
    "Journal of Hematology & Oncology", "J Hematol Oncol",
    "Cancer Immunology Research", "Cancer Immunol Res",
    "Cancers (Basel)",
    "Frontiers in Oncology", "Front Oncol",
    "European Journal of Cancer", "Eur J Cancer",
    "The Oncologist",
    "International Journal of Cancer", "Int J Cancer",
    "British Journal of Cancer", "Br J Cancer",
    "BMC Cancer",
    "Cancer Research Communications", "Cancer Res Commun",
    "Molecular Oncology", "Mol Oncol",
    "Journal of Thoracic Oncology", "J Thorac Oncol",
    "Neuro-Oncology", "Neuro Oncol",
    "Gynecologic Oncology", "Gynecol Oncol",
    "European Urology", "Eur Urol",
    "Hematological Oncology", "Hematol Oncol",
    "Current Oncology", "Curr Oncol",
    "Oncology Letters", "Oncol Lett",
    "World Journal of Clinical Oncology", "World J Clin Oncol",
    "Oncology Reports", "Oncol Rep",
    "Tumour Biology", "Tumour Biol",
    "Onco Targets and Therapy", "Onco Targets Ther",
    "Science Translational Medicine", "Sci Transl Med",
    "Cell Reports Medicine", "Cell Rep Med",
]

PUBLISHERS = [
    "Elsevier", "Wiley", "Springer Nature", "Nature Publishing Group",
    "BMJ Publishing Group",
    "American Association for Cancer Research", "AACR",
    "American Society of Clinical Oncology", "ASCO",
    "American Medical Association",
    "MDPI",
    "Frontiers Media",
    "Spandidos Publications",
    "Oxford University Press", "Oxford Academic",
    "Taylor & Francis",
    "Wolters Kluwer",
    "Dove Medical Press",
]

# Patterns --------------------------------------------------------------------

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)
PMID_RE = re.compile(r"\bPMID[:\s]*\d{4,9}\b", re.IGNORECASE)
PMCID_RE = re.compile(r"\bPMC\d{5,9}\b", re.IGNORECASE)
ISSN_RE = re.compile(r"\bISSN[:\s]*\d{4}-\d{3}[\dXx]\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
DATE_HISTORY_RE = re.compile(
    r"\b(Received|Revised|Accepted|Published online|Published)\s*:?\s*[^\n;,.]*?\d{4}",
    re.IGNORECASE,
)
FUNDING_LINE_RE = re.compile(
    r"^\s*(Funding|Funded by|Acknowledg[e]?ments?|Financial [Ss]upport|Conflicts? of [Ii]nterest|Disclosures?)\b.*$",
    re.MULTILINE,
)


def _word_boundary(token: str) -> str:
    esc = re.escape(token)
    return rf"(?<![\w-]){esc}(?![\w-])"


_JOURNAL_RE = re.compile(
    "|".join(_word_boundary(j) for j in sorted(ONCOLOGY_JOURNALS, key=len, reverse=True)),
    re.IGNORECASE,
)

_PUBLISHER_RE = re.compile(
    "|".join(_word_boundary(p) for p in sorted(PUBLISHERS, key=len, reverse=True)),
    re.IGNORECASE,
)

REDACT_TOKEN = "[REDACTED]"


def strip_identifiers(text: str) -> tuple[str, list[str]]:
    """Strip journal/publisher/affiliation identifiers; return (text, redactions)."""
    redactions: list[str] = []

    def _sub(pattern: re.Pattern, label: str, s: str) -> str:
        def repl(m: re.Match) -> str:
            redactions.append(f"{label}:{m.group(0)}")
            return REDACT_TOKEN
        return pattern.sub(repl, s)

    text = _sub(_JOURNAL_RE, "journal", text)
    text = _sub(_PUBLISHER_RE, "publisher", text)
    text = _sub(DOI_RE, "doi", text)
    text = _sub(PMID_RE, "pmid", text)
    text = _sub(PMCID_RE, "pmcid", text)
    text = _sub(ISSN_RE, "issn", text)
    text = _sub(URL_RE, "url", text)
    text = _sub(DATE_HISTORY_RE, "date_history", text)
    text = FUNDING_LINE_RE.sub("", text)

    return text, redactions
