"""Agreement with source tier (run 1) for papers whose source journal the model named in the venue probe and
for papers it did not, overall and by source tier; differences with 95% CIs (2,000 resamples within tier, seed 42).
Inputs: revision/venue_probe/probe_<model>_<text>/. Outputs: results/recognition_vs_agreement.csv,
recognition_vs_agreement_differences.csv
"""

from __future__ import annotations

import ast
import json

import numpy as np
import pandas as pd

from common import REVISION, analytic_sample, exact, kappa, save, wide

PROBES = REVISION / "venue_probe"
CHECKS = [("claude-opus-4-7", "original"), ("claude-opus-4-7", "cleaned"), ("claude-sonnet-4-6", "original")]


def probe_answers(model: str, text: str) -> pd.DataFrame:
    rows = []
    for f in sorted((PROBES / f"probe_{model}_{text}").glob("PMC*.json")):
        a = json.loads(f.read_text()).get("answer")
        if isinstance(a, str):
            try:
                a = ast.literal_eval(a)
            except (ValueError, SyntaxError):
                a = None
        if isinstance(a, dict) and a.get("journal_guess"):
            rows.append({"pmcid": f.stem, "guess": a["journal_guess"]})
    return pd.DataFrame(rows, columns=["pmcid", "guess"])


def summarize(d: pd.DataFrame, model: str) -> dict:
    a, b = d.tier.to_numpy(), d[model].to_numpy()
    return {"n": len(d), "kappa_w": kappa(a, b) if len(d) > 1 and len(set(a)) > 1 else np.nan,
            "exact_agreement": exact(a, b), "mean_predicted_tier": float(np.mean(b))}


def diff_ci(d: pd.DataFrame, model: str, stat, n_boot: int = 2000, seed: int = 42):
    """Named minus not named; papers resampled within tier."""
    rng = np.random.default_rng(seed)
    groups = [g.index.to_numpy() for _, g in d.groupby("tier")]

    def f(x):
        y, n = x[x.named], x[~x.named]
        return stat(y.tier.to_numpy(), y[model].to_numpy()) - stat(n.tier.to_numpy(), n[model].to_numpy())

    draws = []
    for _ in range(n_boot):
        ix = np.concatenate([rng.choice(g, len(g)) for g in groups])
        try:
            draws.append(f(d.loc[ix]))
        except (ZeroDivisionError, ValueError):
            pass
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return f(d), lo, hi


def main() -> None:
    w = wide(analytic_sample(), run=1)
    rows, diffs = [], []
    for model, text in CHECKS:
        p = probe_answers(model, text)
        d = w[["pmcid", "tier", "journal_name", model]].merge(p, on="pmcid").dropna(subset=[model])
        d[model] = d[model].astype(int)
        d["named"] = d.guess == d.journal_name
        d = d.reset_index(drop=True)
        for tier in ["all", 1, 2, 3, 4]:
            sub = d if tier == "all" else d[d.tier == tier]
            for named in (True, False):
                g = sub[sub.named == named]
                if len(g):
                    rows.append({"model": model, "probe_text": text, "source_tier": tier,
                                 "journal_named": named, **summarize(g, model)})
        for name, stat in [("exact_agreement", exact), ("kappa_w", kappa)]:
            pt, lo, hi = diff_ci(d, model, stat)
            diffs.append({"model": model, "probe_text": text, "measure": name,
                          "named_minus_not_named": pt, "ci_low": lo, "ci_high": hi,
                          "n_named": int(d.named.sum()), "n_not_named": int((~d.named).sum())})
    out = pd.DataFrame(rows)
    save(out, "recognition_vs_agreement.csv")
    save(pd.DataFrame(diffs), "recognition_vs_agreement_differences.csv")
    with pd.option_context("display.width", 200, "display.max_rows", 100):
        print(out.round(3).to_string(index=False))
        print(pd.DataFrame(diffs).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
