"""Compose supplementary multi-panel figures (seven-model edition).

Outputs into figures_composed_supp/:
  suppfig1_specialist_means      — 7 small multiples (specialist mean barhs)
  suppfig2_quality_by_tier       — 7 panels of overall-quality-by-tier boxes
  suppfig3_bland_altman          — 6 spotlight Bland–Altman tiles
  suppfig4_pairwise_confusion    — heatmap-of-heatmaps of pairwise predicted-tier overlap
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_utils import (  # noqa: E402
    OUT_DIR, WORK_ROOT,
    MODEL_COLOR, MODEL_LABEL, MODEL_ORDER, MODEL_SHORT,
    TIER_PALETTE, apply_style,
)

COMPOSED = WORK_ROOT / "figures_composed_supp"

SPEC_COLS = [
    ("meth_score", "Methodological"),
    ("meth_stat_score", "Statistical"),
    ("clinical_score", "Clinical"),
    ("reporting_score", "Reporting"),
    ("data_availability_score", "Data avail."),
    ("novelty_score", "Novelty"),
    ("writing_score", "Writing"),
]


def _spec_panel(ax, master, model):
    sfx = model.replace("-", "_")
    means, labels = [], []
    for col, lbl in SPEC_COLS:
        c = f"{col}__{sfx}"
        if c in master.columns:
            means.append(master[c].mean(skipna=True))
            labels.append(lbl)
    ax.barh(range(len(labels)), means, color=MODEL_COLOR[model])
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 5)
    ax.set_title(MODEL_LABEL[model], fontsize=10, fontweight="bold")


def supp1_specialist():
    fig, axes = plt.subplots(2, 4, figsize=(13, 5.6), layout="constrained")
    master = pd.read_csv(OUT_DIR / "master_per_paper.csv")
    for idx, m in enumerate(MODEL_ORDER):
        ax = axes[idx // 4, idx % 4]
        _spec_panel(ax, master, m)
    axes[1, 3].axis("off")
    fig.savefig(COMPOSED / "suppfig1_specialist_means.pdf")
    fig.savefig(COMPOSED / "suppfig1_specialist_means.png")
    plt.close(fig)


def supp2_quality_by_tier():
    master = pd.read_csv(OUT_DIR / "master_per_paper.csv")
    fig, axes = plt.subplots(2, 4, figsize=(13, 5.6), layout="constrained")
    for idx, m in enumerate(MODEL_ORDER):
        ax = axes[idx // 4, idx % 4]
        sfx = m.replace("-", "_")
        oq = f"overall_quality_1_10__{sfx}"
        data = [master[master["tier"] == t][oq].dropna().values for t in [1, 2, 3, 4]]
        bp = ax.boxplot(data, positions=[1, 2, 3, 4], widths=0.6,
                        patch_artist=True, medianprops={"color": "black"})
        for patch, c in zip(bp["boxes"], TIER_PALETTE):
            patch.set_facecolor(c); patch.set_alpha(0.7)
        ax.set_xticks([1, 2, 3, 4], ["1", "2", "3", "4"], fontsize=8)
        ax.set_title(MODEL_LABEL[m], fontsize=10, fontweight="bold")
        ax.set_ylim(0, 10)
        if idx % 4 == 0:
            ax.set_ylabel("Overall quality")
    axes[1, 3].axis("off")
    fig.savefig(COMPOSED / "suppfig2_quality_by_tier.pdf")
    fig.savefig(COMPOSED / "suppfig2_quality_by_tier.png")
    plt.close(fig)


def supp3_bland_altman():
    master = pd.read_csv(OUT_DIR / "master_per_paper.csv")
    pairs = [
        ("claude-opus-4-7", "claude-sonnet-4-6"),
        ("claude-opus-4-7", "claude-haiku-4-5"),
        ("claude-opus-4-7", "gemini-3-flash-preview"),
        ("claude-opus-4-7", "gpt-5-5-medium"),
        ("gpt-5-5-medium", "gpt-5-2-medium"),
        ("gpt-5-5-medium", "gpt-5-4-mini-medium"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(11, 6), layout="constrained")
    for idx, (a, b) in enumerate(pairs):
        ax = axes[idx // 3, idx % 3]
        sa = a.replace("-", "_"); sb = b.replace("-", "_")
        oa = f"overall_quality_1_10__{sa}"; ob = f"overall_quality_1_10__{sb}"
        sub = master[[oa, ob]].dropna()
        if len(sub) < 5:
            ax.axis("off"); continue
        diff = sub[oa] - sub[ob]; mean = (sub[oa] + sub[ob]) / 2.0
        md = diff.mean(); sd = diff.std(ddof=1)
        ax.scatter(mean, diff, alpha=0.4, s=10, color="#444")
        ax.axhline(md, color="#222", lw=1)
        ax.axhline(md + 1.96 * sd, color="#888", lw=1, ls="--")
        ax.axhline(md - 1.96 * sd, color="#888", lw=1, ls="--")
        ax.set_xlabel("Mean overall quality", fontsize=9)
        ax.set_ylabel("Δ", fontsize=9)
        ax.set_title(f"{MODEL_SHORT[a]} − {MODEL_SHORT[b]}", fontsize=10)
    fig.savefig(COMPOSED / "suppfig3_bland_altman.pdf")
    fig.savefig(COMPOSED / "suppfig3_bland_altman.png")
    plt.close(fig)


def supp4_pairwise_confusion():
    master = pd.read_csv(OUT_DIR / "master_per_paper.csv")
    n = len(MODEL_ORDER)
    fig, axes = plt.subplots(n, n, figsize=(11, 11), layout="constrained")
    for i, mi in enumerate(MODEL_ORDER):
        for j, mj in enumerate(MODEL_ORDER):
            ax = axes[i, j]
            if i == j:
                ax.axis("off")
                ax.text(0.5, 0.5, MODEL_LABEL[mi], ha="center", va="center",
                        transform=ax.transAxes, fontsize=8, fontweight="bold")
                continue
            sa = mi.replace("-", "_"); sb = mj.replace("-", "_")
            ta = f"highest_tier_acceptance__{sa}"; tb = f"highest_tier_acceptance__{sb}"
            sub = master[[ta, tb]].dropna()
            if len(sub) < 3:
                ax.axis("off"); continue
            ct = pd.crosstab(sub[ta].astype(int), sub[tb].astype(int)).reindex(
                index=[1, 2, 3, 4], columns=[1, 2, 3, 4], fill_value=0)
            arr = (ct.div(ct.sum(axis=1).replace(0, 1), axis=0) * 100).values
            ax.imshow(arr, cmap="Blues", vmin=0, vmax=100)
            ax.set_xticks([]); ax.set_yticks([])
            for s in ("top", "right", "bottom", "left"):
                ax.spines[s].set_visible(True); ax.spines[s].set_linewidth(0.5)
    fig.savefig(COMPOSED / "suppfig4_pairwise_confusion.pdf")
    fig.savefig(COMPOSED / "suppfig4_pairwise_confusion.png")
    plt.close(fig)


def main() -> None:
    apply_style()
    COMPOSED.mkdir(parents=True, exist_ok=True)
    supp1_specialist()
    supp2_quality_by_tier()
    supp3_bland_altman()
    supp4_pairwise_confusion()
    print("Composed supp figures →", COMPOSED)


if __name__ == "__main__":
    main()
