"""Venue probe: share of the 485 analysed manuscripts whose source journal each model named, with Wilson 95% CIs.
Inputs: call logs in probe_<model>_<text>/, sample_probe.csv. Output: probe_summary.txt
Usage, from the repository root: python revision/venue_probe/probe_summary.py
"""

import ast
import json
import math
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]


def qwk(a, b, k=4) -> float:
    """Quadratic-weighted Cohen kappa for integer labels 1..k."""
    n = len(a)
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x - 1][y - 1] += 1
    ra = [sum(r) for r in obs]
    cb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = lambda i, j: (i - j) ** 2 / (k - 1) ** 2  # noqa: E731
    o = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k)) / n
    e = sum(w(i, j) * ra[i] * cb[j] for i in range(k) for j in range(k)) / n**2
    return 1 - o / e


def wilson(x: int, n: int, z: float = 1.96) -> tuple:
    p = x / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return c - h, c + h


def main() -> None:
    tr = pd.read_csv(ROOT / "corpus_tracker.csv", dtype=str)
    tier_of = tr.drop_duplicates("journal_name").set_index("journal_name").tier.astype(int).to_dict()
    analysed = set(pd.read_csv(ROOT / "manuscript" / "out" / "_analytical_sample.csv").pmcid)
    s = pd.read_csv(OUT / "sample_probe.csv")
    s = s[s.pmcid.isin(analysed)]
    lines = []
    for d in sorted(OUT.glob("probe_*_*")):
        if not d.is_dir():
            continue
        rows = []
        for p, j, t in zip(s.pmcid, s.journal_name, s.tier):
            f = d / f"{p}.json"
            a = json.loads(f.read_text()).get("answer") if f.exists() else None
            if isinstance(a, str):
                try:
                    a = ast.literal_eval(a)
                except (ValueError, SyntaxError):
                    a = None
            if isinstance(a, dict) and a.get("journal_guess") in tier_of:
                rows.append({"hit": a["journal_guess"] == j, "hit2": j in (a["journal_guess"], a.get("second_guess")),
                             "tier": t, "gtier": tier_of[a["journal_guess"]]})
        r = pd.DataFrame(rows)
        if r.empty:
            lines.append(f"{d.name}: 0/{len(s)} valid answers")
            continue
        n, x, x2 = len(r), int(r.hit.sum()), int(r.hit2.sum())
        lo, hi = wilson(x, n)
        alo, ahi = wilson(x, len(s))
        lines.append(f"{d.name}: valid {n}/{len(s)}; exact journal {x}/{n} ({x/n:.0%}, 95% CI {lo:.0%}-{hi:.0%}); "
                     f"in top two {x2}/{n} ({x2/n:.0%}); tier of guess correct {(r.tier == r.gtier).sum()}/{n} "
                     f"({(r.tier == r.gtier).mean():.0%}); kappa_w {qwk(list(r.tier), list(r.gtier)):.2f}; "
                     f"exact journal among all {len(s)} analysed manuscripts {x}/{len(s)} "
                     f"({x/len(s):.0%}, 95% CI {alo:.0%}-{ahi:.0%})")
    txt = "\n".join(lines) + "\n"
    (OUT / "probe_summary.txt").write_text(txt)
    print(txt, end="")


if __name__ == "__main__":
    main()
