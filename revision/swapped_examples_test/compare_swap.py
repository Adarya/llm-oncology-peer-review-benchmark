"""Swapped-examples test: Claude Opus 4.7 tiers for the 100 manuscripts of sample.csv under the original chief
prompt and under the prompt with swapped example journals; kappa against source tier, paired bootstrap
difference (2,000 resamples, seed 42), tier changes, time and cost per call. Inputs: call logs in
original_examples/ and swapped_examples/. Outputs: swapped_examples_tiers.csv, swapped_examples_summary.txt
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
PROBE = OUT.parent / "venue_probe" / "probe_claude-opus-4-7_original"
LOG_DIR = {"original_examples": OUT / "original_examples", "swapped_examples": OUT / "swapped_examples"}
B = 2000
SEED = 42


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


def load(version: str) -> dict:
    d = {}
    for f in LOG_DIR[version].glob("PMC*.json"):
        if f.name.endswith(".failed.json"):
            continue
        r = json.loads(f.read_text())
        d[r["pmcid"]] = {"tier": r["tier"], "elapsed_s": r["elapsed_s"], "cost_usd": r["total_cost_usd"]}
    return d


def boot_diff(truth, a, b) -> tuple[float, float, float]:
    rng = random.Random(SEED)
    n = len(truth)
    diffs = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        t = [truth[i] for i in idx]
        try:
            diffs.append(qwk(t, [b[i] for i in idx]) - qwk(t, [a[i] for i in idx]))
        except ZeroDivisionError:
            continue
    diffs.sort()
    return qwk(truth, b) - qwk(truth, a), diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


def named_in_probe(pmcid: str, journal: str) -> bool:
    a = json.loads((PROBE / f"{pmcid}.json").read_text()).get("answer")
    return isinstance(a, dict) and a.get("journal_guess") == journal


def main() -> None:
    s = pd.read_csv(OUT / "sample.csv")
    logs = {v: load(v) for v in LOG_DIR}
    for v, res in logs.items():
        s[v] = s.pmcid.map(lambda p: res.get(p, {}).get("tier"))
    d = s.dropna(subset=list(LOG_DIR)).copy()
    for c in ("original_examples", "swapped_examples", "opus_run1_tier", "tier"):
        d[c] = d[c].astype(int)
    d["journal_named_in_probe"] = [named_in_probe(p, j) for p, j in zip(d.pmcid, d.journal_name)]
    d.to_csv(OUT / "swapped_examples_tiers.csv", index=False)
    t = list(d.tier)
    orig, swap = d.original_examples, d.swapped_examples
    diff, lo, hi = boot_diff(t, list(orig), list(swap))
    changed = d[swap != orig]
    lines = [f"Manuscripts with a result under both prompts: {len(d)}/{len(s)} "
             f"(by tier {d.groupby('tier').size().to_dict()})", "",
             "Quadratic weighted kappa vs source tier, same manuscripts:",
             f"  Run 1 of the main analysis: {qwk(t, list(d.opus_run1_tier)):.2f}",
             f"  Original examples         : {qwk(t, list(orig)):.2f}",
             f"  Swapped examples          : {qwk(t, list(swap)):.2f}",
             f"  Swapped minus original: {diff:+.2f} (paired bootstrap 95% CI {lo:+.2f} to {hi:+.2f}, B={B})",
             f"  Exact same tier as source: original {(orig == d.tier).mean():.0%}, swapped {(swap == d.tier).mean():.0%}",
             f"  Same tier under both prompts: {(swap == orig).sum()}/{len(d)}",
             f"  Changes: {len(changed)}; to a lower tier (larger tier number) {(changed.swapped_examples > changed.original_examples).sum()}, "
             f"to a higher tier {(changed.swapped_examples < changed.original_examples).sum()}",
             "  Changes to a lower tier by source tier: "
             + ", ".join(f"tier {k} {v}" for k, v in changed[changed.swapped_examples > changed.original_examples]
                         .groupby("tier").size().reindex([1, 2, 3, 4], fill_value=0).items()),
             f"  Changes by venue-probe result: journal named {int(changed.journal_named_in_probe.sum())}/"
             f"{int(d.journal_named_in_probe.sum())}, not named {int((~changed.journal_named_in_probe).sum())}/"
             f"{int((~d.journal_named_in_probe).sum())}", "",
             "Mean assigned tier by source tier (run 1 / original / swapped):"]
    for tier, g in d.groupby("tier"):
        lines.append(f"  Tier {tier} (n={len(g)}): {g.opus_run1_tier.mean():.2f} / {g.original_examples.mean():.2f} / "
                     f"{g.swapped_examples.mean():.2f}")
    lines.append("\nMean assigned tier by source journal (original -> swapped):")
    for (tier, j), g in d.groupby(["tier", "journal_name"]):
        lines.append(f"  {tier} {j:26s} n={len(g):2d}  {g.original_examples.mean():.2f} -> {g.swapped_examples.mean():.2f}")

    calls = pd.DataFrame([{"version": v, **logs[v][p]} for v in LOG_DIR for p in d.pmcid])
    q = lambda x: np.percentile(x, [25, 50, 75])  # noqa: E731
    lines += ["", f"Time and cost per call ({len(calls)} calls):"]
    for name, g in [("all calls", calls)] + list(calls.groupby("version")):
        (t1, t2, t3), (c1, c2, c3) = q(g.elapsed_s), q(g.cost_usd)
        lines.append(f"  {name:17s} (n={len(g):3d}): time median {t2:.0f} s (IQR {t1:.0f}-{t3:.0f}); "
                     f"cost median US${c2:.2f} (IQR {c1:.2f}-{c3:.2f})")
    txt = "\n".join(lines) + "\n"
    (OUT / "swapped_examples_summary.txt").write_text(txt)
    print(txt, end="")


if __name__ == "__main__":
    main()
