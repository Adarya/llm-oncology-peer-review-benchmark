"""Apply the exclusion rule to the 497 sampled records and write the analytical sample (n=485).

The rule excludes 12 records: 9 retraction notices, 1 reply, 1 commentary and
1 record without extractable text.

Inputs: corpus/index/enumeration.csv, corpus/index/sampled.csv, corpus/normalized/ (not distributed).
Outputs: _exclusions.csv, out/_analytical_sample.csv.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_utils import PROJECT_ROOT, WORK_ROOT, OUT_DIR, ensure_dirs  # noqa: E402

ENUM = PROJECT_ROOT / "corpus/index/enumeration.csv"
SAMPLED = PROJECT_ROOT / "corpus/index/sampled.csv"
NORM_DIR = PROJECT_ROOT / "corpus/normalized"

EXCLUSIONS_CSV = WORK_ROOT / "_exclusions.csv"
ANALYTIC_CSV = OUT_DIR / "_analytical_sample.csv"

NON_RESEARCH_PT = (
    "Retraction Notice", "Erratum", "Expression of Concern",
    "Comment", "Editorial",
)
TITLE_EXCLUDE_PATTERNS = [
    r"^\[Retracted\]",
    r"^Retraction Note",
    r"^Reply to",
    r"^Response to",
    r"^Comment on",
    r"^Editorial",
    r"^Critical considerations for",
]
MIN_BODY_WORDS = 50  # minimum number of body words


def body_words(pmcid: str) -> int:
    f = NORM_DIR / f"{pmcid}.md"
    if not f.exists():
        return 0
    txt = f.read_text(encoding="utf-8")
    body = txt.split("## References")[0]
    body = re.sub(r"^## (Title|Figures|Tables)[\s\S]*?(?=^##|\Z)", "", body, flags=re.MULTILINE)
    return len(body.split())


def main() -> None:
    ensure_dirs()
    enum = pd.read_csv(ENUM, dtype=str).fillna("")
    sampled = pd.read_csv(SAMPLED, dtype=str).fillna("")

    sample = sampled.merge(
        enum[["pmcid", "pub_types", "title"]],
        on="pmcid",
        how="left",
        suffixes=("", "_enum"),
    )
    if "title_enum" in sample.columns:
        sample["title"] = sample["title"].where(sample["title"] != "", sample["title_enum"])
        sample = sample.drop(columns=["title_enum"])

    sample["body_words"] = [body_words(p) for p in sample["pmcid"]]

    exclusions = []
    for _, r in sample.iterrows():
        reasons = []
        pt = r.get("pub_types", "") or ""
        for needle in NON_RESEARCH_PT:
            if needle in pt:
                reasons.append(f"pub_types={needle}")
        title = (r.get("title") or "").strip()
        for pat in TITLE_EXCLUDE_PATTERNS:
            if re.match(pat, title, re.IGNORECASE):
                reasons.append(f"title_pattern={pat}")
                break
        if r["body_words"] < MIN_BODY_WORDS:
            reasons.append(f"body_words<{MIN_BODY_WORDS}")
        if reasons:
            exclusions.append({
                "pmcid": r["pmcid"],
                "tier": r["tier"],
                "journal_name": r["journal_name"],
                "title": title[:200],
                "pub_types": pt,
                "body_words": r["body_words"],
                "reason": "; ".join(sorted(set(reasons))),
            })

    excl = pd.DataFrame(exclusions)
    excl.to_csv(EXCLUSIONS_CSV, index=False)
    print(f"\nExclusions: {len(excl)} of {len(sample)}")
    if len(excl):
        print(excl[["pmcid", "tier", "body_words", "reason"]].to_string(index=False))

    analytic = sample[~sample["pmcid"].isin(excl["pmcid"])].copy()
    analytic[["tier", "journal_name", "pmcid", "pmid", "doi", "title",
              "cancer_domain", "study_type"]].to_csv(ANALYTIC_CSV, index=False)
    print(f"\nAnalytical sample: {len(analytic)} papers (was {len(sample)})")
    print("By tier:")
    print(analytic["tier"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
