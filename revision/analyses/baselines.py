"""Prediction of source tier from text features and study labels, without a language model.
Logistic regression and random forest; 5-fold cross-validation stratified by tier (10 repeats, seeds 42-51)
and leave-one-journal-out. Input: revision/data/text_features.csv (rewritten from corpus/normalized/ when present).
Outputs: results/baseline_predictors.csv, results/opus_kappa_within_feature_strata.csv
"""

import re
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from common import DATA, ROOT, analytic_sample, bootstrap, exact, kappa, save, wide, within_one

NORM = ROOT / "corpus" / "normalized"
FEATURES_CSV = DATA / "text_features.csv"
# matmul RuntimeWarnings raised inside scikit-learn (numpy 2.0 with macOS Accelerate)
warnings.filterwarnings("ignore", category=RuntimeWarning)


def features(pmcid: str) -> dict:
    t = (NORM / f"{pmcid}.md").read_text()
    secs = re.split(r"(?m)^## ", t)
    get = lambda name: next((x for x in secs if x.lower().startswith(name)), "")
    refs = get("references")
    figs = get("figures")
    tabs = get("tables")
    body = "\n".join(x for x in secs if not x.lower().startswith(("references", "figures", "tables")))
    return {
        "pmcid": pmcid,
        "length_chars": len(t),
        "body_words": len(body.split()),
        "n_references": len(re.findall(r"(?m)^\s*(?:\[?\d+[\].)]|-)\s+\S", refs)),
        "n_figures": len(re.findall(r"(?m)^\*\*(?:Figure|Fig)", figs)),
        "n_tables": len(re.findall(r"(?m)^\*\*Table", tabs)),
        "nct_number_present": int(bool(re.search(r"NCT\s?\d{8}", t))),
        "randomised_keyword": int(bool(re.search(r"\brandomi[sz]ed\b", t, re.I))),
        "phase_3_keyword": int(bool(re.search(r"\bphase\s*(?:3|III)\b", t, re.I))),
        "multicentre_keyword": int(bool(re.search(r"\bmulti-?(?:cent(?:er|re)|institution(?:al)?)\b", t, re.I))),
    }


NUMERIC = ["length_chars", "body_words", "n_references", "n_figures", "n_tables"]
BINARY = ["nct_number_present", "randomised_keyword", "phase_3_keyword", "multicentre_keyword"]


def design(df, cols, opus=False):
    X = pd.DataFrame(index=df.index)
    for c in cols:
        if c in NUMERIC:
            X[c] = np.log1p(df[c])
        elif c in BINARY:
            X[c] = df[c]
        else:  # categorical
            X = X.join(pd.get_dummies(df[c], prefix=c).astype(float))
    if opus:
        X = X.join(pd.get_dummies(df["opus"].astype(int), prefix="opus_tier").astype(float))
    return X.to_numpy(float)


def cv_predict(model_fn, X, y, seed):
    pred = np.empty_like(y)
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(X, y):
        m = model_fn(seed)
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[te])
        pred[te] = np.clip(np.rint(p @ m.classes_), 1, 4).astype(int)
    return pred


def evaluate(name, model_fn, X, y):
    ks, ex, w1 = [], [], []
    for seed in range(42, 52):
        p = cv_predict(model_fn, X, y, seed)
        ks.append(kappa(y, p)); ex.append(exact(y, p)); w1.append(within_one(y, p))
    return {"predictor": name, "kappa_quadratic_mean": round(np.mean(ks), 3),
            "kappa_min": round(min(ks), 3), "kappa_max": round(max(ks), 3),
            "exact_pct_mean": round(100 * np.mean(ex), 1), "within_one_pct_mean": round(100 * np.mean(w1), 1)}


def evaluate_leave_journal_out(name, model_fn, X, y, journals):
    """Train on 13 journals, predict the held-out journal; repeat for all 14."""
    pred = np.empty_like(y)
    for j in np.unique(journals):
        te = journals == j
        m = model_fn(42)
        m.fit(X[~te], y[~te])
        pred[te] = np.clip(np.rint(m.predict_proba(X[te]) @ m.classes_), 1, 4).astype(int)
    return {"predictor": name, "kappa_quadratic_mean": round(kappa(y, pred), 3), "kappa_min": None,
            "kappa_max": None, "exact_pct_mean": round(100 * exact(y, pred), 1),
            "within_one_pct_mean": round(100 * within_one(y, pred), 1)}


