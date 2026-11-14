"""Project configuration: journals, quotas, dates. NCBI_EMAIL is read from the environment."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"
INDEX_DIR = CORPUS_DIR / "index"
RAW_DIR = CORPUS_DIR / "raw"
NORMALIZED_DIR = CORPUS_DIR / "normalized"

DATE_FROM = "2026/02/01"
DATE_TO = "2026/04/18"

NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")
NCBI_TOOL = "llm_publication_audit"
NCBI_API_KEY = None

RANDOM_SEED = 42

EXCLUDE_PT = [
    "Editorial", "Letter", "Comment", "News", "Review", "Case Reports",
    "Published Erratum", "Retraction of Publication", "Retracted Publication",
]

JOURNALS = [
    {"tier": 1, "name": "Nature Cancer",          "nlm": "Nat Cancer",         "quota": 11, "restrict_cancer": False},
    {"tier": 1, "name": "Nature Medicine",        "nlm": "Nat Med",            "quota": 13, "restrict_cancer": True},
    {"tier": 1, "name": "JCO",                    "nlm": "J Clin Oncol",       "quota": 29, "restrict_cancer": False},
    {"tier": 1, "name": "JAMA Oncology",          "nlm": "JAMA Oncol",         "quota": 12, "restrict_cancer": False},
    {"tier": 2, "name": "Nature Communications",  "nlm": "Nat Commun",         "quota": 45, "restrict_cancer": True},
    {"tier": 2, "name": "Cancer Research",        "nlm": "Cancer Res",         "quota": 20, "restrict_cancer": False},
    {"tier": 2, "name": "Clinical Cancer Research","nlm": "Clin Cancer Res",   "quota": 25, "restrict_cancer": False},
    {"tier": 2, "name": "ESMO Open",              "nlm": "ESMO Open",          "quota": 20, "restrict_cancer": False},
    {"tier": 2, "name": "JCO Precision Oncology", "nlm": "JCO Precis Oncol",   "quota": 10, "restrict_cancer": False},
    {"tier": 3, "name": "Cancers",                "nlm": "Cancers (Basel)",    "quota": 85, "restrict_cancer": False},
    {"tier": 3, "name": "Frontiers in Oncology",  "nlm": "Front Oncol",        "quota": 100,"restrict_cancer": False},
    {"tier": 4, "name": "Oncology Letters",       "nlm": "Oncol Lett",         "quota": 65, "restrict_cancer": False},
    {"tier": 4, "name": "Current Oncology",       "nlm": "Curr Oncol",         "quota": 35, "restrict_cancer": False},
    {"tier": 4, "name": "Cancer Reports",         "nlm": "Cancer Rep (Hoboken)","quota": 30,"restrict_cancer": False},
]

TARGET_N = sum(j["quota"] for j in JOURNALS)
assert TARGET_N == 500, f"quotas sum to {TARGET_N}, expected 500"


def pubmed_query(nlm_abbr: str, restrict_cancer: bool = False) -> str:
    q = f'"{nlm_abbr}"[Journal] AND "Journal Article"[PT]'
    excl = " OR ".join(f'"{pt}"[PT]' for pt in EXCLUDE_PT)
    q += f" NOT ({excl})"
    q += ' AND "pubmed pmc open access"[Filter]'
    if restrict_cancer:
        q += " AND (neoplasms[MeSH] OR cancer[Title/Abstract] OR tumor[Title/Abstract] OR oncolog*[Title/Abstract])"
    return q
