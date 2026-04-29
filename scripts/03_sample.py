"""Step 3 — Stratified random sampling per journal quota.

For each journal, sample up to quota papers, stratified by (cancer_domain, study_type).
Seed = config.RANDOM_SEED. Writes corpus/index/sampled.csv.

Usage:
    .venv/bin/python scripts/03_sample.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def proportional_allocation(counts: pd.Series, n: int) -> pd.Series:
    """Allocate n across strata proportionally, capped by stratum size."""
    if counts.sum() == 0 or n == 0:
        return pd.Series(0, index=counts.index, dtype=int)
    raw = counts * (n / counts.sum())
    alloc = np.floor(raw).astype(int)
    remainders = (raw - alloc).sort_values(ascending=False)
    diff = n - alloc.sum()
    for idx in remainders.index:
        if diff <= 0:
            break
        if alloc[idx] < counts[idx]:
            alloc[idx] += 1
            diff -= 1
    while diff > 0:
        room = (counts - alloc).sort_values(ascending=False)
        if room.iloc[0] <= 0:
            break
        alloc[room.index[0]] += 1
        diff -= 1
    return alloc


def stratified_sample(df: pd.DataFrame, n: int, strata_cols: list[str], seed: int) -> pd.DataFrame:
    n = min(n, len(df))
    if n == 0:
        return df.iloc[0:0]
    counts = df.groupby(strata_cols).size()
    alloc = proportional_allocation(counts, n)
    rng = np.random.default_rng(seed)
    samples = []
    for strata, take in alloc.items():
        if take <= 0:
            continue
        mask = pd.Series(True, index=df.index)
        cols = strata_cols if isinstance(strata, tuple) else [strata_cols[0]]
        vals = strata if isinstance(strata, tuple) else (strata,)
        for c, v in zip(cols, vals):
            mask &= (df[c] == v)
        subset = df[mask]
        sample_seed = int(rng.integers(0, 2**31 - 1))
        samples.append(subset.sample(n=int(take), random_state=sample_seed))
    return pd.concat(samples).sort_index()


def main() -> None:
    df = pd.read_csv(config.INDEX_DIR / "classification.csv", dtype=str).fillna("")
    print(f"Loaded {len(df)} classified rows")

    sampled_parts: list[pd.DataFrame] = []
    report_rows: list[dict] = []

    for j in config.JOURNALS:
        pool = df[df["nlm_abbr"] == j["nlm"]].copy()
        target = min(j["quota"], len(pool))
        sampled = stratified_sample(pool, target, ["cancer_domain", "study_type"], seed=config.RANDOM_SEED + j["tier"] * 100 + hash(j["nlm"]) % 1000)
        sampled_parts.append(sampled)
        report_rows.append({
            "tier": j["tier"],
            "journal": j["name"],
            "pool": len(pool),
            "quota": j["quota"],
            "sampled": len(sampled),
            "short": j["quota"] - len(sampled),
        })
        print(f"  [{j['tier']}] {j['name']}: pool={len(pool)}, quota={j['quota']}, sampled={len(sampled)}")

    sampled = pd.concat(sampled_parts, ignore_index=True)
    out = config.INDEX_DIR / "sampled.csv"
    sampled.to_csv(out, index=False)

    report = pd.DataFrame(report_rows)
    report.loc["TOTAL"] = [
        "", "TOTAL",
        int(report["pool"].sum()),
        int(report["quota"].sum()),
        int(report["sampled"].sum()),
        int(report["short"].sum()),
    ]
    print("\n=== Sample report ===")
    print(report.to_string(index=False))
    print(f"\nWrote {len(sampled)} rows to {out}")

    print("\n=== Sampled: domain × tier ===")
    print(pd.crosstab(sampled["cancer_domain"], sampled["tier"]).to_string())
    print("\n=== Sampled: study_type × tier ===")
    print(pd.crosstab(sampled["study_type"], sampled["tier"]).to_string())


if __name__ == "__main__":
    main()
