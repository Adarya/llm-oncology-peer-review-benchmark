"""Inter-model agreement, seven-model edition.

Computes:
  - Pairwise quadratic-weighted κ (21 pairs) on highest_tier_acceptance.
  - Pairwise recommendation κ (linear-weighted, 4-class).
  - Pairwise Pearson r and Bland-Altman LoA on overall_quality.
  - Seven-way Fleiss κ + ordinal Krippendorff α on tier (intersection sample).
  - Seven-way ICC(2,1) absolute-agreement on overall_quality.

Outputs:
  out/pairwise_kappa.csv
  out/pairwise_overall_corr.csv
  out/multimodel_agreement.csv
  figures/fig11_kappa_forest_pairwise.pdf
  figures/heatmap_pairwise_kappa_tier.pdf
  figures/fig7_<a>_vs_<b>_scatter_overall.pdf  (selected pairs only)
  figures/fig8_<a>_vs_<b>_bland_altman.pdf     (selected pairs only)
"""

from __future__ import annotations

import sys
from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_utils import (  # noqa: E402
    OUT_DIR, MODEL_COLOR, MODEL_LABEL, MODEL_ORDER, MODEL_SHORT,
    apply_style, new_panel, save_panel, ensure_dirs, pair_label, FIG_DIR,
)
from sklearn.metrics import cohen_kappa_score
from scipy import stats as scipy_stats


def fleiss_kappa(M: np.ndarray) -> float:
    """Fleiss' kappa for an N×k tally matrix (rows=items, cols=categories)."""
    n_total = M.sum(axis=1)
    n = int(n_total.max())
    N, k = M.shape
    p = M.sum(axis=0) / (N * n)
    P_i = (np.power(M, 2).sum(axis=1) - n) / (n * (n - 1))
    P_bar = P_i.mean()
    P_e = (p ** 2).sum()
    if P_e == 1.0:
        return 1.0
    return float((P_bar - P_e) / (1 - P_e))


def ordinal_krippendorff_alpha(values: np.ndarray) -> float:
    """Ordinal Krippendorff's α on an items × raters matrix with NaNs."""
    n_items, n_raters = values.shape
    cats = sorted({int(v) for v in values.ravel() if not np.isnan(v)})
    cmap = {c: i for i, c in enumerate(cats)}
    K = len(cats)
    if K < 2:
        return 1.0
    delta = np.zeros((K, K))
    for i in range(K):
        for j in range(K):
            delta[i, j] = (cats[i] - cats[j]) ** 2

    counts = np.zeros((n_items, K))
    for r in range(n_raters):
        for i in range(n_items):
            v = values[i, r]
            if not np.isnan(v):
                counts[i, cmap[int(v)]] += 1

    n = counts.sum(axis=1)
    valid = n >= 2
    counts = counts[valid]
    n = n[valid]

    Do = 0.0
    for c, n_i in zip(counts, n):
        for u in range(K):
            for v in range(K):
                if u == v:
                    continue
                Do += c[u] * c[v] * delta[u, v] / (n_i - 1)
    Do /= n.sum()

    p = counts.sum(axis=0) / counts.sum()
    De = 0.0
    for u in range(K):
        for v in range(K):
            if u == v:
                continue
            De += p[u] * p[v] * delta[u, v]

    return float(1 - Do / De) if De else 1.0


def icc21_absolute(values: np.ndarray) -> float:
    """ICC(2,1) absolute agreement, complete-cases only."""
    df = pd.DataFrame(values).dropna()
    if len(df) < 3:
        return float("nan")
    n, k = df.shape
    grand = df.values.mean()
    BMS = k * df.mean(axis=1).var(ddof=1)
    JMS = n * df.mean(axis=0).var(ddof=1)
    EMS = ((df.values - df.mean(axis=1).values[:, None] - df.mean(axis=0).values[None, :] + grand) ** 2).sum() / ((n - 1) * (k - 1))
    denom = BMS + (k - 1) * EMS + (k * (JMS - EMS) / n)
    return float((BMS - EMS) / denom) if denom else float("nan")


