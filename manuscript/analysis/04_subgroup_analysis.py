"""Subgroup-by-strata kappa for each of the seven models.

Outputs:
  tables/subgroup_kappa_by_study_type.csv
  tables/subgroup_kappa_by_cancer_domain.csv
  figures/fig12_subgroup_kappa_study_type.pdf
  figures/fig13_subgroup_kappa_cancer_domain.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_utils import (  # noqa: E402
    OUT_DIR, TABLE_DIR, MODEL_COLOR, MODEL_LABEL, MODEL_ORDER, MODEL_SHORT,
    apply_style, new_panel, save_panel, ensure_dirs,
)
from sklearn.metrics import cohen_kappa_score

MIN_N = 15  # minimum n per (model, stratum) cell to report


def per_strata_kappa(master: pd.DataFrame, strata_col: str) -> pd.DataFrame:
    rows = []
    for stratum, sub in master.groupby(strata_col):
        if not stratum or stratum == "":
            continue
        for model in MODEL_ORDER:
            sfx = model.replace("-", "_")
            pred_col = f"highest_tier_acceptance__{sfx}"
            data = sub[["tier", pred_col]].dropna()
            if len(data) < MIN_N:
                continue
            try:
                k = cohen_kappa_score(data["tier"].astype(int), data[pred_col].astype(int),
                                       weights="quadratic")
            except ValueError:
                k = float("nan")
            rows.append({
                "stratum": stratum, "model": model, "n": int(len(data)),
                "kappa_quadratic": float(k),
            })
    return pd.DataFrame(rows)


def fig_subgroup(df: pd.DataFrame, label: str, stem: str) -> None:
    strata = (df.groupby("stratum")["n"].max()
                .sort_values(ascending=False).index.tolist())
    fig, ax = new_panel(size=(5.4, 3.2 + 0.18 * len(strata)))
    width = 0.10
    y = np.arange(len(strata))
    for i, model in enumerate(MODEL_ORDER):
        sub = df[df["model"] == model].set_index("stratum")
        vals = [sub.loc[s, "kappa_quadratic"] if s in sub.index else np.nan for s in strata]
        ax.barh(y + (i - len(MODEL_ORDER) / 2 + 0.5) * width, vals,
                height=width, color=MODEL_COLOR[model], label=MODEL_LABEL[model])
    ax.axvline(0.4, color="#888", ls="--", lw=1)
    ax.set_yticks(y); ax.set_yticklabels(strata, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Quadratic-weighted κ"); ax.set_xlim(-0.2, 1.0)
    ax.set_title(f"Subgroup κ by {label}")
    ax.legend(fontsize=8, loc="lower right", ncols=2)
    save_panel(fig, stem)


def main() -> None:
    apply_style()
    ensure_dirs()
    master = pd.read_csv(OUT_DIR / "master_per_paper.csv")

    by_study = per_strata_kappa(master, "study_type")
    by_domain = per_strata_kappa(master, "cancer_domain")
    by_study.to_csv(TABLE_DIR / "subgroup_kappa_by_study_type.csv", index=False)
    by_domain.to_csv(TABLE_DIR / "subgroup_kappa_by_cancer_domain.csv", index=False)

    fig_subgroup(by_study, "study type", "fig12_subgroup_kappa_study_type")
    fig_subgroup(by_domain, "cancer domain", "fig13_subgroup_kappa_cancer_domain")

    print(f"Study-type strata × model rows: {len(by_study)}")
    print(f"Cancer-domain strata × model rows: {len(by_domain)}")


if __name__ == "__main__":
    main()
