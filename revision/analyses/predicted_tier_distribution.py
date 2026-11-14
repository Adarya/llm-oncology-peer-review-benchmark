"""Predicted tier by source tier (run 1): per model, counts and percentages of each predicted tier within
each source tier and over all manuscripts with a valid tier.
Input: results/<model>/<PMCID>/run_1.json. Output: results/predicted_tier_by_source_tier.csv
"""

import pandas as pd

from common import LABEL, MODELS, analytic_sample, save, wide

TIERS = (1, 2, 3, 4)


def main():
    w = wide(analytic_sample(), 1)
    rows = []
    for m in MODELS:
        d = w[["tier", m]].dropna().astype(int)
        for name, g in [(str(t), d[d.tier == t]) for t in TIERS] + [("all", d)]:
            c = g[m].value_counts().reindex(TIERS, fill_value=0)
            r = {"model": LABEL[m], "source_tier": name, "n": len(g)}
            r.update({f"n_predicted_tier_{k}": int(c[k]) for k in TIERS})
            r.update({f"pct_predicted_tier_{k}": round(100 * c[k] / len(g), 1) for k in TIERS})
            rows.append(r)
    out = pd.DataFrame(rows)
    save(out, "predicted_tier_by_source_tier.csv")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
