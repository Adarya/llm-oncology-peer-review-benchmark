"""Build manuscript tables (T1–T5).

Outputs into tables/:
  T1_cohort_characteristics.csv
  T2_primary_outcomes_by_model.csv
  T3_pairwise_intermodel_agreement.csv
  T4_specialist_means_by_model.csv
  T5_multimodel_agreement.csv
  publication_tables.md       (human-readable bundle)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_utils import (  # noqa: E402
    OUT_DIR, TABLE_DIR, MODEL_LABEL, MODEL_ORDER, MODEL_SHORT, ensure_dirs, format_p,
)


def t1_cohort(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rows.append(("Total papers (analytical sample)", str(len(master)), ""))
    counts = master["tier"].value_counts().sort_index()
    for t in [1, 2, 3, 4]:
        rows.append((f"  Tier {t} (source journal)", str(int(counts.get(t, 0))),
                     f"{counts.get(t, 0)/len(master)*100:.1f}%"))
    rows.append(("Cancer-domain strata represented",
                 str(master["cancer_domain"].nunique()), ""))
    rows.append(("Study-type strata represented",
                 str(master["study_type"].nunique()), ""))
    return pd.DataFrame(rows, columns=["Characteristic", "Value", "Percent"])


def t2_primary(master: pd.DataFrame) -> pd.DataFrame:
    metrics = pd.read_csv(OUT_DIR / "per_model_metrics.csv")
    out = metrics.copy()
    out["κ (95% CI)"] = out.apply(lambda r: f"{r['kappa_quadratic']:.3f} ({r['kappa_ci_low']:.3f}, {r['kappa_ci_high']:.3f})", axis=1)
    out["Exact match"] = (out["exact_match_frac"] * 100).round(1).astype(str) + "%"
    out["Within ±1"] = (out["within_1_tier_frac"] * 100).round(1).astype(str) + "%"
    out["Spearman ρ"] = out.apply(lambda r: f"{r['spearman_rho']:.3f} (p {format_p(r['spearman_p'])})", axis=1)
    out["Δ (pred − source)"] = out["mean_delta_pred_minus_source"].round(3).astype(str)
    out["Mean overall (1–10)"] = out["mean_overall_quality"].round(2).astype(str)
    out["Recommendation: accept"] = (out["rec_accept_frac"] * 100).round(1).astype(str) + "%"
    out["minor"] = (out["rec_minor_frac"] * 100).round(1).astype(str) + "%"
    out["major"] = (out["rec_major_frac"] * 100).round(1).astype(str) + "%"
    out["reject"] = (out["rec_reject_frac"] * 100).round(1).astype(str) + "%"
    cols = ["label", "n", "κ (95% CI)", "Exact match", "Within ±1", "Spearman ρ",
            "Δ (pred − source)", "Mean overall (1–10)",
            "Recommendation: accept", "minor", "major", "reject"]
    return out[cols].rename(columns={"label": "Model"})


def t3_pairwise() -> pd.DataFrame:
    df = pd.read_csv(OUT_DIR / "pairwise_kappa.csv")
    df["model_a"] = df["model_a"].map(MODEL_LABEL)
    df["model_b"] = df["model_b"].map(MODEL_LABEL)
    df["κ tier"] = df["kappa_quad_tier"].round(3)
    df["κ recommendation"] = df["kappa_linear_recommendation"].round(3)
    df["Pearson r (overall)"] = df["pearson_r_overall"].round(3)
    df["Bland–Altman (mean diff)"] = df["bland_altman_mean_diff"].round(3)
    df["LoA"] = df.apply(lambda r: f"({r['bland_altman_loa_low']:.2f}, {r['bland_altman_loa_high']:.2f})", axis=1)
    return df[["model_a", "model_b", "n_tier", "κ tier", "κ recommendation",
               "n_overall", "Pearson r (overall)", "Bland–Altman (mean diff)", "LoA"]]


def t4_specialist(master: pd.DataFrame) -> pd.DataFrame:
    dims = [
        ("meth_score", "Methodological rigor"),
        ("meth_stat_score", "Statistical appropriateness"),
        ("clinical_score", "Clinical / LoE"),
        ("reporting_score", "Reporting quality"),
        ("data_availability_score", "Data availability"),
        ("novelty_score", "Novelty"),
        ("writing_score", "Writing"),
    ]
    rows = []
    for col, label in dims:
        row = {"Dimension": label}
        for model in MODEL_ORDER:
            sfx = model.replace("-", "_")
            c = f"{col}__{sfx}"
            row[MODEL_LABEL[model]] = round(master[c].mean(skipna=True), 2)
        rows.append(row)
    return pd.DataFrame(rows)


def t5_multimodel() -> pd.DataFrame:
    df = pd.read_csv(OUT_DIR / "multimodel_agreement.csv")
    df = df.round(3)
    return df


def write_md(t1, t2, t3, t4, t5) -> None:
    p = TABLE_DIR / "publication_tables.md"
    parts = ["# Publication tables — seven-model benchmark\n"]
    for label, df in [("Table 1. Cohort characteristics", t1),
                      ("Table 2. Primary outcomes per model", t2),
                      ("Table 3. Pairwise inter-model agreement", t3),
                      ("Table 4. Specialist rubric means by model", t4),
                      ("Table 5. Seven-way multi-model agreement", t5)]:
        parts.append(f"\n## {label}\n")
        parts.append(df.to_markdown(index=False))
        parts.append("\n")
    p.write_text("\n".join(parts))


def main() -> None:
    ensure_dirs()
    master = pd.read_csv(OUT_DIR / "master_per_paper.csv")
    t1 = t1_cohort(master); t1.to_csv(TABLE_DIR / "T1_cohort_characteristics.csv", index=False)
    t2 = t2_primary(master); t2.to_csv(TABLE_DIR / "T2_primary_outcomes_by_model.csv", index=False)
    t3 = t3_pairwise(); t3.to_csv(TABLE_DIR / "T3_pairwise_intermodel_agreement.csv", index=False)
    t4 = t4_specialist(master); t4.to_csv(TABLE_DIR / "T4_specialist_means_by_model.csv", index=False)
    t5 = t5_multimodel(); t5.to_csv(TABLE_DIR / "T5_multimodel_agreement.csv", index=False)
    write_md(t1, t2, t3, t4, t5)
    print("Tables written to", TABLE_DIR)


if __name__ == "__main__":
    main()
