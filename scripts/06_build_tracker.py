"""Step 6 — Build corpus_tracker.csv joining sampled + fetch + normalize + QA status.

Usage:
    .venv/bin/python scripts/06_build_tracker.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def main() -> None:
    sampled = pd.read_csv(config.INDEX_DIR / "sampled.csv", dtype=str).fillna("")
    qa = pd.read_csv(config.INDEX_DIR / "qa_report.csv", dtype=str).fillna("")

    sampled["xml_exists"] = sampled["pmcid"].apply(
        lambda p: (config.RAW_DIR / f"{p}.xml").exists() and (config.RAW_DIR / f"{p}.xml").stat().st_size > 500
    )
    sampled["md_exists"] = sampled["pmcid"].apply(
        lambda p: (config.NORMALIZED_DIR / f"{p}.md").exists()
    )

    merged = sampled.merge(qa, on="pmcid", how="left")

    keep = [
        "tier", "journal_name", "nlm_abbr", "pmid", "pmcid", "doi",
        "pub_date", "title", "cancer_domain", "study_type",
        "xml_exists", "md_exists",
        "passed", "journal_hits", "publisher_hits", "id_hits", "url_hits",
        "n_redactions", "md_length",
    ]
    keep = [c for c in keep if c in merged.columns]
    out = config.PROJECT_ROOT / "corpus_tracker.csv"
    merged[keep].sort_values(["tier", "journal_name", "pmcid"]).to_csv(out, index=False)

    print(f"Wrote {out}  ({len(merged)} rows)")
    print("\n=== Per-tier pipeline status ===")
    status = merged.groupby("tier").agg(
        sampled=("pmcid", "count"),
        xml_ok=("xml_exists", "sum"),
        md_ok=("md_exists", "sum"),
    )
    print(status.to_string())

    print("\n=== Per-journal pipeline status ===")
    status = merged.groupby(["tier", "journal_name"]).agg(
        sampled=("pmcid", "count"),
        xml_ok=("xml_exists", "sum"),
        md_ok=("md_exists", "sum"),
    )
    print(status.to_string())


if __name__ == "__main__":
    main()
