"""Data loading, agreement statistics and bootstrap shared by the analysis scripts.
Inputs: results/<model>/<PMCID>/run_<k>.json, manuscript/out/_analytical_sample.csv, corpus_tracker.csv.
The predicted tier is read as in manuscript/analysis/01_build_master_table.py; values outside 1-4 are missing.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RESULTS_OUT = HERE / "results"
REVISION = HERE.parent
ROOT = HERE.parents[1]
RAW = ROOT / "results"
MAIN = ROOT / "manuscript"
DATA = REVISION / "data"

SEED = 42
N_BOOT = 2000
TIERS = np.array([1, 2, 3, 4])

# Order of Table 1.
MODELS = [
    "claude-opus-4-7",
    "gemini-3-flash-preview",
    "claude-sonnet-4-6",
    "gpt-5-5-medium",
    "gpt-5-2-medium",
    "gpt-5-4-mini-medium",
    "claude-haiku-4-5",
]
LABEL = {
    "claude-opus-4-7": "Claude Opus 4.7",
    "gemini-3-flash-preview": "Gemini 3 Flash",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "gpt-5-5-medium": "GPT-5.5 (medium)",
    "gpt-5-2-medium": "GPT-5.2 (medium)",
    "gpt-5-4-mini-medium": "GPT-5.4 mini (medium)",
    "claude-haiku-4-5": "Claude Haiku 4.5",
}
REC_ORDER = {"accept": 1, "minor_revisions": 2, "major_revisions": 3, "reject": 4}


# ---------------------------------------------------------------- loading

def _chief(r: dict) -> dict:
    cr = r.get("chief_reviewer") or {}
    ss = r.get("specialist_scores") or {}
    if isinstance(ss, dict) and "chief_reviewer" in ss and not cr:
        cr = ss.get("chief_reviewer", {})
    return cr if isinstance(cr, dict) else {}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


@lru_cache(maxsize=None)
def load_runs() -> pd.DataFrame:
    """Long table: one row per (model, run, pmcid) for every run file on disk."""
    rows = []
    for model in MODELS:
        for path in sorted((RAW / model).glob("PMC*/run_*.json")):
            run = int(path.stem.split("_")[1])
            rec = {"model": model, "run": run, "pmcid": path.parent.name, "parse_error": False}
            try:
                r = json.loads(path.read_text())
            except json.JSONDecodeError:
                r, rec["parse_error"] = {}, True
            cr = _chief(r)
            tier = _num(cr.get("highest_tier_acceptance"))
            rec["tier_raw"] = cr.get("highest_tier_acceptance")
            rec["pred_tier"] = tier if tier in (1, 2, 3, 4) else np.nan
            q = _num(cr.get("overall_quality_1_10"))
            rec["quality"] = q
            rec["recommendation"] = cr.get("recommendation_at_that_tier")
            rec["hallucination_flag"] = cr.get("predicted_hallucination_flag")
            rec["architecture"] = r.get("architecture")
            rec["model_string_in_output"] = r.get("model")
            rec["timestamp"] = r.get("timestamp")
            rec["has_chief"] = bool(cr)
            ss = r.get("specialist_scores") or {}
            for sec, key, col in [
                ("methodological_rigor", "score", "meth_score"),
                ("methodological_rigor", "statistical_score", "meth_stat_score"),
                ("clinical_relevance_loe", "score", "clinical_score"),
                ("reporting_quality", "score", "reporting_score"),
                ("reporting_quality", "data_availability_score", "data_availability_score"),
                ("novelty_literature", "score", "novelty_score"),
                ("writing_presentation", "score", "writing_score"),
            ]:
                s = ss.get(sec) if isinstance(ss, dict) else None
                rec[col] = _num(s.get(key)) if isinstance(s, dict) else np.nan
            rows.append(rec)
    out = pd.DataFrame(rows)
    if not (out.run > 1).any():
        print("No run-2 or run-3 outputs under results/: unzip outputs_runs_2_3.zip at the repository root.")
    return out


@lru_cache(maxsize=None)
def tracker() -> pd.DataFrame:
    t = pd.read_csv(ROOT / "corpus_tracker.csv")
    return t.drop_duplicates("pmcid").set_index("pmcid")


@lru_cache(maxsize=None)
def analytic_sample() -> pd.DataFrame:
    s = pd.read_csv(MAIN / "out" / "_analytical_sample.csv")
    s["tier"] = s["tier"].astype(int)
    s = s.join(tracker()[["md_length", "pub_date"]], on="pmcid")
    return s.reset_index(drop=True)


@lru_cache(maxsize=None)
def original_records() -> pd.DataFrame:
    """The 496 records with a run-1 output, before the eligibility exclusions."""
    pm = sorted({p.parent.name for p in (RAW / "claude-opus-4-7").glob("PMC*/run_1.json")})
    t = tracker()
    s = t.loc[pm, ["tier", "journal_name", "cancer_domain", "study_type", "md_length"]].reset_index()
    s["tier"] = s["tier"].astype(int)
    return s


def wide(sample: pd.DataFrame, run: int = 1, field: str = "pred_tier") -> pd.DataFrame:
    """sample (pmcid, tier, journal_name, ...) plus one column per model for `field` in `run`."""
    L = load_runs()
    L = L[L.run == run]
    out = sample.copy()
    for m in MODELS:
        s = L[L.model == m].set_index("pmcid")[field]
        out[m] = out.pmcid.map(s)
    return out


# ---------------------------------------------------------------- agreement statistics

def _confusion(a, b, k=4):
    a = np.asarray(a, int) - 1
    b = np.asarray(b, int) - 1
    return np.bincount(a * k + b, minlength=k * k).reshape(k, k).astype(float)


def _weights(kind: str, k=4):
    i, j = np.meshgrid(np.arange(k), np.arange(k), indexing="ij")
    if kind == "quadratic":
        return (i - j) ** 2 / (k - 1) ** 2
    if kind == "linear":
        return np.abs(i - j) / (k - 1)
    return (i != j).astype(float)  # unweighted


def kappa(a, b, weights="quadratic", k=4) -> float:
    """Cohen kappa on labels 1..k (disagreement-weight form; equals sklearn cohen_kappa_score)."""
    O = _confusion(a, b, k)
    n = O.sum()
    E = np.outer(O.sum(1), O.sum(0)) / n
    W = _weights(weights, k)
    den = (W * E).sum()
    return float(1 - (W * O).sum() / den) if den else np.nan


def gwet_ac2(a, b, weights="quadratic", k=4) -> float:
    """Gwet AC2 (AC1 when unweighted) for two raters; Gwet 2014, Handbook of Inter-Rater Reliability."""
    O = _confusion(a, b, k)
    p = O / O.sum()
    w = 1 - _weights(weights, k)  # agreement weights
    pa = (w * p).sum()
    pi = (p.sum(1) + p.sum(0)) / 2
    pe = w.sum() / (k * (k - 1)) * (pi * (1 - pi)).sum()
    return float((pa - pe) / (1 - pe))


def exact(a, b) -> float:
    return float((np.asarray(a) == np.asarray(b)).mean())


def within_one(a, b) -> float:
    return float((np.abs(np.asarray(a, float) - np.asarray(b, float)) <= 1).mean())


# ---------------------------------------------------------------- bootstrap

def paper_indices(n, rng):
    return rng.integers(0, n, n)


def journal_cluster_indices(journal: np.ndarray, tier: np.ndarray, rng):
    """Row indices after resampling journals with replacement within each tier."""
    idx = []
    for t in np.unique(tier):
        js = np.unique(journal[tier == t])
        for j in rng.choice(js, size=len(js), replace=True):
            idx.append(np.flatnonzero((journal == j) & (tier == t)))
    return np.concatenate(idx)


def bootstrap(stat, df: pd.DataFrame, cluster: bool = False, n_boot: int = N_BOOT, seed: int = SEED):
    """Percentile 95% CI of stat(df_resampled). Returns (point, low, high, draws)."""
    rng = np.random.default_rng(seed)
    point = stat(df)
    j = df["journal_name"].to_numpy()
    t = df["tier"].to_numpy()
    draws = np.empty(n_boot)
    for i in range(n_boot):
        ix = journal_cluster_indices(j, t, rng) if cluster else paper_indices(len(df), rng)
        try:
            draws[i] = stat(df.iloc[ix])
        except (ZeroDivisionError, ValueError):
            draws[i] = np.nan
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return float(point), float(lo), float(hi), draws


def save(df: pd.DataFrame, name: str) -> Path:
    RESULTS_OUT.mkdir(exist_ok=True)
    p = RESULTS_OUT / name
    df.to_csv(p, index=False)
    return p