def main() -> None:
    apply_style()
    ensure_dirs()
    master = pd.read_csv(OUT_DIR / "master_per_paper.csv")

    pairs = list(combinations(MODEL_ORDER, 2))
    pair_rows = []
    overall_rows = []
    pair_kmat = pd.DataFrame(np.eye(len(MODEL_ORDER)), index=MODEL_ORDER, columns=MODEL_ORDER, dtype=float)

    for a, b in pairs:
        sa = a.replace("-", "_"); sb = b.replace("-", "_")
        ta = f"highest_tier_acceptance__{sa}"; tb = f"highest_tier_acceptance__{sb}"
        ra = f"recommendation_at_that_tier__{sa}"; rb = f"recommendation_at_that_tier__{sb}"
        oa = f"overall_quality_1_10__{sa}"; ob = f"overall_quality_1_10__{sb}"

        sub = master[[ta, tb]].dropna()
        kt = cohen_kappa_score(sub[ta].astype(int), sub[tb].astype(int), weights="quadratic") if len(sub) else np.nan

        sub_r = master[[ra, rb]].dropna()
        rec_kappa = cohen_kappa_score(sub_r[ra], sub_r[rb], weights="linear") if len(sub_r) else np.nan

        sub_o = master[[oa, ob]].dropna()
        if len(sub_o) >= 3:
            r_pearson, p_pearson = scipy_stats.pearsonr(sub_o[oa], sub_o[ob])
            diff = sub_o[oa] - sub_o[ob]
            mean_diff = diff.mean(); sd_diff = diff.std(ddof=1)
            loa_low = mean_diff - 1.96 * sd_diff; loa_high = mean_diff + 1.96 * sd_diff
        else:
            r_pearson = p_pearson = mean_diff = loa_low = loa_high = float("nan")

        pair_rows.append({
            "model_a": a, "model_b": b,
            "n_tier": int(len(sub)),
            "kappa_quad_tier": float(kt),
            "kappa_linear_recommendation": float(rec_kappa),
            "n_overall": int(len(sub_o)),
            "pearson_r_overall": float(r_pearson),
            "pearson_p_overall": float(p_pearson),
            "bland_altman_mean_diff": float(mean_diff),
            "bland_altman_loa_low": float(loa_low),
            "bland_altman_loa_high": float(loa_high),
        })
        pair_kmat.loc[a, b] = pair_kmat.loc[b, a] = float(kt)

    pair_df = pd.DataFrame(pair_rows)
    pair_df.to_csv(OUT_DIR / "pairwise_kappa.csv", index=False)
    pair_kmat.to_csv(OUT_DIR / "pairwise_kappa_matrix.csv")

    # Heat-map of pairwise tier kappa
    fig, ax = new_panel(size=(4.6, 4.0))
    arr = pair_kmat.values.astype(float)
    im = ax.imshow(arr, cmap="viridis", vmin=0, vmax=1)
    labels = [MODEL_LABEL[m] for m in MODEL_ORDER]
    ax.set_xticks(range(len(MODEL_ORDER))); ax.set_yticks(range(len(MODEL_ORDER)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10)
    ax.set_yticklabels(labels, fontsize=10)
    for i in range(len(MODEL_ORDER)):
        for j in range(len(MODEL_ORDER)):
            v = arr[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v < 0.55 else "black", fontsize=10)
    ax.set_title("Pairwise κ (predicted tier)")
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04)
    save_panel(fig, "heatmap_pairwise_kappa_tier")

    # Forest of pairwise kappas
    fig, ax = new_panel(size=(4.6, 4.6))
    pair_df_sorted = pair_df.sort_values("kappa_quad_tier", ascending=True).reset_index(drop=True)
    y = np.arange(len(pair_df_sorted))
    ax.scatter(pair_df_sorted["kappa_quad_tier"], y, s=40,
               color=[MODEL_COLOR[a] for a in pair_df_sorted["model_a"]])
    ax.set_yticks(y)
    ax.set_yticklabels([f"{MODEL_SHORT[a]} × {MODEL_SHORT[b]}"
                       for a, b in zip(pair_df_sorted["model_a"], pair_df_sorted["model_b"])],
                      fontsize=9)
    ax.axvline(0.4, color="#888", ls="--", lw=1)
    ax.set_xlabel("Pairwise quadratic-weighted κ (tier)")
    ax.set_xlim(0, 1)
    save_panel(fig, "fig11_kappa_forest_pairwise")

    # Multi-model summary on the all-7 intersection
    sub_cols = [f"highest_tier_acceptance__{m.replace('-', '_')}" for m in MODEL_ORDER]
    overall_cols = [f"overall_quality_1_10__{m.replace('-', '_')}" for m in MODEL_ORDER]
    inter = master.dropna(subset=sub_cols).copy()
    print(f"Intersection (all 7 models, tier): {len(inter)}")

    cats = [1, 2, 3, 4]
    M = np.zeros((len(inter), len(cats)), dtype=int)
    for j, m in enumerate(MODEL_ORDER):
        col = f"highest_tier_acceptance__{m.replace('-', '_')}"
        for ci, cat in enumerate(cats):
            M[:, ci] += (inter[col].astype(int).values == cat).astype(int)
    fk = fleiss_kappa(M)
    krip = ordinal_krippendorff_alpha(inter[sub_cols].astype(float).to_numpy())

    inter_oq = master.dropna(subset=overall_cols)
    icc = icc21_absolute(inter_oq[overall_cols].astype(float).to_numpy())
    print(f"Intersection (all 7 models, overall_quality): {len(inter_oq)}")

    multi = pd.DataFrame([{
        "n_intersection_tier": len(inter),
        "fleiss_kappa_tier_7way": fk,
        "krippendorff_alpha_ordinal_tier_7way": krip,
        "n_intersection_overall_quality": len(inter_oq),
        "icc21_absolute_overall_quality_7way": icc,
    }])
    multi.to_csv(OUT_DIR / "multimodel_agreement.csv", index=False)
    print(multi.round(3).to_string(index=False))

    # Selected pair scatters & Bland–Altman: each provider's lead model vs the others
    spotlight = [
        ("claude-opus-4-7", "gemini-3-flash-preview"),
        ("claude-opus-4-7", "gpt-5-5-medium"),
        ("claude-opus-4-7", "claude-haiku-4-5"),
        ("gpt-5-5-medium", "gpt-5-2-medium"),
        ("gpt-5-5-medium", "gpt-5-4-mini-medium"),
        ("claude-sonnet-4-6", "gpt-5-5-medium"),
    ]
    for a, b in spotlight:
        sa = a.replace("-", "_"); sb = b.replace("-", "_")
        oa = f"overall_quality_1_10__{sa}"; ob = f"overall_quality_1_10__{sb}"
        sub = master[[oa, ob]].dropna()
        if len(sub) < 5:
            continue
        # Scatter
        fig, ax = new_panel()
        ax.scatter(sub[oa], sub[ob], alpha=0.4, s=14, color="#444")
        lim = (0, 10)
        ax.plot(lim, lim, color="#888", ls="--", lw=1)
        ax.set_xlim(lim); ax.set_ylim(lim)
        ax.set_xlabel(MODEL_LABEL[a] + " (overall)")
        ax.set_ylabel(MODEL_LABEL[b] + " (overall)")
        save_panel(fig, f"fig7_{pair_label(a, b)}_scatter_overall")
        # Bland–Altman
        diff = sub[oa] - sub[ob]; mean = (sub[oa] + sub[ob]) / 2.0
        md = diff.mean(); sd = diff.std(ddof=1)
        fig, ax = new_panel()
        ax.scatter(mean, diff, alpha=0.4, s=14, color="#444")
        ax.axhline(md, color="#222", lw=1)
        ax.axhline(md + 1.96 * sd, color="#888", lw=1, ls="--")
        ax.axhline(md - 1.96 * sd, color="#888", lw=1, ls="--")
        ax.set_xlabel("Mean overall quality"); ax.set_ylabel("Δ overall quality")
        ax.set_title(f"{MODEL_SHORT[a]} − {MODEL_SHORT[b]}")
        save_panel(fig, f"fig8_{pair_label(a, b)}_bland_altman")


if __name__ == "__main__":
    main()
