"""Step 7 — Draw 10% random sample for manual QA of blinding.

Stratified by tier × journal. Copies the 50 normalized .md files into corpus/qa_sample/
and creates qa_manual_checklist.csv for a research assistant to fill in.

Usage:
    .venv/bin/python scripts/07_qa_sample.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

QA_FRACTION = 0.10
QA_SEED = config.RANDOM_SEED + 7


def main() -> None:
    tracker = pd.read_csv(config.PROJECT_ROOT / "corpus_tracker.csv", dtype=str).fillna("")
    tracker = tracker[tracker["md_exists"] == "True"].copy()

    rng = np.random.default_rng(QA_SEED)
    n_total = max(1, int(round(len(tracker) * QA_FRACTION)))

    counts = tracker.groupby(["tier", "journal_name"]).size()
    raw = counts * (n_total / counts.sum())
    alloc = np.floor(raw).astype(int)
    rem = (raw - alloc).sort_values(ascending=False)
    diff = n_total - alloc.sum()
    for idx in rem.index:
        if diff <= 0:
            break
        if alloc[idx] < counts[idx]:
            alloc[idx] += 1
            diff -= 1

    selected: list[pd.DataFrame] = []
    for (tier, journal), take in alloc.items():
        pool = tracker[(tracker["tier"] == tier) & (tracker["journal_name"] == journal)]
        if take <= 0 or pool.empty:
            continue
        take = int(min(take, len(pool)))
        sample_seed = int(rng.integers(0, 2**31 - 1))
        selected.append(pool.sample(n=take, random_state=sample_seed))

    qa = pd.concat(selected, ignore_index=True).sort_values(["tier", "journal_name", "pmcid"])
    print(f"Selected {len(qa)} papers for manual QA ({QA_FRACTION:.0%} of {len(tracker)})")

    qa_dir = config.CORPUS_DIR / "qa_sample"
    if qa_dir.exists():
        shutil.rmtree(qa_dir)
    qa_dir.mkdir(parents=True, exist_ok=True)

    for _, r in qa.iterrows():
        src = config.NORMALIZED_DIR / f"{r['pmcid']}.md"
        if src.exists():
            shutil.copy2(src, qa_dir / f"{r['pmcid']}.md")

    checklist = qa[["tier", "journal_name", "pmcid", "pmid", "doi", "pub_date",
                    "cancer_domain", "study_type", "title"]].copy()
    checklist["manual_status"] = "pending"
    checklist["journal_leak_found"] = ""
    checklist["publisher_leak_found"] = ""
    checklist["id_leak_found"] = ""
    checklist["author_affiliation_leak"] = ""
    checklist["other_issue"] = ""
    checklist["reviewer_initials"] = ""
    checklist["review_date"] = ""

    out = config.PROJECT_ROOT / "qa_manual_checklist.csv"
    checklist.to_csv(out, index=False)
    print(f"Wrote checklist: {out}")
    print(f"Markdown copies: {qa_dir}/")

    print("\nPer-tier sample count:")
    print(qa.groupby("tier").size().to_string())


if __name__ == "__main__":
    main()
