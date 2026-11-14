"""Agreement with source tier under three kappa weightings, Gwet AC1/AC2 and constant-rule baselines (run 1).
Kappa CIs: 2,000 paper-level bootstrap resamples, seed 42.
Outputs: results/agreement_by_weighting.csv, results/constant_rule_baselines.csv
"""

import numpy as np
import pandas as pd

from common import LABEL, MODELS, analytic_sample, bootstrap, exact, gwet_ac2, kappa, save, wide, within_one


def main():
    s = analytic_sample()
    w = wide(s, 1)
    rows = []
    for m in MODELS:
        d = w[["tier", "journal_name", m]].dropna().rename(columns={m: "pred"}).astype({"pred": int})
        r = {"model": LABEL[m], "n": len(d)}
        for wt in ["unweighted", "linear", "quadratic"]:
            k, lo, hi, _ = bootstrap(lambda x, wt=wt: kappa(x.tier, x.pred, wt), d)
            r[f"kappa_{wt}"], r[f"kappa_{wt}_ci_low"], r[f"kappa_{wt}_ci_high"] = round(k, 3), round(lo, 3), round(hi, 3)
        r["gwet_ac1_unweighted"] = round(gwet_ac2(d.tier, d.pred, "unweighted"), 3)
        r["gwet_ac2_linear"] = round(gwet_ac2(d.tier, d.pred, "linear"), 3)
        r["gwet_ac2_quadratic"] = round(gwet_ac2(d.tier, d.pred, "quadratic"), 3)
        r["exact_pct"] = round(100 * exact(d.tier, d.pred), 1)
        r["within_one_pct"] = round(100 * within_one(d.tier, d.pred), 1)
        rows.append(r)
    out = pd.DataFrame(rows)
    save(out, "agreement_by_weighting.csv")
    print(out.to_string(index=False))

    t = s.tier.to_numpy()
    base = []
    for k in [1, 2, 3, 4]:
        c = np.full_like(t, k)
        base.append({"rule": f"always tier {k}", "n": len(t), "exact_pct": round(100 * exact(t, c), 1),
                     "within_one_pct": round(100 * within_one(t, c), 1),
                     "kappa_quadratic": 0.0,
                     "gwet_ac2_quadratic": round(gwet_ac2(t, c, "quadratic"), 3)})
    b = pd.DataFrame(base)
    save(b, "constant_rule_baselines.csv")
    print("\nSource tier counts:", s.tier.value_counts().sort_index().to_dict())
    print(b.to_string(index=False))


if __name__ == "__main__":
    main()
