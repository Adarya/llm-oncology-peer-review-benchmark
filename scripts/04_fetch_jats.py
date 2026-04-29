"""Step 4 — Fetch JATS XML for all sampled PMCIDs.

Reads corpus/index/sampled.csv; writes corpus/raw/<PMCID>.xml.
Skips files that already exist. Records failures in corpus/index/fetch_errors.csv.

Usage:
    .venv/bin/python scripts/04_fetch_jats.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
from Bio import Entrez
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

Entrez.email = config.NCBI_EMAIL
Entrez.tool = config.NCBI_TOOL
if config.NCBI_API_KEY:
    Entrez.api_key = config.NCBI_API_KEY

SLEEP = 0.34 if not config.NCBI_API_KEY else 0.11


def fetch_one(pmcid: str) -> bytes:
    pmcid_num = pmcid.replace("PMC", "")
    handle = Entrez.efetch(db="pmc", id=pmcid_num, rettype="full", retmode="xml")
    data = handle.read()
    handle.close()
    return data if isinstance(data, bytes) else data.encode("utf-8")


def main() -> None:
    sampled = pd.read_csv(config.INDEX_DIR / "sampled.csv", dtype=str).fillna("")
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    errors: list[dict] = []
    ok = 0
    skipped = 0

    for _, row in tqdm(sampled.iterrows(), total=len(sampled), desc="fetch JATS"):
        pmcid = row["pmcid"]
        if not pmcid:
            errors.append({"pmid": row["pmid"], "pmcid": "", "error": "no PMCID"})
            continue
        out_path = config.RAW_DIR / f"{pmcid}.xml"
        if out_path.exists() and out_path.stat().st_size > 500:
            skipped += 1
            continue
        try:
            data = fetch_one(pmcid)
            if b"<pmc-articleset" not in data and b"<article" not in data:
                raise ValueError("response missing <article> root")
            out_path.write_bytes(data)
            ok += 1
        except Exception as e:  # noqa: BLE001
            errors.append({"pmid": row["pmid"], "pmcid": pmcid, "error": str(e)[:200]})
        time.sleep(SLEEP)

    print(f"\nFetched: {ok}  Skipped (cached): {skipped}  Errors: {len(errors)}")
    if errors:
        err_df = pd.DataFrame(errors)
        err_path = config.INDEX_DIR / "fetch_errors.csv"
        err_df.to_csv(err_path, index=False)
        print(f"Errors written to {err_path}")


if __name__ == "__main__":
    main()
