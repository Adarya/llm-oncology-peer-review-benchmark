"""Journal-clustered 95% CIs of kappa, leave-one-journal-out kappa and results by journal (run 1).
Clustered bootstrap: journals resampled with replacement within tier, 2,000 resamples, seed 42.
Outputs: results/journal_clustered_ci.csv, leave_one_journal_out.csv, leave_one_journal_out_range.csv,
per_journal_results.csv
"""

import numpy as np
import pandas as pd

from common import LABEL, MODELS, analytic_sample, bootstrap, kappa, save, wide


def main():
    s = analytic_sample()
    w = wide(s, 1)
    print("Journals per tier:", s.groupby("tier").journal_name.nunique().to_dict())

    ci, lojo = [], []
    for m in MODELS:
        d = w[["tier", "journal_name", m]].dropna().rename(columns={m: "pred"}).astype({"pred": int})
        f = lambda x: kappa(x.tier, x.pred)
        k, plo, phi, _ = bootstrap(f, d)
        _, clo, chi, _ = bootstrap(f, d, cluster=True)
        ci.append({"model": LABEL[m], "n": len(d), "kappa_quadratic": round(k, 3),
                   "paper_level_ci_low": round(plo, 3), "paper_level_ci_high": round(phi, 3),
                   "journal_clustered_ci_low": round(clo, 3), "journal_clustered_ci_high": round(chi, 3)})
        for j in sorted(d.journal_name.unique()):
            r = d[d.journal_name != j]
            lojo.append({"model": LABEL[m], "journal_left_out": j,
                         "tier_of_journal": int(d[d.journal_name == j].tier.iloc[0]),
                         "n_remaining": len(r), "kappa_quadratic": round(kappa(r.tier, r.pred), 3)})
    ci = pd.DataFrame(ci)
    lojo = pd.DataFrame(lojo)
    rng = lojo.groupby("model", sort=False).agg(
        kappa_min=("kappa_quadratic", "min"), kappa_max=("kappa_quadratic", "max")).reset_index()
    rng["journal_giving_min"] = [lojo.loc[lojo[lojo.model == m].kappa_quadratic.idxmin(), "journal_left_out"]
                                 for m in rng.model]
    rng["journal_giving_max"] = [lojo.loc[lojo[lojo.model == m].kappa_quadratic.idxmax(), "journal_left_out"]
                                 for m in rng.model]
    save(ci, "journal_clustered_ci.csv")
    save(lojo, "leave_one_journal_out.csv")
    save(rng, "leave_one_journal_out_range.csv")
    print(ci.to_string(index=False))
    print(rng.to_string(index=False))

    pj = []
    for (t, j), g in w.groupby(["tier", "journal_name"]):
        r = {"tier": t, "journal": j, "n_papers": len(g)}
        for m in MODELS:
            p = g[m].dropna()
            r[f"{LABEL[m]}: n with output"] = len(p)
            r[f"{LABEL[m]}: mean predicted tier"] = round(p.mean(), 2)
            r[f"{LABEL[m]}: % predicted own tier"] = round(100 * (p == t).mean(), 1)
            r[f"{LABEL[m]}: % within one tier"] = round(100 * ((p - t).abs() <= 1).mean(), 1)
        pj.append(r)
    pj = pd.DataFrame(pj)
    save(pj, "per_journal_results.csv")
    print(pj[["tier", "journal", "n_papers"]].to_string(index=False))


if __name__ == "__main__":
    main()
