"""Kappa per model (run 1) against tiers recomputed from Journal Citation Reports values under two band sets
(>= 20 / 10 / 4 and >= 30 / 10 / 4, JCR 2024 and 2025), and Spearman correlation of predicted tier with log JIF.
Input: revision/data/jcr_values.csv. 95% CIs: 2,000 paper-level bootstrap resamples, seed 42.
Outputs: results/retiering_by_jcr.csv, results/retiering_papers_changed.csv
"""

import numpy as np
import pandas as pd
from scipy import stats

from common import DATA, LABEL, MODELS, analytic_sample, bootstrap, kappa, save, wide

JCR = DATA / "jcr_values.csv"
LABEL_SETS = {
    "assigned tier": "assigned_tier",
    "bands given to models 20/10/4, JCR 2024": "tier_bands_given_to_models_20_10_4_jcr2024",
    "bands given to models 20/10/4, JCR 2025": "tier_bands_given_to_models_20_10_4_jcr2025",
    "protocol bands 30/10/4, JCR 2024": "tier_protocol_bands_30_10_4_jcr2024",
    "protocol bands 30/10/4, JCR 2025": "tier_protocol_bands_30_10_4_jcr2025",
}


def main():
    j = pd.read_csv(JCR).set_index("journal")
    s = analytic_sample()
    missing = set(s.journal_name) - set(j.index)
    assert not missing, f"journals not in jcr_values.csv: {missing}"
    assert (s.journal_name.map(j.assigned_tier) == s.tier).all(), "assigned_tier in jcr_values.csv differs from corpus tier"
    w = wide(s, 1)
    for name, col in LABEL_SETS.items():
        w[name] = w.journal_name.map(j[col]).astype(int)
    w["log_jif_2025"] = np.log(w.journal_name.map(j.jif_2025))

    changed = []
    for name in LABEL_SETS:
        diff = w[w[name] != w.tier]
        changed.append({"label_set": name, "n_papers_tier_changed": len(diff), "of_n": len(w),
                        "journals_changed": "; ".join(f"{jn} ({int(g.tier.iloc[0])}->{int(g[name].iloc[0])}, n={len(g)})"
                                                      for jn, g in diff.groupby("journal_name")),
                        "tier_counts_1_to_4": "/".join(str(int((w[name] == k).sum())) for k in [1, 2, 3, 4])})
    changed = pd.DataFrame(changed)
    save(changed, "retiering_papers_changed.csv")
    pd.set_option("display.width", 250, "display.max_colwidth", 150)
    print(changed.to_string(index=False))

    rows = []
    for m in MODELS:
        d = w.dropna(subset=[m]).copy()
        d["pred"] = d[m].astype(int)
        r = {"model": LABEL[m], "n": len(d)}
        for name in LABEL_SETS:
            dd = d.assign(ref=d[name])
            k, lo, hi, _ = bootstrap(lambda x: kappa(x.ref, x.pred), dd)
            r[f"kappa: {name}"] = round(k, 3)
            r[f"ci: {name}"] = f"{lo:.3f} to {hi:.3f}"
        rho, p = stats.spearmanr(d.pred, d.log_jif_2025)
        r["spearman predicted tier vs log JIF 2025"] = round(rho, 3)
        r["spearman p"] = f"{p:.1e}"
        rows.append(r)
    ref = stats.spearmanr(w.tier, w.log_jif_2025)[0]
    rows.append({"model": "assigned tier", "n": len(w),
                 "spearman predicted tier vs log JIF 2025": round(ref, 3)})
    out = pd.DataFrame(rows)
    save(out, "retiering_by_jcr.csv")
    print(out[["model", "n"] + [f"kappa: {n}" for n in LABEL_SETS] + ["spearman predicted tier vs log JIF 2025"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
