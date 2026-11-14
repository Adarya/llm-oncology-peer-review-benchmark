"""Paired differences in quadratic kappa between models (run 1), on the papers with a tier from both models.
95% CIs: paper-level and journal-clustered bootstrap, 2,000 resamples, seed 42.
Outputs: results/kappa_differences_adjacent.csv, kappa_differences_vs_opus.csv, kappa_differences_all_pairs.csv
"""

import itertools

import pandas as pd

from common import LABEL, MODELS, analytic_sample, bootstrap, kappa, save, wide


def diff_row(w, a, b, clustered=True):
    d = w[["tier", "journal_name", a, b]].dropna()
    f = lambda x: kappa(x.tier, x[a].astype(int)) - kappa(x.tier, x[b].astype(int))
    pt, lo, hi, draws = bootstrap(f, d)
    r = {"model_A": LABEL[a], "model_B": LABEL[b], "n_papers_both": len(d),
         "kappa_A": round(kappa(d.tier, d[a].astype(int)), 3), "kappa_B": round(kappa(d.tier, d[b].astype(int)), 3),
         "difference_A_minus_B": round(pt, 3),
         "paper_level_ci_low": round(lo, 3), "paper_level_ci_high": round(hi, 3),
         "share_of_resamples_A_not_higher": round(float((draws <= 0).mean()), 4)}
    if clustered:
        _, clo, chi, cdraws = bootstrap(f, d, cluster=True)
        r.update({"journal_clustered_ci_low": round(clo, 3), "journal_clustered_ci_high": round(chi, 3),
                  "clustered_share_A_not_higher": round(float((cdraws <= 0).mean()), 4)})
    return r


def main():
    w = wide(analytic_sample(), 1)
    adj = pd.DataFrame([diff_row(w, a, b) for a, b in zip(MODELS, MODELS[1:])])
    vs = pd.DataFrame([diff_row(w, MODELS[0], b) for b in MODELS[1:]])
    allp = pd.DataFrame([diff_row(w, a, b, clustered=False) for a, b in itertools.combinations(MODELS, 2)])
    save(adj, "kappa_differences_adjacent.csv")
    save(vs, "kappa_differences_vs_opus.csv")
    save(allp, "kappa_differences_all_pairs.csv")
    cols = ["model_A", "model_B", "n_papers_both", "difference_A_minus_B", "paper_level_ci_low",
            "paper_level_ci_high", "journal_clustered_ci_low", "journal_clustered_ci_high"]
    print(adj[cols].to_string(index=False))
    print(vs[cols].to_string(index=False))


if __name__ == "__main__":
    main()
