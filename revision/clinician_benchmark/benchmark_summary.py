"""Clinician benchmark: quadratic kappa against source tier for each clinician, the clinicians pooled and each
model on the same 80 manuscripts, and between the two clinicians of a manuscript; 95% CIs from 2,000 bootstrap
resamples of manuscripts within tier (seed 42). Inputs (not distributed): <folder>/ratings_<id>/M*.json and
<folder>/key.csv, with <folder> as the only argument. Output: benchmark_summary.csv
"""

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parent / "analyses"))
import common  # noqa: E402

MODELS = common.MODELS

RATERS = ["a", "b", "c", "d"]  # ids of the four rating sets (folder names ratings_<id>)
# ratings left out: manuscripts the clinician had seen before the benchmark
SEEN_BEFORE = {("a", "M25"), ("b", "M22"), ("b", "M70")}
B, SEED = 2000, 42


def kw(a, b):
    return round(cohen_kappa_score(a, b, weights="quadratic"), 2)


def load(folder: Path, rater: str) -> pd.DataFrame:
    rows = []
    for f in glob.glob(str(folder / f"ratings_{rater}/M*.json")):
        d = json.load(open(f))
        d = d.get("data", d)
        d["code"] = Path(f).stem
        rows.append(d)
    return pd.DataFrame(rows).set_index("code").rename(columns={"tier": "rating"}) if rows else pd.DataFrame()


def boot(papers, stat):
    rng = np.random.default_rng(SEED)
    groups = [g.index.to_numpy() for _, g in papers.groupby("tier")]
    vals = []
    for _ in range(B):
        idx = np.concatenate([rng.choice(g, len(g)) for g in groups])
        vals.append(stat(idx))
    return np.percentile(vals, [2.5, 97.5]).round(2)


def main(folder):
    key = pd.read_csv(folder / "key.csv", keep_default_na=False).set_index("code")
    long = pd.concat([load(folder, r).assign(rater=r) for r in RATERS]).reset_index()
    long = long[[(r, c) not in SEEN_BEFORE for r, c in zip(long.rater, long.code)]]
    long["rating"] = long.rating.astype(int)
    long["tier"] = long.code.map(key.tier).astype(int)
    papers = key[["tier", "pmcid"]].copy()
    run1 = common.wide(common.analytic_sample()).set_index("pmcid")
    for m in MODELS:
        papers[m] = papers.pmcid.map(run1[m])
    by_paper = long.groupby("code")
    rows = []

    def add(name, n, k, ci, exact=None):
        rows.append({"comparison": name, "n": n, "kappa_w": k, "ci_low": ci[0], "ci_high": ci[1], "exact": exact})

    for r in RATERS:
        d = long[long.rater == r]
        add(f"clinician {r} vs source", len(d), kw(d.tier, d.rating), [np.nan, np.nan],
            f"{(d.rating == d.tier).sum()}/{len(d)}")

    def pooled(idx):
        d = pd.concat([by_paper.get_group(c) for c in idx if c in by_paper.groups])
        return kw(d.tier, d.rating)
    add("clinicians pooled vs source", len(long), kw(long.tier, long.rating), boot(papers, pooled),
        f"{(long.rating == long.tier).sum()}/{len(long)}")

    pairs = long.sort_values("rater").groupby("code").rating.agg(list)
    pairs = pairs[pairs.str.len() == 2]
    a, b = pairs.str[0], pairs.str[1]

    def between(idx):
        p = pairs.reindex([c for c in idx if c in pairs.index])
        return kw(p.str[0], p.str[1])
    add("clinician vs clinician", len(pairs), kw(a, b), boot(papers, between), f"{(a == b).sum()}/{len(pairs)}")

    for m in MODELS:
        x = papers[m].dropna().astype(int)
        add(f"{m} vs source", len(x), kw(papers.loc[x.index, "tier"], x),
            boot(papers.loc[x.index], lambda idx: kw(papers.loc[idx, "tier"], papers.loc[idx, m].astype(int))),
            f"{(x == papers.loc[x.index, 'tier']).sum()}/{len(x)}")

    diff = boot(papers, lambda idx: kw(papers.loc[idx, "tier"], papers.loc[idx, "claude-opus-4-7"].astype(int)) - pooled(idx))
    k_diff = round(rows[6]["kappa_w"] - rows[4]["kappa_w"], 2)
    add("claude-opus-4-7 minus clinicians pooled", len(papers), k_diff, diff)
    out = pd.DataFrame(rows)
    # clinicians are numbered 1-4 by descending kappa (ties: more ratings first)
    first = out.iloc[:len(RATERS)].sort_values(["kappa_w", "n"], ascending=False, kind="stable").reset_index(drop=True)
    first["comparison"] = [f"clinician {i + 1} vs source" for i in range(len(first))]
    out = pd.concat([first, out.iloc[len(RATERS):]], ignore_index=True)
    print(out.to_string(index=False))
    print("\nrecognition:", long.recognised.value_counts().to_dict())
    print("confidence:", long.confidence.value_counts().to_dict())
    out.to_csv(OUT / "benchmark_summary.csv", index=False)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
