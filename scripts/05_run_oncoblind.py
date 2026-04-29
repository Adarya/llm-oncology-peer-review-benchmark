"""Step 5 — Run oncoblind normalization on all fetched JATS XMLs.

Produces corpus/normalized/<PMCID>.md + corpus/index/qa_report.csv.

Usage:
    .venv/bin/python scripts/05_run_oncoblind.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from oncoblind import normalize  # noqa: E402


def main() -> None:
    config.NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    xml_files = sorted(config.RAW_DIR.glob("PMC*.xml"))
    print(f"Normalizing {len(xml_files)} XMLs")

    qa_rows: list[dict] = []
    failed: list[dict] = []

    for xml_path in tqdm(xml_files, desc="oncoblind"):
        pmcid = xml_path.stem
        try:
            raw = xml_path.read_bytes()
            result = normalize(raw)
            out_md = config.NORMALIZED_DIR / f"{pmcid}.md"
            out_md.write_text(result.markdown, encoding="utf-8")
            qa = result.qa
            qa_rows.append({
                "pmcid": pmcid,
                "passed": qa.passed,
                "journal_hits": len(qa.journal_hits),
                "publisher_hits": len(qa.publisher_hits),
                "id_hits": len(qa.id_hits),
                "url_hits": len(qa.url_hits),
                "journal_hit_sample": "; ".join(qa.journal_hits[:3]),
                "publisher_hit_sample": "; ".join(qa.publisher_hits[:3]),
                "id_hit_sample": "; ".join(qa.id_hits[:3]),
                "url_hit_sample": "; ".join(qa.url_hits[:3]),
                "n_redactions": len(result.redactions),
                "md_length": len(result.markdown),
            })
        except Exception as e:  # noqa: BLE001
            failed.append({"pmcid": pmcid, "error": str(e)[:300]})

    qa_df = pd.DataFrame(qa_rows)
    qa_df.to_csv(config.INDEX_DIR / "qa_report.csv", index=False)

    print(f"\nNormalized: {len(qa_df)}  Failed: {len(failed)}")
    if len(qa_df):
        print(f"QA passed: {int(qa_df['passed'].sum())} / {len(qa_df)}")
        print(f"Papers with journal-name leaks: {int((qa_df['journal_hits'] > 0).sum())}")
        print(f"Papers with publisher leaks:    {int((qa_df['publisher_hits'] > 0).sum())}")
        print(f"Papers with id leaks (DOI/PMID): {int((qa_df['id_hits'] > 0).sum())}")
        print(f"Papers with URL leaks:          {int((qa_df['url_hits'] > 0).sum())}")
        print(f"Median markdown length:         {int(qa_df['md_length'].median())}")

    if failed:
        fail_df = pd.DataFrame(failed)
        fail_df.to_csv(config.INDEX_DIR / "normalize_errors.csv", index=False)
        print(f"\nFailures written to {config.INDEX_DIR / 'normalize_errors.csv'}")


if __name__ == "__main__":
    main()
