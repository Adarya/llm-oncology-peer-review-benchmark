"""Compose multi-panel main figures.

Outputs into figures_composed/:
  fig1_primary.{pdf,png}                  — kappa forest + 7 confusion mini-tiles
  fig2_calibration_recommendation.{pdf,png} — 7 calibration deltas + 7 recommendation stacks
  fig3_intermodel.{pdf,png}               — 7×7 pairwise-kappa heatmap + family box-plots
  fig4_subgroups.{pdf,png}                — study-type and cancer-domain forest panels
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_utils import (  # noqa: E402
    OUT_DIR, WORK_ROOT, TABLE_DIR,
    MODEL_COLOR, MODEL_LABEL, MODEL_ORDER, MODEL_SHORT, MODEL_PROVIDER, PROVIDER_COLOR,
    TIER_PALETTE, apply_style,
)

COMPOSED = WORK_ROOT / "figures_composed"

REC_ORDER = ["accept", "minor_revisions", "major_revisions", "reject"]
REC_COLORS = ["#2ca25f", "#99d8c9", "#fd8d3c", "#c83c3c"]
REC_LABELS = ["Accept", "Minor", "Major", "Reject"]


def _label(ax, letter, x=-0.15, y=1.07):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=15, fontweight="bold",
            ha="left", va="top")


def _confusion(ax, master, model):
    sfx = model.replace("-", "_")
    sub = master[["tier", f"highest_tier_acceptance__{sfx}"]].dropna()
    sub["pred"] = sub[f"highest_tier_acceptance__{sfx}"].astype(int)
    sub["tier"] = sub["tier"].astype(int)
    ct = pd.crosstab(sub["tier"], sub["pred"]).reindex(
        index=[1, 2, 3, 4], columns=[1, 2, 3, 4], fill_value=0)
    arr = (ct.div(ct.sum(axis=1).replace(0, 1), axis=0) * 100).values
    ax.imshow(arr, cmap="Blues", vmin=0, vmax=100, aspect="equal")
    for i in range(4):
        for j in range(4):
            v = arr[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center",
                    color="white" if v > 55 else "#111", fontsize=8.5,
                    fontweight="bold")
    ax.set_xticks(range(4), labels=["1", "2", "3", "4"], fontsize=8)
    ax.set_yticks(range(4), labels=["1", "2", "3", "4"], fontsize=8)
    ax.set_title(MODEL_LABEL[model], fontsize=10, fontweight="bold")
    for s in ("top", "right", "bottom", "left"):
        ax.spines[s].set_visible(True); ax.spines[s].set_linewidth(0.8)


def _kappa_forest(ax, pm):
    pm = pm.set_index("model").reindex(MODEL_ORDER).reset_index()
    for i, row in pm.iterrows():
        ax.errorbar(
            row["kappa_quadratic"], i,
            xerr=[[row["kappa_quadratic"] - row["kappa_ci_low"]],
                  [row["kappa_ci_high"] - row["kappa_quadratic"]]],
            fmt="o", markersize=10, color=MODEL_COLOR[row["model"]],
            ecolor=MODEL_COLOR[row["model"]], elinewidth=2.2, capsize=3,
            capthick=1.2, markeredgecolor="black", markeredgewidth=0.7,
        )
    ax.axvline(0.4, color="#888", ls="--", lw=1)
    ax.set_yticks(range(len(pm)), labels=[MODEL_LABEL[m] for m in pm["model"]],
                  fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Quadratic-weighted κ vs source tier", fontsize=11)
    ax.set_xlim(0, 1)


def fig1_primary(master, pm):
    fig = plt.figure(figsize=(11.5, 5.6), layout="constrained")
    gs = fig.add_gridspec(2, 5, width_ratios=[1.6, 1, 1, 1, 1], height_ratios=[1, 1])
    ax_forest = fig.add_subplot(gs[:, 0])
    _kappa_forest(ax_forest, pm)
    _label(ax_forest, "a", x=-0.30)
    # Seven mini-confusion matrices in two rows (4 + 3)
    positions = [(0, 1), (0, 2), (0, 3), (0, 4),
                 (1, 1), (1, 2), (1, 3)]
    letters = ["b", "c", "d", "e", "f", "g", "h"]
    for (r, c), letter, model in zip(positions, letters, MODEL_ORDER):
        ax = fig.add_subplot(gs[r, c])
        _confusion(ax, master, model)
        _label(ax, letter)
    fig.savefig(COMPOSED / "fig1_primary.pdf")
    fig.savefig(COMPOSED / "fig1_primary.png")
    plt.close(fig)


def _calibration(ax, master, model):
    sfx = model.replace("-", "_")
    sub = master[["tier", f"highest_tier_acceptance__{sfx}"]].dropna()
    sub["delta"] = sub[f"highest_tier_acceptance__{sfx}"].astype(float) - sub["tier"].astype(float)
    g = sub.groupby("tier")["delta"].agg(["mean", "std", "count"]).reindex([1, 2, 3, 4])
    means = g["mean"].values
    sems = (g["std"] / np.sqrt(g["count"].replace(0, np.nan))).values
    x = np.arange(4)
    ax.bar(x, means, yerr=sems, color=TIER_PALETTE,
           edgecolor="black", linewidth=0.7, capsize=2,
           error_kw=dict(linewidth=0.7, ecolor="black"))
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_xticks(x, labels=["1", "2", "3", "4"], fontsize=8)
    ax.set_ylim(-2.4, 2.6)
    ax.set_title(MODEL_LABEL[model], fontsize=10, fontweight="bold")


def _recommendation(ax, master, model, show_legend=False):
    sfx = model.replace("-", "_")
    rec_col = f"recommendation_at_that_tier__{sfx}"
    sub = master[["tier", rec_col]].dropna()
    ct = pd.crosstab(sub["tier"], sub[rec_col], normalize="index") * 100
    ct = ct.reindex(index=[1, 2, 3, 4], columns=REC_ORDER, fill_value=0)
    x = np.arange(4)
    bottom = np.zeros(4)
    for col, c, lab in zip(REC_ORDER, REC_COLORS, REC_LABELS):
        vals = ct[col].values
        ax.bar(x, vals, bottom=bottom, color=c, edgecolor="black",
               linewidth=0.5, label=lab)
        bottom += vals
    ax.set_xticks(x, labels=["1", "2", "3", "4"], fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_title(MODEL_LABEL[model], fontsize=10, fontweight="bold")
    if show_legend:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25),
                  ncol=4, fontsize=9, frameon=False)


def fig2_calibration_recommendation(master):
    fig = plt.figure(figsize=(13.5, 6.0), layout="constrained")
    gs = fig.add_gridspec(2, 7)
    for j, m in enumerate(MODEL_ORDER):
        ax = fig.add_subplot(gs[0, j])
        _calibration(ax, master, m)
        if j == 0:
            ax.set_ylabel(r"$\Delta$ (pred $-$ source)", fontsize=10)
            _label(ax, "a", x=-0.3)
    for j, m in enumerate(MODEL_ORDER):
        ax = fig.add_subplot(gs[1, j])
        _recommendation(ax, master, m, show_legend=(j == 3))
        if j == 0:
            ax.set_ylabel("Recommendation share (%)", fontsize=10)
            _label(ax, "b", x=-0.3)
    fig.savefig(COMPOSED / "fig2_calibration_recommendation.pdf")
    fig.savefig(COMPOSED / "fig2_calibration_recommendation.png")
    plt.close(fig)


def fig3_intermodel(pair_kmat, master):
    fig = plt.figure(figsize=(11, 4.8), layout="constrained")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1])
    ax = fig.add_subplot(gs[0, 0])
    arr = pair_kmat.values
    im = ax.imshow(arr, cmap="viridis", vmin=0, vmax=1)
    labels = [MODEL_LABEL[m] for m in MODEL_ORDER]
    ax.set_xticks(range(len(MODEL_ORDER)), labels, rotation=40, ha="right", fontsize=9)
    ax.set_yticks(range(len(MODEL_ORDER)), labels, fontsize=9)
    for i in range(len(MODEL_ORDER)):
        for j in range(len(MODEL_ORDER)):
            v = arr[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v < 0.55 else "black", fontsize=9)
    ax.set_title("Pairwise quadratic-weighted κ (predicted tier)", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    _label(ax, "a", x=-0.3)

    # Right panel: ICC bar with provider grouping
    ax2 = fig.add_subplot(gs[0, 1])
    overall_cols = [f"overall_quality_1_10__{m.replace('-', '_')}" for m in MODEL_ORDER]
    sub = master[["tier"] + overall_cols].dropna()
    means = []
    for m, col in zip(MODEL_ORDER, overall_cols):
        means.append([
            MODEL_LABEL[m], MODEL_PROVIDER[m], MODEL_COLOR[m],
            sub[col].mean(),
        ])
    df = pd.DataFrame(means, columns=["label", "provider", "color", "mean_overall"])
    df = df.sort_values("mean_overall", ascending=True).reset_index(drop=True)
    ax2.barh(range(len(df)), df["mean_overall"], color=df["color"],
             edgecolor="black", linewidth=0.7)
    ax2.set_yticks(range(len(df)), df["label"], fontsize=9)
    ax2.set_xlabel("Mean overall quality (1–10)", fontsize=11)
    _label(ax2, "b", x=-0.3)
    fig.savefig(COMPOSED / "fig3_intermodel.pdf")
    fig.savefig(COMPOSED / "fig3_intermodel.png")
    plt.close(fig)


def fig4_subgroups(by_study, by_domain):
    fig = plt.figure(figsize=(13, 8), layout="constrained")
    gs = fig.add_gridspec(1, 2)

    def _draw(ax, df, title):
        strata = (df.groupby("stratum")["n"].max()
                    .sort_values(ascending=False).index.tolist())
        width = 0.10
        y = np.arange(len(strata))
        for i, model in enumerate(MODEL_ORDER):
            sub = df[df["model"] == model].set_index("stratum")
            vals = [sub.loc[s, "kappa_quadratic"] if s in sub.index else np.nan for s in strata]
            ax.barh(y + (i - len(MODEL_ORDER) / 2 + 0.5) * width, vals,
                    height=width, color=MODEL_COLOR[model], label=MODEL_LABEL[model])
        ax.axvline(0.4, color="#888", ls="--", lw=1)
        ax.set_yticks(y, strata, fontsize=10)
        ax.invert_yaxis()
        ax.set_xlabel("Quadratic-weighted κ", fontsize=11)
        ax.set_xlim(-0.2, 1.0)
        ax.set_title(title, fontsize=11, fontweight="bold")

    ax_a = fig.add_subplot(gs[0, 0]); _draw(ax_a, by_study, "Study-type strata"); _label(ax_a, "a")
    ax_b = fig.add_subplot(gs[0, 1]); _draw(ax_b, by_domain, "Cancer-domain strata"); _label(ax_b, "b")
    handles, labels_ = ax_a.get_legend_handles_labels()
    fig.legend(handles, labels_, ncol=4, loc="lower center",
               bbox_to_anchor=(0.5, -0.04), fontsize=9, frameon=False)
    fig.savefig(COMPOSED / "fig4_subgroups.pdf")
    fig.savefig(COMPOSED / "fig4_subgroups.png")
    plt.close(fig)


def main() -> None:
    apply_style()
    COMPOSED.mkdir(parents=True, exist_ok=True)
    master = pd.read_csv(OUT_DIR / "master_per_paper.csv")
    pm = pd.read_csv(OUT_DIR / "per_model_metrics.csv")
    pair_kmat = pd.read_csv(OUT_DIR / "pairwise_kappa_matrix.csv", index_col=0)
    pair_kmat = pair_kmat.reindex(index=MODEL_ORDER, columns=MODEL_ORDER).astype(float)
    by_study = pd.read_csv(TABLE_DIR / "subgroup_kappa_by_study_type.csv")
    by_domain = pd.read_csv(TABLE_DIR / "subgroup_kappa_by_cancer_domain.csv")

    fig1_primary(master, pm)
    fig2_calibration_recommendation(master)
    fig3_intermodel(pair_kmat, master)
    fig4_subgroups(by_study, by_domain)
    print("Composed main figures →", COMPOSED)


if __name__ == "__main__":
    main()
