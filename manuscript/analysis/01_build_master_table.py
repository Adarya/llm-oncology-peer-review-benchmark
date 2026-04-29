"""Build the unified seven-model master table.

Reads results/<model>/<PMCID>/run_1.json for each model and joins with the
analytical sample produced by 00_eligibility_filter.py. Writes a wide CSV:
one row per PMCID, columns for each chief and specialist field with model
suffix.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_utils import OUT_DIR, PROJECT_ROOT, MODEL_ORDER, ensure_dirs  # noqa: E402

RUN_ID = 1
RESULTS = PROJECT_ROOT / "results"
ANALYTIC_CSV = OUT_DIR / "_analytical_sample.csv"

CHIEF_KEYS = [
    "overall_quality_1_10",
    "highest_tier_acceptance",
    "recommendation_at_that_tier",
    "predicted_hallucination_flag",
]
SPEC_DIM_COL = {
    ("methodological_rigor", "score"):                  "meth_score",
    ("methodological_rigor", "statistical_score"):      "meth_stat_score",
    ("clinical_relevance_loe", "score"):                "clinical_score",
    ("clinical_relevance_loe", "loe_oxford"):           "loe_oxford",
    ("reporting_quality", "score"):                     "reporting_score",
    ("reporting_quality", "standard_used"):             "standard_used",
    ("reporting_quality", "data_availability_score"):   "data_availability_score",
    ("novelty_literature", "score"):                    "novelty_score",
    ("writing_presentation", "score"):                  "writing_score",
}


def _load_one_model(model_dir: Path, suffix: str) -> pd.DataFrame:
    rows: list[dict] = []
    for path in sorted(model_dir.glob(f"PMC*/run_{RUN_ID}.json")):
        pmcid = path.parent.name
        try:
            r = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        cr = r.get("chief_reviewer") or {}
        ss = r.get("specialist_scores") or {}
        # Some Haiku/agent JSONs nested chief_reviewer inside specialist_scores
        if isinstance(ss, dict) and "chief_reviewer" in ss and not cr:
            cr = ss.get("chief_reviewer", {})
        row: dict = {"pmcid": pmcid}
        for k in CHIEF_KEYS:
            row[f"{k}__{suffix}"] = cr.get(k) if isinstance(cr, dict) else None
        row[f"architecture__{suffix}"] = r.get("architecture")
        for (section, key), colname in SPEC_DIM_COL.items():
            sec = ss.get(section) if isinstance(ss, dict) else None
            row[f"{colname}__{suffix}"] = sec.get(key) if isinstance(sec, dict) else None
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    ensure_dirs()
    if not ANALYTIC_CSV.exists():
        raise SystemExit("Run 00_eligibility_filter.py first")
    base = pd.read_csv(ANALYTIC_CSV, dtype=str).fillna("")
    base["tier"] = pd.to_numeric(base["tier"], errors="coerce")

    for model in MODEL_ORDER:
        mdir = RESULTS / model
        df = _load_one_model(mdir, suffix=model.replace("-", "_"))
        base = base.merge(df, on="pmcid", how="left")

    numeric_keywords = (
        "overall_quality_1_10", "highest_tier_acceptance",
        "meth_score", "meth_stat_score", "clinical_score",
        "reporting_score", "data_availability_score",
        "novelty_score", "writing_score",
    )
    for c in [col for col in base.columns if any(k in col for k in numeric_keywords)]:
        base[c] = pd.to_numeric(base[c], errors="coerce")
    # Clamp predicted tier to 1..4 (some Haiku/Sonnet papers used "5" for retraction)
    for c in [col for col in base.columns if "highest_tier_acceptance" in col]:
        base[c] = base[c].where((base[c] >= 1) & (base[c] <= 4))

    out = OUT_DIR / "master_per_paper.csv"
    base.to_csv(out, index=False)

    print(f"Master table: {out}")
    print(f"Rows: {len(base)}  (analytical sample)")
    coverage = {}
    for model in MODEL_ORDER:
        sfx = model.replace("-", "_")
        col = f"highest_tier_acceptance__{sfx}"
        coverage[model] = int(base[col].notna().sum())
    for m, n in coverage.items():
        print(f"  {m}: {n} valid predictions")


if __name__ == "__main__":
    main()
