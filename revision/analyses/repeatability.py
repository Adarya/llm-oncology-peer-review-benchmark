"""Repeatability across runs 1 to 3 for the six models with three runs, and kappa against source tier in each run.
Measures: pairwise kappa between runs, Fleiss kappa, Krippendorff alpha, ICC(2,1) of overall quality.
Outputs: results/kappa_vs_source_by_run.csv, repeatability_three_runs.csv, repeatability_weighted.csv,
repeatability_rank_by_metric.csv
"""

import numpy as np
import pandas as pd

from common import LABEL, MODELS, REC_ORDER, analytic_sample, bootstrap, kappa, load_runs, save

SIX = [m for m in MODELS if m != "gemini-3-flash-preview"]

FIELDS = ["n", "kappa_q_run1_vs_2", "kappa_q_run1_vs_3", "kappa_q_run2_vs_3", "fleiss_kappa_3way",
             "krippendorff_alpha_ordinal", "icc_quality", "recommendation_fleiss_kappa",
             "strict_three_run_match_pct", "within_one_pct"]


def fleiss(vals: np.ndarray, k=4) -> float:
    """Unweighted Fleiss kappa; vals is items x raters with labels 1..k."""
    M = np.stack([(vals == c).sum(1) for c in range(1, k + 1)], 1).astype(float)
    n = vals.shape[1]
    p = M.sum(0) / M.sum()
    Pi = ((M ** 2).sum(1) - n) / (n * (n - 1))
    Pe = (p ** 2).sum()
    return float((Pi.mean() - Pe) / (1 - Pe))


def kripp(vals: np.ndarray, k=4, metric="ordinal") -> float:
    """Krippendorff alpha, complete data, labels 1..k. 'ordinal' uses the ordinal metric;
    'interval' uses squared differences (quadratic weighting)."""
    co = np.zeros((k, k))
    m = vals.shape[1]
    for row in vals.astype(int) - 1:
        for i in range(m):
            for j in range(m):
                if i != j:
                    co[row[i], row[j]] += 1 / (m - 1)
    npc = co.sum(1)
    N = co.sum()
    d = np.zeros((k, k))
    for c in range(k):
        for e in range(k):
            if c != e:
                if metric == "ordinal":
                    lo, hi = min(c, e), max(c, e)
                    d[c, e] = (npc[lo:hi + 1].sum() - (npc[c] + npc[e]) / 2) ** 2
                else:
                    d[c, e] = (c - e) ** 2
    Do = (co * d).sum() / N
    De = ((np.outer(npc, npc) - np.diag(npc)) * d).sum() / (N * (N - 1))
    return float(1 - Do / De)


def icc21(x: np.ndarray) -> float:
    n, k = x.shape
    g = x.mean()
    ssr = k * ((x.mean(1) - g) ** 2).sum()
    ssc = n * ((x.mean(0) - g) ** 2).sum()
    sse = ((x - g) ** 2).sum() - ssr - ssc
    msr, msc, mse = ssr / (n - 1), ssc / (k - 1), sse / ((n - 1) * (k - 1))
    return float((msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n))


