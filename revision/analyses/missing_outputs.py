"""Missing tier outputs in run 1: list with reasons, counts by source tier, relation to text length,
kappa under complete-case, common-sample, best-case and worst-case handling, and Haiku failures by run.
Outputs: results/missing_outputs_list.csv, missing_outputs_by_tier.csv, missing_outputs_vs_length.csv,
missing_outputs_sensitivity.csv, haiku_failures_across_runs.csv
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from common import LABEL, MODELS, analytic_sample, exact, kappa, load_runs, save, wide, within_one


def reason(row):
    if pd.isna(row.get("run")):
        return "no output file"
    if row["parse_error"]:
        return "file is not valid JSON"
    if not row["has_chief"]:
        return "no chief_reviewer block"
    if pd.isna(row["tier_raw"]) or row["tier_raw"] is None:
        return "tier field missing or null"
    return f"tier value outside 1-4 ({row['tier_raw']!r})"


def main():
    s = analytic_sample()
    L = load_runs()
    w = wide(s, 1)

    miss = []
    for m in MODELS:
        r1 = L[(L.model == m) & (L.run == 1)].set_index("pmcid")
        for _, p in s.iterrows():
            if p.pmcid in r1.index and not pd.isna(r1.loc[p.pmcid, "pred_tier"]):
                continue
            row = r1.loc[p.pmcid].to_dict() if p.pmcid in r1.index else {}
            if p.pmcid in r1.index:
                row["run"] = 1
            miss.append({"model": LABEL[m], "pmcid": p.pmcid, "source_tier": p.tier, "journal": p.journal_name,
                         "blinded_length_chars": p.md_length, "reason": reason(row)})
    miss = pd.DataFrame(miss)
    save(miss, "missing_outputs_list.csv")
    print(miss.groupby(["model", "reason"]).size().to_string())

    bt = (miss.groupby(["model", "source_tier"]).size().unstack(fill_value=0)
          .reindex(columns=[1, 2, 3, 4], fill_value=0))
    bt["total_missing"] = bt.sum(1)
    tot = s.tier.value_counts().sort_index()
    bt.loc["papers in sample"] = list(tot.values) + [len(s)]
    save(bt.reset_index().rename(columns={1: "tier_1", 2: "tier_2", 3: "tier_3", 4: "tier_4"}),
         "missing_outputs_by_tier.csv")
    print(bt.to_string())

    lens = []
    for m in miss.model.unique():
        ids = set(miss[miss.model == m].pmcid)
        f = s[s.pmcid.isin(ids)].md_length
        o = s[~s.pmcid.isin(ids)].md_length
        u = stats.mannwhitneyu(f, o, alternative="two-sided")
        # logistic regression of failure on log length and tier
        X = pd.get_dummies(s.tier.astype(str), prefix="tier", drop_first=True).astype(float)
        X["log_length"] = np.log(s.md_length)
        X = sm.add_constant(X)
        y = s.pmcid.isin(ids).astype(float)
        try:
            fit = sm.Logit(y, X).fit(disp=0)
            orl = float(np.exp(fit.params["log_length"]))
            ci = np.exp(fit.conf_int().loc["log_length"]).to_numpy()
            p_len = float(fit.pvalues["log_length"])
        except Exception as e:  # noqa: BLE001
            orl, ci, p_len = np.nan, [np.nan, np.nan], np.nan
            print("logit failed", m, e)
        chi = stats.chi2_contingency(pd.crosstab(s.tier, s.pmcid.isin(ids)))
        lens.append({"model": m, "n_failed": len(f), "median_length_failed": int(f.median()),
                     "median_length_others": int(o.median()), "mann_whitney_p": round(u.pvalue, 4),
                     "odds_ratio_per_e_fold_length_adjusted_for_tier": round(orl, 2),
                     "or_ci_low": round(ci[0], 2), "or_ci_high": round(ci[1], 2), "or_p": round(p_len, 4),
                     "chi_square_p_failure_vs_tier": round(chi[1], 4)})
    lens = pd.DataFrame(lens)
    save(lens, "missing_outputs_vs_length.csv")
    print(lens.to_string(index=False))

    common = w.dropna(subset=MODELS)
    sens = []
    for m in MODELS:
        d = w[["tier", m]].copy()
        cc = d.dropna()
        worst = d[m].where(d[m].notna(), np.where(d.tier <= 2, 4, 1))
        best = d[m].where(d[m].notna(), d.tier)
        sens.append({"model": LABEL[m], "n_complete_case": len(cc),
                     "kappa_complete_case": round(kappa(cc.tier, cc[m].astype(int)), 3),
                     "n_common_sample": len(common),
                     "kappa_common_sample": round(kappa(common.tier, common[m].astype(int)), 3),
                     "kappa_worst_case_all_485": round(kappa(d.tier, worst.astype(int)), 3),
                     "kappa_best_case_all_485": round(kappa(d.tier, best.astype(int)), 3),
                     "exact_pct_missing_counted_wrong": round(100 * (d[m] == d.tier).mean(), 1),
                     "within_one_pct_missing_counted_wrong": round(100 * ((d[m] - d.tier).abs() <= 1).mean(), 1)})
    sens = pd.DataFrame(sens)
    save(sens, "missing_outputs_sensitivity.csv")
    print(sens.to_string(index=False))

    h = L[L.model == "claude-haiku-4-5"]
    hw = s[["pmcid", "tier"]].copy()
    for r in [1, 2, 3]:
        hr = h[h.run == r].set_index("pmcid").pred_tier
        hw[f"failed_run_{r}"] = hw.pmcid.map(hr).isna()
    hw = hw[hw[[f"failed_run_{r}" for r in [1, 2, 3]]].any(axis=1)]
    save(hw, "haiku_failures_across_runs.csv")
    f1, f2, f3 = (set(hw[hw[f"failed_run_{r}"]].pmcid) for r in [1, 2, 3])
    print(f"Haiku failures: run1 {len(f1)}, run2 {len(f2)}, run3 {len(f3)}; in all three {len(f1 & f2 & f3)}; "
          f"run1 also failing in run2 {len(f1 & f2)}, in run3 {len(f1 & f3)}; any run {len(f1 | f2 | f3)}")


if __name__ == "__main__":
    main()
