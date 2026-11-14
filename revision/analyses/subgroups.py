"""Quadratic kappa per model (run 1) by study type and by cancer domain, with 95% CIs (2,000 paper-level
bootstrap resamples, seed 42), and the source-tier distribution of each stratum.
Outputs: results/subgroup_kappa_study_type.csv, subgroup_kappa_cancer_domain.csv, subgroup_tier_distribution.csv
"""

import numpy as np
import pandas as pd

from common import LABEL, MODELS, analytic_sample, bootstrap, kappa, save, wide


def strata(w, col):
    rows = []
    for st, g in w.groupby(col):
        for m in MODELS:
            d = g[["tier", "journal_name", m]].dropna().rename(columns={m: "pred"}).astype({"pred": int})
            if len(d) < 2 or d.tier.nunique() < 2:
                k = lo = hi = np.nan
            else:
                k, lo, hi, _ = bootstrap(lambda x: kappa(x.tier, x.pred), d)
            rows.append({"stratum": st, "model": LABEL[m], "n": len(d),
                         "kappa_quadratic": round(k, 3), "ci_low": round(lo, 3), "ci_high": round(hi, 3),
                         "fewer_than_15_papers": len(d) < 15})
    return pd.DataFrame(rows)


def main():
    w = wide(analytic_sample(), 1)
    st = strata(w, "study_type")
    cd = strata(w, "cancer_domain")
    save(st, "subgroup_kappa_study_type.csv")
    save(cd, "subgroup_kappa_cancer_domain.csv")
    dist = []
    for col in ["study_type", "cancer_domain"]:
        for v, g in w.groupby(col):
            c = g.tier.value_counts().reindex([1, 2, 3, 4], fill_value=0)
            dist.append({"grouping": col, "stratum": v, "n": len(g), "tier_1": c[1], "tier_2": c[2],
                         "tier_3": c[3], "tier_4": c[4], "tier_sd": round(g.tier.std(), 2)})
    dist = pd.DataFrame(dist)
    save(dist, "subgroup_tier_distribution.csv")
    for name, t in [("study type", st), ("cancer domain", cd)]:
        print(f"\n{name}:")
        print(t.pivot(index="stratum", columns="model", values="kappa_quadratic")
              .reindex(columns=[LABEL[m] for m in MODELS]).round(2).to_string())
    print(dist.to_string(index=False))


if __name__ == "__main__":
    main()