def main():
    s = analytic_sample()
    L = load_runs()
    L = L[L.pmcid.isin(s.pmcid)]

    # kappa against source tier, per run
    rows = []
    for m in MODELS:
        r = {"model": LABEL[m]}
        ks = []
        for run in [1, 2, 3]:
            d = L[(L.model == m) & (L.run == run)][["pmcid", "pred_tier"]].dropna()
            d = d.merge(s[["pmcid", "tier", "journal_name"]], on="pmcid")
            r[f"run_{run}_n"] = len(d)
            if len(d):
                k = kappa(d.tier, d.pred_tier.astype(int))
                r[f"run_{run}_kappa"] = round(k, 3)
                ks.append(k)
            else:
                r[f"run_{run}_kappa"] = np.nan
        r["mean_kappa_over_available_runs"] = round(float(np.mean(ks)), 3)
        r["runs_available"] = len(ks)
        rows.append(r)
    byrun = pd.DataFrame(rows)
    save(byrun, "kappa_vs_source_by_run.csv")
    print(byrun.to_string(index=False))

    tab, wtd = [], []
    for m in SIX:
        W = {}
        for run in [1, 2, 3]:
            W[run] = L[(L.model == m) & (L.run == run)].set_index("pmcid")
        T = pd.DataFrame({r: W[r].pred_tier for r in [1, 2, 3]}).reindex(s.pmcid).dropna().astype(int)
        Q = pd.DataFrame({r: W[r].quality for r in [1, 2, 3]}).reindex(s.pmcid)
        Q = Q[Q.apply(lambda c: c.between(1, 10)).all(1)].dropna()
        R = pd.DataFrame({r: W[r].recommendation.map(lambda v: REC_ORDER.get(str(v).strip().lower()))
                          for r in [1, 2, 3]}).reindex(s.pmcid).dropna().astype(int)
        v = T.to_numpy()
        got = [len(T), kappa(v[:, 0], v[:, 1]), kappa(v[:, 0], v[:, 2]), kappa(v[:, 1], v[:, 2]),
               fleiss(v), kripp(v, metric="ordinal"), icc21(Q.to_numpy().astype(float)), fleiss(R.to_numpy()),
               100 * (v.max(1) == v.min(1)).mean(), 100 * ((v.max(1) - v.min(1)) <= 1).mean()]
        row = {"model": LABEL[m]}
        for f, g in zip(FIELDS, got):
            row[f] = round(g, 3) if f != "n" else g
        row["n_quality_complete"] = len(Q)
        row["n_recommendation_complete"] = len(R)
        tab.append(row)

        pairs = [(0, 1), (0, 2), (1, 2)]
        wtd.append({"model": LABEL[m], "n": len(T),
                    "mean_pairwise_kappa_quadratic": round(np.mean([kappa(v[:, a], v[:, b]) for a, b in pairs]), 3),
                    "krippendorff_alpha_interval_quadratic": round(kripp(v, metric="interval"), 3),
                    "krippendorff_alpha_ordinal": round(kripp(v, metric="ordinal"), 3),
                    "fleiss_kappa_unweighted": round(fleiss(v), 3),
                    "mean_pairwise_kappa_unweighted": round(np.mean([kappa(v[:, a], v[:, b], "unweighted") for a, b in pairs]), 3),
                    "strict_three_run_match_pct": round(100 * (v.max(1) == v.min(1)).mean(), 1),
                    "icc_quality": round(icc21(Q.to_numpy().astype(float)), 3)})
    tab = pd.DataFrame(tab)
    wtd = pd.DataFrame(wtd)
    save(tab, "repeatability_three_runs.csv")
    save(wtd, "repeatability_weighted.csv")
    pd.set_option("display.width", 250)
    print(tab.to_string(index=False))
    print(wtd.to_string(index=False))

    ranks = []
    for col in [c for c in wtd.columns if c not in ("model", "n")] + \
               ["kappa_q_run1_vs_2", "kappa_q_run1_vs_3", "kappa_q_run2_vs_3", "recommendation_fleiss_kappa", "within_one_pct"]:
        src = wtd if col in wtd else tab
        top = src.sort_values(col, ascending=False).iloc[0]
        ranks.append({"metric": col, "highest_model": top.model, "value": top[col],
                      "gpt_5_4_mini_value": float(src[src.model == LABEL["gpt-5-4-mini-medium"]][col].iloc[0])})
    ranks = pd.DataFrame(ranks)
    save(ranks, "repeatability_rank_by_metric.csv")
    print(ranks.to_string(index=False))

    g = L[(L.model == "gemini-3-flash-preview")]
    g2 = g[g.run == 2].set_index("pmcid").pred_tier.dropna()
    g1 = g[g.run == 1].set_index("pmcid").pred_tier.dropna()
    both = g1.index.intersection(g2.index)
    if len(both):
        print(f"Gemini partial second run: {len(g2)} papers with a tier; run1 vs run2 quadratic kappa on "
              f"{len(both)} papers = {kappa(g1[both].astype(int), g2[both].astype(int)):.3f}")


if __name__ == "__main__":
    main()
