"""Relations between the fields of each model's output (run 1): Spearman correlations of overall quality,
recommendation and specialist scores with tier, and recommendations by predicted and by source tier.
Outputs: results/consistency_quality_vs_tier.csv, recommendation_by_predicted_tier.csv,
recommendation_by_source_tier.csv, subscores_vs_predicted_tier.csv
"""

import pandas as pd
from scipy import stats

from common import LABEL, MODELS, REC_ORDER, analytic_sample, load_runs, save

SUBS = ["meth_score", "meth_stat_score", "clinical_score", "reporting_score", "data_availability_score",
        "novelty_score", "writing_score"]


def main():
    s = analytic_sample()
    L = load_runs()
    L = L[(L.run == 1) & L.pmcid.isin(s.pmcid)].merge(s[["pmcid", "tier"]], on="pmcid")
    L["rec"] = L.recommendation.map(lambda v: str(v).strip().lower() if v is not None else None)
    L["rec_ord"] = L.rec.map(REC_ORDER)

    q, rp, rs, sub = [], [], [], []
    for m in MODELS:
        d = L[L.model == m]
        a = d.dropna(subset=["pred_tier", "quality"])
        b = d.dropna(subset=["pred_tier", "rec_ord"])
        c = d.dropna(subset=["quality"])
        q.append({"model": LABEL[m], "n": len(a),
                  "spearman_quality_vs_predicted_tier": round(stats.spearmanr(a.quality, a.pred_tier)[0], 3),
                  "spearman_recommendation_vs_predicted_tier": round(stats.spearmanr(b.rec_ord, b.pred_tier)[0], 3),
                  "spearman_quality_vs_source_tier": round(stats.spearmanr(c.quality, c.tier)[0], 3),
                  "spearman_quality_vs_recommendation": round(
                      stats.spearmanr(*d.dropna(subset=["quality", "rec_ord"])[["quality", "rec_ord"]].T.values)[0], 3)})
        for col, out in [("pred_tier", rp), ("tier", rs)]:
            t = pd.crosstab(d[col], d.rec, normalize="index").reindex(columns=list(REC_ORDER), fill_value=0) * 100
            n = d.dropna(subset=[col]).groupby(col).size()
            for tier, row in t.iterrows():
                key = "predicted_tier" if col == "pred_tier" else "source_tier"
                out.append({"model": LABEL[m], key: int(tier), "n": int(n.get(tier, 0)),
                            **{f"pct_{k}": round(v, 1) for k, v in row.items()}})
        r = {"model": LABEL[m]}
        for scol in SUBS:
            e = d.dropna(subset=[scol, "pred_tier"])
            r[scol] = round(stats.spearmanr(e[scol], e.pred_tier)[0], 3) if len(e) > 2 else None
        sub.append(r)
    q, rp, rs, sub = map(pd.DataFrame, (q, rp, rs, sub))
    save(q, "consistency_quality_vs_tier.csv")
    save(rp, "recommendation_by_predicted_tier.csv")
    save(rs, "recommendation_by_source_tier.csv")
    save(sub, "subscores_vs_predicted_tier.csv")
    pd.set_option("display.width", 250)
    print(q.to_string(index=False))
    print(rs.to_string(index=False))
    print(rp.to_string(index=False))
    print(sub.to_string(index=False))


if __name__ == "__main__":
    main()
