"""Quadratic kappa per model (run 1) on the 485 analysed articles and on all 496 records with a run-1 output.
95% CIs: 2,000 paper-level bootstrap resamples, seed 42.
Output: results/original_496_sensitivity.csv
"""

import pandas as pd

from common import LABEL, MAIN, MODELS, analytic_sample, bootstrap, kappa, original_records, save, wide


def main():
    s485 = analytic_sample()
    s496 = original_records()
    ex = pd.read_csv(MAIN / "_exclusions.csv")
    print(f"records with a run-1 output: {len(s496)}; analysed: {len(s485)}; exclusion list: {len(ex)}")
    rows = []
    for name, s in [("analytic 485", s485), ("original 496", s496)]:
        w = wide(s, 1)
        for m in MODELS:
            d = w[["tier", "journal_name", m]].dropna().rename(columns={m: "pred"}).astype({"pred": int})
            k, lo, hi, _ = bootstrap(lambda x: kappa(x.tier, x.pred), d)
            rows.append({"sample": name, "model": LABEL[m], "n": len(d), "kappa_quadratic": round(k, 3),
                         "ci_low": round(lo, 3), "ci_high": round(hi, 3)})
    out = pd.DataFrame(rows)
    piv = out.pivot(index="model", columns="sample", values=["n", "kappa_quadratic"])
    save(out, "original_496_sensitivity.csv")
    print(piv.reindex([LABEL[m] for m in MODELS]).to_string())
    print(ex[["pmcid", "tier", "journal_name", "reason"]].to_string(index=False))


if __name__ == "__main__":
    main()
