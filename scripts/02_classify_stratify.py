"""Step 2 — Classify each enumerated paper by cancer domain + study type.

Uses MeSH headings (primary) and title/abstract keywords (fallback).
Writes corpus/index/classification.csv.

Usage:
    .venv/bin/python scripts/02_classify_stratify.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

DOMAIN_RULES = [
    ("pediatric",   ["child", "pediatric", "paediatric", "infant", "adolescent"],
                    ["Child", "Infant", "Adolescent", "Pediatrics"]),
    ("breast",      [r"\bbreast cancer\b", r"\bbreast carcinoma\b", r"\bbreast tumou?r\b"],
                    ["Breast Neoplasms"]),
    ("lung",        [r"\blung cancer\b", "non-small cell lung", "small cell lung", "nsclc", "sclc"],
                    ["Lung Neoplasms", "Carcinoma, Non-Small-Cell Lung", "Small Cell Lung Carcinoma",
                     "Carcinoma, Small Cell"]),
    ("hematologic", ["leukemia", "leukaemia", "lymphoma", "myeloma", "myelodysplastic",
                     "myeloproliferative", "hodgkin"],
                    ["Leukemia", "Lymphoma", "Multiple Myeloma", "Hematologic Neoplasms",
                     "Myelodysplastic Syndromes", "Myeloproliferative Disorders", "Hodgkin Disease",
                     "Lymphoma, Non-Hodgkin", "Leukemia, Myeloid, Acute", "Leukemia, Lymphocytic, Chronic, B-Cell",
                     "Precursor Cell Lymphoblastic Leukemia-Lymphoma"]),
    ("gi",          ["colorectal", "colon cancer", "rectal cancer", "gastric", "stomach cancer",
                     "pancreatic cancer", "esophageal", "oesophageal", "hepatocellular", "liver cancer",
                     "cholangiocarcinoma", "biliary"],
                    ["Colorectal Neoplasms", "Colonic Neoplasms", "Rectal Neoplasms", "Stomach Neoplasms",
                     "Pancreatic Neoplasms", "Esophageal Neoplasms", "Liver Neoplasms", "Biliary Tract Neoplasms",
                     "Carcinoma, Hepatocellular", "Cholangiocarcinoma", "Gastrointestinal Neoplasms"]),
    ("gu",          ["prostate cancer", "bladder cancer", "renal cell", "kidney cancer", "testicular"],
                    ["Prostatic Neoplasms", "Urinary Bladder Neoplasms", "Kidney Neoplasms",
                     "Carcinoma, Renal Cell", "Testicular Neoplasms", "Urologic Neoplasms"]),
    ("cns",         ["glioblastoma", "glioma", "brain cancer", "brain tumor", "brain tumour",
                     "medulloblastoma"],
                    ["Brain Neoplasms", "Glioma", "Glioblastoma", "Central Nervous System Neoplasms",
                     "Medulloblastoma", "Astrocytoma"]),
    ("gynecologic", ["ovarian cancer", "cervical cancer", "endometrial", "uterine"],
                    ["Ovarian Neoplasms", "Uterine Neoplasms", "Endometrial Neoplasms",
                     "Uterine Cervical Neoplasms", "Genital Neoplasms, Female"]),
    ("head_neck",   ["head and neck", "nasopharyng", "oropharyng", "oral cancer", "laryng"],
                    ["Head and Neck Neoplasms", "Nasopharyngeal Neoplasms", "Oropharyngeal Neoplasms",
                     "Mouth Neoplasms", "Laryngeal Neoplasms"]),
    ("sarcoma",     ["sarcoma", "osteosarcoma", "leiomyosarcoma"],
                    ["Sarcoma", "Osteosarcoma", "Leiomyosarcoma", "Soft Tissue Neoplasms"]),
    ("melanoma_skin", ["melanoma", "skin cancer", "cutaneous"],
                      ["Melanoma", "Skin Neoplasms"]),
]


def classify_domain(mesh: str, title: str, abstract: str) -> str:
    mesh_terms = {m.strip() for m in mesh.split(";")} if mesh else set()
    text = f"{title} {abstract}".lower()

    if any(m in mesh_terms for m in ["Child", "Infant", "Adolescent", "Pediatrics"]) \
            and any("Neoplasm" in m or "Leukemia" in m or "Sarcoma" in m for m in mesh_terms):
        return "pediatric"
    if any(kw in text for kw in ["childhood cancer", "pediatric cancer", "paediatric cancer"]):
        return "pediatric"

    for domain, kws, meshes in DOMAIN_RULES:
        if domain == "pediatric":
            continue
        if any(m in mesh_terms for m in meshes):
            return domain
        if any(re.search(kw, text) for kw in kws):
            return domain

    return "rare_nos"


STUDY_RULES_MESH = [
    ("meta",           ["Meta-Analysis as Topic", "Meta-Analysis", "Systematic Review",
                        "Systematic Reviews as Topic"]),
    ("rct_late",       ["Randomized Controlled Trial", "Clinical Trial, Phase III",
                        "Clinical Trial, Phase IV"]),
    ("trial_early",    ["Clinical Trial, Phase I", "Clinical Trial, Phase II", "Clinical Trial"]),
    ("observational",  ["Cohort Studies", "Case-Control Studies", "Cross-Sectional Studies",
                        "Retrospective Studies", "Observational Study"]),
]


STUDY_RULES_PT = [
    ("meta",         ["Meta-Analysis", "Systematic Review"]),
    ("rct_late",     ["Randomized Controlled Trial", "Clinical Trial, Phase III",
                      "Clinical Trial, Phase IV"]),
    ("trial_early",  ["Clinical Trial, Phase I", "Clinical Trial, Phase II",
                      "Clinical Trial, Phase I, II", "Clinical Trial, Phase II, III",
                      "Clinical Trial"]),
    ("observational", ["Observational Study"]),
]


PRECLIN_KW = [
    "mouse model", "murine model", "xenograft", "in vitro", "cell line",
    "organoid", "patient-derived xenograft", "pdx model",
    "crispr screen", "knockout mice", "transgenic mice", "zebrafish",
]

BIOMARKER_KW = [
    "biomarker", "prognostic marker", "predictive marker", "gene signature",
    "circulating tumor dna", "ctdna", "liquid biopsy", "immunohistochemistry",
    "tumor microenvironment", "mutational signature", "molecular classification",
    "transcriptomic", "proteomic", "methylation signature",
]

RWE_KW = [
    "real-world", "real world evidence", "claims data", "registry",
    "electronic health record", "population-based cohort", "national cancer database",
    "seer ",
]


def classify_study_type(pub_types: str, mesh: str, title: str, abstract: str) -> str:
    pt_set = {p.strip() for p in pub_types.split(";")} if pub_types else set()
    mesh_set = {m.strip() for m in mesh.split(";")} if mesh else set()
    text = f"{title} {abstract}".lower()

    for label, pts in STUDY_RULES_PT:
        if any(p in pt_set for p in pts):
            return label
    for label, mterms in STUDY_RULES_MESH:
        if any(m in mesh_set for m in mterms):
            return label

    if any(kw in text for kw in RWE_KW):
        return "real_world"

    has_preclinical = any(kw in text for kw in PRECLIN_KW)
    has_biomarker = any(kw in text for kw in BIOMARKER_KW)
    has_patient_sample = any(kw in text for kw in
                             ["patient samples", "tumor samples", "patient cohort",
                              "clinical samples", "patient tissue"])

    if has_biomarker and (has_patient_sample or "patients" in text):
        return "translational_biomarker"
    if has_preclinical:
        return "preclinical"
    if any(kw in text for kw in ["patients", "enrolled", "consecutive patients", "inclusion criteria"]):
        return "observational"

    return "unclassified"


def main() -> None:
    enum_path = config.INDEX_DIR / "enumeration.csv"
    df = pd.read_csv(enum_path, dtype=str).fillna("")
    print(f"Loaded {len(df)} rows from {enum_path}")

    df["cancer_domain"] = df.apply(
        lambda r: classify_domain(r["mesh"], r["title"], r["abstract"]), axis=1
    )
    df["study_type"] = df.apply(
        lambda r: classify_study_type(r["pub_types"], r["mesh"], r["title"], r["abstract"]),
        axis=1,
    )

    out = config.INDEX_DIR / "classification.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out}")

    print("\n=== Cancer domain distribution ===")
    print(df["cancer_domain"].value_counts().to_string())

    print("\n=== Study type distribution ===")
    print(df["study_type"].value_counts().to_string())

    print("\n=== Domain × Tier ===")
    print(pd.crosstab(df["cancer_domain"], df["tier"]).to_string())

    print("\n=== Study type × Tier ===")
    print(pd.crosstab(df["study_type"], df["tier"]).to_string())


if __name__ == "__main__":
    main()
