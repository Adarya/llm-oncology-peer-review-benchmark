"""Table 1 (run 1): per model, n, quadratic kappa with 95% CI (1,000 paper-level bootstrap resamples, seed 42),
exact and within-one-tier agreement, mean signed difference and mean overall quality.
Input: results/<model>/<PMCID>/run_1.json. Output: results/table1.csv
"""

import pandas as pd

from common import LABEL, MODELS, analytic_sample, bootstrap, exact, kappa, save, wide, within_one


def main():
    s = analytic_sample()
    tiers = wide(s, 1, "pred_tier")
    qual = wide(s, 1, "quality")
    rows = []
    for m in MODELS:
        d = tiers[["pmcid", "tier", "journal_name", m]].dropna(subset=[m]).rename(columns={m: "pred"})
        d["pred"] = d["pred"].astype(int)
        k, lo, hi, _ = bootstrap(lambda x: kappa(x.tier, x.pred), d, n_boot=1000)
        rows.append({"model": LABEL[m], "n": len(d), "kappa_quadratic": round(k, 4), "ci_low": round(lo, 4),
                     "ci_high": round(hi, 4), "exact_pct": round(100 * exact(d.tier, d.pred), 2),
                     "within_one_pct": round(100 * within_one(d.tier, d.pred), 2),
                     "mean_difference_pred_minus_source": round((d.pred - d.tier).mean(), 4),
                     "mean_overall_quality": round(qual[m].mean(), 4)})
    out = pd.DataFrame(rows)
    save(out, "table1.csv")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
