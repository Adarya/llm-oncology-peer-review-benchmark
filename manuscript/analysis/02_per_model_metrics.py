"""Per-model primary outcomes and single-panel figures.

Outputs:
  out/per_model_metrics.csv        — primary table (kappa, accuracy, calibration)
  out/calibration_by_tier.csv      — mean(pred-source) by source tier × model
  figures/fig1_<model>_tier_confusion_rowpct
  figures/fig2_<model>_calibration_delta
  figures/fig3_<model>_overall_by_tier
  figures/fig4_<model>_recommendation_stack
  figures/fig5_<model>_specialist_means
  figures/fig6_<model>_predicted_tier_counts
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_utils import (  # noqa: E402
    OUT_DIR, MODEL_COLOR, MODEL_LABEL, MODEL_ORDER, MODEL_SHORT,
    TIER_PALETTE, apply_style, new_panel, save_panel, ensure_dirs,
)

from sklearn.metrics import cohen_kappa_score
from scipy import stats as scipy_stats

RNG_SEED = 42
N_BOOT = 1000
REC_ORDER = ["accept", "minor_revisions", "major_revisions", "reject"]
REC_COLORS = ["#2a8a5f", "#4b89c4", "#f2a541", "#c83c3c"]
SPEC_COLS = [
    ("meth_score", "Methodological"),
    ("meth_stat_score", "Statistical"),
    ("clinical_score", "Clinical / LoE"),
    ("reporting_score", "Reporting"),
    ("data_availability_score", "Data avail."),
    ("novelty_score", "Novelty"),
    ("writing_score", "Writing"),
]


def bootstrap_kappa_ci(y_true: np.ndarray, y_pred: np.ndarray, *,
                       n_boot: int = N_BOOT, seed: int = RNG_SEED) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    n = len(y_true)
    kappas = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        try:
            kappas[i] = cohen_kappa_score(y_true[idx], y_pred[idx], weights="quadratic")
        except ValueError:
            kappas[i] = np.nan
    point = cohen_kappa_score(y_true, y_pred, weights="quadratic")
    lo, hi = np.nanpercentile(kappas, [2.5, 97.5])
    return float(point), float(lo), float(hi)


def per_model_table(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model in MODEL_ORDER:
        sfx = model.replace("-", "_")
        pred_col = f"highest_tier_acceptance__{sfx}"
        oq_col = f"overall_quality_1_10__{sfx}"
        rec_col = f"recommendation_at_that_tier__{sfx}"
        sub = master[["tier", pred_col, oq_col, rec_col]].dropna(subset=["tier", pred_col])
        if len(sub) == 0:
            continue
        y_true = sub["tier"].astype(int).to_numpy()
        y_pred = sub[pred_col].astype(int).to_numpy()
        kappa, lo, hi = bootstrap_kappa_ci(y_true, y_pred)
        exact = float((y_true == y_pred).mean())
        within1 = float((np.abs(y_true - y_pred) <= 1).mean())
        rho, rho_p = scipy_stats.spearmanr(y_true, y_pred)
        mean_oq = float(master[oq_col].mean(skipna=True))
        mean_pred = float(sub[pred_col].mean())
        mean_source = float(sub["tier"].mean())
        rec = master[rec_col].dropna().value_counts(normalize=True)
        rows.append({
            "model": model,
            "label": MODEL_LABEL[model],
            "n": int(len(sub)),
            "kappa_quadratic": kappa, "kappa_ci_low": lo, "kappa_ci_high": hi,
            "exact_match_frac": exact, "within_1_tier_frac": within1,
            "spearman_rho": float(rho), "spearman_p": float(rho_p),
            "mean_overall_quality": mean_oq,
            "mean_pred_tier": mean_pred,
            "mean_source_tier": mean_source,
            "mean_delta_pred_minus_source": mean_pred - mean_source,
            "rec_accept_frac": float(rec.get("accept", 0.0)),
            "rec_minor_frac": float(rec.get("minor_revisions", 0.0)),
            "rec_major_frac": float(rec.get("major_revisions", 0.0)),
            "rec_reject_frac": float(rec.get("reject", 0.0)),
        })
    return pd.DataFrame(rows)


def calibration_by_tier(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model in MODEL_ORDER:
        sfx = model.replace("-", "_")
        pred_col = f"highest_tier_acceptance__{sfx}"
        sub = master[["tier", pred_col]].dropna()
        sub["delta"] = sub[pred_col].astype(float) - sub["tier"].astype(float)
        g = sub.groupby("tier")["delta"].agg(["mean", "std", "count"]).reset_index()
        g["model"] = model
        rows.append(g)
    out = pd.concat(rows, ignore_index=True)
    out.columns = ["source_tier", "mean_delta", "std_delta", "n", "model"]
    return out


def fig_tier_confusion(master: pd.DataFrame, model: str) -> None:
    sfx = model.replace("-", "_")
    pred_col = f"highest_tier_acceptance__{sfx}"
    sub = master[["tier", pred_col]].dropna()
    cm = pd.crosstab(sub["tier"].astype(int), sub[pred_col].astype(int)).reindex(
        index=[1, 2, 3, 4], columns=[1, 2, 3, 4], fill_value=0
    )
    row_pct = cm.div(cm.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    fig, ax = new_panel(size=(3.4, 2.9))
    im = ax.imshow(row_pct.values, cmap="Blues", vmin=0, vmax=1)
    for i in range(4):
        for j in range(4):
            v = row_pct.values[i, j]
            ax.text(j, i, f"{v*100:.0f}", ha="center", va="center",
                    fontsize=12, color="black" if v < 0.5 else "white")
    ax.set_xticks(range(4)); ax.set_xticklabels(["T1", "T2", "T3", "T4"])
    ax.set_yticks(range(4)); ax.set_yticklabels(["T1", "T2", "T3", "T4"])
    ax.set_xlabel("Predicted tier"); ax.set_ylabel("Source tier")
    ax.set_title(MODEL_LABEL[model])
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    save_panel(fig, f"fig1_{MODEL_SHORT[model]}_tier_confusion_rowpct")


def fig_calibration(cal: pd.DataFrame, model: str) -> None:
    sub = cal[cal["model"] == model]
    fig, ax = new_panel()
    ax.bar(sub["source_tier"].astype(int), sub["mean_delta"],
           color=MODEL_COLOR[model], width=0.7)
    ax.axhline(0, color="#666", lw=1)
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlabel("Source tier"); ax.set_ylabel("Δ (pred − source)")
    ax.set_title(MODEL_LABEL[model])
    save_panel(fig, f"fig2_{MODEL_SHORT[model]}_calibration_delta")


def fig_overall_by_tier(master: pd.DataFrame, model: str) -> None:
    sfx = model.replace("-", "_")
    oq_col = f"overall_quality_1_10__{sfx}"
    fig, ax = new_panel()
    data = [master[master["tier"] == t][oq_col].dropna().values for t in [1, 2, 3, 4]]
    bp = ax.boxplot(data, positions=[1, 2, 3, 4], widths=0.6, patch_artist=True,
                    medianprops={"color": "black"})
    for patch, c in zip(bp["boxes"], TIER_PALETTE):
        patch.set_facecolor(c); patch.set_alpha(0.7)
    ax.set_xticks([1, 2, 3, 4]); ax.set_xticklabels(["T1", "T2", "T3", "T4"])
    ax.set_xlabel("Source tier"); ax.set_ylabel("Overall quality (1–10)")
    ax.set_title(MODEL_LABEL[model])
    save_panel(fig, f"fig3_{MODEL_SHORT[model]}_overall_by_tier")


def fig_recommendation(master: pd.DataFrame, model: str) -> None:
    sfx = model.replace("-", "_")
    rec_col = f"recommendation_at_that_tier__{sfx}"
    fig, ax = new_panel()
    rows = []
    for tier in [1, 2, 3, 4]:
        s = master[master["tier"] == tier][rec_col].dropna()
        rows.append([(s == r).mean() for r in REC_ORDER])
    arr = np.array(rows)
    bottom = np.zeros(4)
    for i, (label, color) in enumerate(zip(REC_ORDER, REC_COLORS)):
        ax.bar([1, 2, 3, 4], arr[:, i], bottom=bottom, color=color,
               edgecolor="white", linewidth=0.8, label=label.replace("_", " "))
        bottom += arr[:, i]
    ax.set_xticks([1, 2, 3, 4]); ax.set_xticklabels(["T1", "T2", "T3", "T4"])
    ax.set_xlabel("Source tier"); ax.set_ylabel("Recommendation share")
    ax.set_ylim(0, 1)
    ax.set_title(MODEL_LABEL[model])
    ax.legend(fontsize=9, loc="lower right", ncols=2)
    save_panel(fig, f"fig4_{MODEL_SHORT[model]}_recommendation_stack")


def fig_specialist_means(master: pd.DataFrame, model: str) -> None:
    sfx = model.replace("-", "_")
    means = []
    labels = []
    for col, lbl in SPEC_COLS:
        c = f"{col}__{sfx}"
        if c not in master.columns:
            continue
        means.append(master[c].mean(skipna=True))
        labels.append(lbl)
    fig, ax = new_panel(size=(3.6, 2.7))
    ax.barh(range(len(labels)), means, color=MODEL_COLOR[model])
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Mean specialist score"); ax.set_xlim(0, 5)
    ax.set_title(MODEL_LABEL[model])
    save_panel(fig, f"fig5_{MODEL_SHORT[model]}_specialist_means")


def fig_predicted_counts(master: pd.DataFrame, model: str) -> None:
    sfx = model.replace("-", "_")
    pred_col = f"highest_tier_acceptance__{sfx}"
    counts = master[pred_col].dropna().astype(int).value_counts().reindex([1, 2, 3, 4], fill_value=0)
    fig, ax = new_panel()
    ax.bar([1, 2, 3, 4], counts.values, color=TIER_PALETTE)
    ax.set_xticks([1, 2, 3, 4]); ax.set_xticklabels(["T1", "T2", "T3", "T4"])
    ax.set_xlabel("Predicted tier"); ax.set_ylabel("Papers")
    ax.set_title(MODEL_LABEL[model])
    save_panel(fig, f"fig6_{MODEL_SHORT[model]}_predicted_tier_counts")


def fig_kappa_forest(table: pd.DataFrame) -> None:
    fig, ax = new_panel(size=(4.4, 3.0))
    y = np.arange(len(table))
    for i, row in table.iterrows():
        ax.errorbar(row["kappa_quadratic"], i,
                    xerr=[[row["kappa_quadratic"] - row["kappa_ci_low"]],
                          [row["kappa_ci_high"] - row["kappa_quadratic"]]],
                    fmt="o", color=MODEL_COLOR[row["model"]], capsize=3, lw=1.5,
                    markersize=8)
    ax.set_yticks(y); ax.set_yticklabels(table["label"])
    ax.invert_yaxis()
    ax.axvline(0.4, color="#888", ls="--", lw=1, label="κ = 0.4 (H1 floor)")
    ax.set_xlabel("Quadratic-weighted κ vs source tier")
    ax.set_xlim(0, 1)
    ax.legend(fontsize=10, loc="lower right")
    save_panel(fig, "fig10_kappa_forest_vs_source_tier")


def main() -> None:
    apply_style()
    ensure_dirs()
    master = pd.read_csv(OUT_DIR / "master_per_paper.csv")

    table = per_model_table(master)
    table.to_csv(OUT_DIR / "per_model_metrics.csv", index=False)
    print("\nPer-model primary outcomes:")
    print(table.set_index("label")[["n", "kappa_quadratic", "kappa_ci_low",
                                     "kappa_ci_high", "exact_match_frac",
                                     "within_1_tier_frac", "mean_delta_pred_minus_source"]]
          .round(3).to_string())

    cal = calibration_by_tier(master)
    cal.to_csv(OUT_DIR / "calibration_by_tier.csv", index=False)

    for model in MODEL_ORDER:
        fig_tier_confusion(master, model)
        fig_calibration(cal, model)
        fig_overall_by_tier(master, model)
        fig_recommendation(master, model)
        fig_specialist_means(master, model)
        fig_predicted_counts(master, model)

    fig_kappa_forest(table)


if __name__ == "__main__":
    main()
