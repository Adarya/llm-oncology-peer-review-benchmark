"""AUROC of the overall quality score for each pair of source tiers (run 1), per model; the better tier is
the positive class; 95% CI from 1,000 bootstrap resamples within class (seed 42).
Input: manuscript/out/master_per_paper.csv. Output: results/auroc_tier_discrimination.csv
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from common import LABEL, MAIN, MODELS, save

N_BOOT = 1000
SEED = 42
PAIRS = list(itertools.combinations([1, 2, 3, 4], 2))


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Rank-based AUROC (Mann-Whitney U), ties by average ranks."""
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    r = rankdata(np.concatenate([pos, neg]))
    n1, n0 = len(pos), len(neg)
    return (r[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def boot_ci(pos: np.ndarray, neg: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    """Percentile CI; papers resampled within each class."""
    vals = np.empty(N_BOOT)
    for i in range(N_BOOT):
        p = rng.choice(pos, size=len(pos), replace=True)
        n = rng.choice(neg, size=len(neg), replace=True)
        vals[i] = auroc(p, n)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main() -> pd.DataFrame:
    master = pd.read_csv(MAIN / "out" / "master_per_paper.csv")
    rng = np.random.default_rng(SEED)

    records = []
    for m in MODELS:
        col = f"overall_quality_1_10__{m.replace('-', '_')}"
        sub = master[["tier", col]].dropna()
        sub.columns = ["tier", "q"]
        for a, b in PAIRS:
            pos = sub.loc[sub.tier == a, "q"].to_numpy(float)
            neg = sub.loc[sub.tier == b, "q"].to_numpy(float)
            point = auroc(pos, neg)
            lo, hi = boot_ci(pos, neg, rng)
            records.append({
                "model": m, "label": LABEL[m],
                "pair": f"T{a} vs T{b}", "tier_pos": a, "tier_neg": b,
                "n_pos": len(pos), "n_neg": len(neg),
                "auroc": point, "ci_low": lo, "ci_high": hi,
            })

    df = pd.DataFrame(records)
    save(df, "auroc_tier_discrimination.csv")
    print(df.round(3).to_string(index=False))
    return df


if __name__ == "__main__":
    main()