def main():
    s = analytic_sample()
    have_texts = NORM.is_dir() and all((NORM / f"{p}.md").exists() for p in s.pmcid)
    if have_texts:
        f = pd.DataFrame([features(p) for p in s.pmcid])
    else:
        print("corpus/normalized/ not found: reading revision/data/text_features.csv")
        f = pd.read_csv(FEATURES_CSV)[["pmcid"] + NUMERIC + BINARY]
    df = s.merge(f, on="pmcid")
    df["opus"] = wide(s, 1)["claude-opus-4-7"].to_numpy()
    if have_texts:
        df.drop(columns=["title", "doi"], errors="ignore").to_csv(FEATURES_CSV, index=False)
    print(df.groupby("tier")[NUMERIC + BINARY].median().T.to_string())

    y = df.tier.to_numpy()
    logit = lambda seed: make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, C=1.0))
    forest = lambda seed: RandomForestClassifier(n_estimators=500, min_samples_leaf=3, random_state=seed)
    cat = ["study_type", "cancer_domain"]
    rows = [
        evaluate("study type only (logistic)", logit, design(df, ["study_type"]), y),
        evaluate("study type + cancer domain (logistic)", logit, design(df, cat), y),
        evaluate("length and counts only (logistic)", logit, design(df, NUMERIC), y),
        evaluate("all simple features (logistic)", logit, design(df, NUMERIC + BINARY + cat), y),
        evaluate("all simple features (random forest)", forest, design(df, NUMERIC + BINARY + cat), y),
        evaluate("all simple features + Opus tier (logistic)", logit, design(df, NUMERIC + BINARY + cat, opus=True), y),
    ]
    jn = df.journal_name.to_numpy()
    rows += [
        evaluate_leave_journal_out("study type only (logistic), held-out journal", logit, design(df, ["study_type"]), y, jn),
        evaluate_leave_journal_out("all simple features (logistic), held-out journal", logit,
                                   design(df, NUMERIC + BINARY + cat), y, jn),
        evaluate_leave_journal_out("all simple features (random forest), held-out journal", forest,
                                   design(df, NUMERIC + BINARY + cat), y, jn),
    ]
    rows.append({"predictor": "Claude Opus 4.7 alone (no fitting)", "kappa_quadratic_mean": round(kappa(y, df.opus.astype(int)), 3),
                 "kappa_min": None, "kappa_max": None, "exact_pct_mean": round(100 * exact(y, df.opus), 1),
                 "within_one_pct_mean": round(100 * within_one(y, df.opus), 1)})
    out = pd.DataFrame(rows)
    save(out, "baseline_predictors.csv")
    print(out.to_string(index=False))

    strata = []
    df["length_quartile"] = pd.qcut(df.length_chars, 4, labels=["Q1 shortest", "Q2", "Q3", "Q4 longest"])
    df["reference_quartile"] = pd.qcut(df.n_references.rank(method="first"), 4, labels=["Q1 fewest", "Q2", "Q3", "Q4 most"])
    for col in ["length_quartile", "reference_quartile", "nct_number_present", "study_type"]:
        for v, g in df.groupby(col):
            d = g[["tier", "journal_name", "opus"]].rename(columns={"opus": "pred"}).astype({"pred": int})
            if d.tier.nunique() < 2:
                continue
            k, lo, hi, _ = bootstrap(lambda x: kappa(x.tier, x.pred), d)
            c = d.tier.value_counts().reindex([1, 2, 3, 4], fill_value=0)
            strata.append({"stratified_by": col, "stratum": v, "n": len(d), "tier_counts_1_to_4": "/".join(map(str, c)),
                           "opus_kappa": round(k, 3), "ci_low": round(lo, 3), "ci_high": round(hi, 3)})
    strata = pd.DataFrame(strata)
    save(strata, "opus_kappa_within_feature_strata.csv")
    print(strata.to_string(index=False))


if __name__ == "__main__":
    main()
