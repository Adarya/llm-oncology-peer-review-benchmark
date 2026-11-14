"""Export tables and figures for one model's outputs to an output directory under the project root.

Usage:
    .venv/bin/python scripts/10_export_prelim_results.py
    .venv/bin/python scripts/10_export_prelim_results.py --model-dir <model> --output-dir <dir>
    .venv/bin/python scripts/10_export_prelim_results.py --model-dir <model> --output-dir <dir> \\
        --compare-with <other model> --compare-output-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

try:
    from scipy import stats as scipy_stats
except ImportError:
    scipy_stats = None  # type: ignore[misc, assignment]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

OUT_DIR = config.PROJECT_ROOT / "prelim_mid_results_18042026"
RUN_ID = 1

try:
    from sklearn.metrics import cohen_kappa_score
except ImportError:
    cohen_kappa_score = None  # type: ignore[misc, assignment]


def _load_merged(model_dir: Path) -> pd.DataFrame:
    tracker = pd.read_csv(config.PROJECT_ROOT / "corpus_tracker.csv", dtype=str).fillna("")
    tracker["tier"] = pd.to_numeric(tracker["tier"], errors="coerce")

    rows = []
    skipped: list[tuple[str, str]] = []
    pattern = f"run_{RUN_ID}.json"
    for p in sorted(model_dir.glob(f"PMC*/{pattern}")):
        pmcid = p.parent.name
        try:
            r = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            skipped.append((pmcid, str(e)[:200]))
            continue
        cr = r.get("chief_reviewer") or {}
        ss = r.get("specialist_scores") or {}

        def g(*path, key=None, default=None):
            cur = ss
            for part in path:
                if not isinstance(cur, dict):
                    return default
                cur = cur.get(part)
            if key is None:
                return cur if cur is not None else default
            if isinstance(cur, dict):
                return cur.get(key, default)
            return default

        rows.append(
            {
                "pmcid": pmcid,
                "model": r.get("model"),
                "architecture": r.get("architecture"),
                "run_id": r.get("run_id"),
                "timestamp": r.get("timestamp"),
                "overall_quality_1_10": cr.get("overall_quality_1_10"),
                "highest_tier_acceptance": cr.get("highest_tier_acceptance"),
                "recommendation_at_that_tier": cr.get("recommendation_at_that_tier"),
                "predicted_hallucination_flag": cr.get("predicted_hallucination_flag"),
                "chief_rationale": cr.get("rationale"),
                "meth_score": g("methodological_rigor", key="score"),
                "meth_stat_score": g("methodological_rigor", key="statistical_score"),
                "clinical_score": g("clinical_relevance_loe", key="score"),
                "loe_oxford": g("clinical_relevance_loe", key="loe_oxford"),
                "reporting_score": g("reporting_quality", key="score"),
                "standard_used": g("reporting_quality", key="standard_used"),
                "data_availability_score": g("reporting_quality", key="data_availability_score"),
                "novelty_score": g("novelty_literature", key="score"),
                "writing_score": g("writing_presentation", key="score"),
            }
        )

    df = pd.DataFrame(rows)
    merged = df.merge(tracker, on="pmcid", how="left", suffixes=("", "_tracker"))
    for c in [
        "overall_quality_1_10",
        "highest_tier_acceptance",
        "meth_score",
        "meth_stat_score",
        "clinical_score",
        "reporting_score",
        "data_availability_score",
        "novelty_score",
        "writing_score",
    ]:
        merged[c] = pd.to_numeric(merged[c], errors="coerce")
    merged["delta_pred_minus_source"] = merged["highest_tier_acceptance"] - merged["tier"]
    merged["_spec_mean_six"] = merged[
        ["meth_score", "meth_stat_score", "clinical_score", "reporting_score", "novelty_score", "writing_score"]
    ].mean(axis=1, skipna=True)
    if skipped:
        try:
            merged.attrs["json_parse_skipped"] = skipped  # type: ignore[attr-defined]
        except AttributeError:
            pass
    return merged


def _spearman_pairs(df: pd.DataFrame) -> pd.DataFrame:
    pairs = [
        ("tier", "overall_quality_1_10", "Source tier", "Overall quality (1–10)"),
        ("tier", "highest_tier_acceptance", "Source tier", "Predicted tier (model)"),
        ("tier", "_spec_mean_six", "Source tier", "Mean specialist score (6 dims)"),
        ("highest_tier_acceptance", "overall_quality_1_10", "Predicted tier", "Overall quality (1–10)"),
        ("_spec_mean_six", "overall_quality_1_10", "Mean specialist score (6 dims)", "Overall quality (1–10)"),
    ]
    rows = []
    for xa, xb, xlab, ylab in pairs:
        a = pd.to_numeric(df[xa], errors="coerce")
        b = pd.to_numeric(df[xb], errors="coerce")
        mask = a.notna() & b.notna()
        if scipy_stats is not None and int(mask.sum()) >= 3:
            rho, p = scipy_stats.spearmanr(a[mask], b[mask])
            rows.append({"x_variable": xlab, "y_variable": ylab, "spearman_rho": rho, "p_value": p, "n": int(mask.sum())})
        else:
            rows.append({"x_variable": xlab, "y_variable": ylab, "spearman_rho": np.nan, "p_value": np.nan, "n": int(mask.sum())})
    return pd.DataFrame(rows)


def _write_derived_summaries(
    df: pd.DataFrame,
    ct: pd.DataFrame,
    ct_row: pd.DataFrame,
    by_tier: pd.DataFrame,
    rec_ct: pd.DataFrame,
    *,
    summary_heading: str,
    coverage_section: str,
    results_model_subdir: str,
) -> None:
    n = len(df)
    oq = df["overall_quality_1_10"]
    pred_vc = df["highest_tier_acceptance"].value_counts().sort_index()
    rec_vc = df["recommendation_at_that_tier"].value_counts()
    arch_vc = df["architecture"].fillna("NA").value_counts()

    spec_means = pd.DataFrame(
        [
            ("methodological_rigor", df["meth_score"].mean()),
            ("statistical_appropriateness", df["meth_stat_score"].mean()),
            ("clinical_translational_relevance", df["clinical_score"].mean()),
            ("reporting_quality", df["reporting_score"].mean()),
            ("data_code_availability", df["data_availability_score"].mean()),
            ("novelty", df["novelty_score"].mean()),
            ("writing_presentation", df["writing_score"].mean()),
        ],
        columns=["dimension", "mean_score"],
    )
    spec_means.to_csv(OUT_DIR / "specialist_dimension_means.csv", index=False)

    pred_tbl = pred_vc.rename_axis("predicted_tier").reset_index(name="count")
    pred_tbl.to_csv(OUT_DIR / "predicted_tier_counts.csv", index=False)

    rec_glob = rec_vc.rename_axis("recommendation").reset_index(name="count")
    rec_glob["fraction_of_papers"] = rec_glob["count"] / n
    rec_glob.to_csv(OUT_DIR / "recommendation_global.csv", index=False)

    rec_row = rec_ct.div(rec_ct.sum(axis=1), axis=0)
    rec_row.to_csv(OUT_DIR / "recommendation_row_fraction_by_source_tier.csv")

    cal = df.groupby("tier")["delta_pred_minus_source"].agg(["mean", "std", "count"]).reset_index()
    cal.columns = ["source_tier", "mean_pred_minus_source", "std_pred_minus_source", "n"]
    cal.to_csv(OUT_DIR / "calibration_delta_pred_minus_source_by_tier.csv", index=False)

    spearman_df = _spearman_pairs(df)
    spearman_df.to_csv(OUT_DIR / "spearman_correlations.csv", index=False)

    hi_ven = df[(df["tier"] <= 2) & (df["highest_tier_acceptance"] >= 4)][
        ["pmcid", "pmid", "journal_name", "tier", "highest_tier_acceptance", "overall_quality_1_10", "title"]
    ].sort_values(["overall_quality_1_10", "pmcid"])
    hi_ven.to_csv(OUT_DIR / "tier_mismatch_high_venue_predicted_tier4plus.csv", index=False)

    lo_ven = df[(df["tier"] >= 3) & (df["highest_tier_acceptance"] <= 2)][
        ["pmcid", "pmid", "journal_name", "tier", "highest_tier_acceptance", "overall_quality_1_10", "title"]
    ].sort_values(["overall_quality_1_10", "pmcid"], ascending=[False, True])
    lo_ven.to_csv(OUT_DIR / "tier_mismatch_low_venue_predicted_tier12.csv", index=False)

    metrics_rows = [
        ("n_papers", str(n), ""),
        ("mean_overall_quality_1_10", f"{oq.mean():.6f}", ""),
        ("std_overall_quality_1_10", f"{oq.std(ddof=1):.6f}", ""),
        ("median_overall_quality_1_10", f"{oq.median():.6f}", ""),
        ("mean_predicted_tier", f"{df['highest_tier_acceptance'].mean():.6f}", ""),
        ("hallucination_flag_count", str(int(df['predicted_hallucination_flag'].eq(True).sum())), ""),
        ("hallucination_flag_rate", f"{df['predicted_hallucination_flag'].eq(True).mean():.6f}", ""),
        ("architecture_single_agent_count", str(int((df['architecture'] == 'single-agent').sum())), ""),
        ("architecture_multi_agent_count", str(int((df['architecture'] == 'multi-agent').sum())), ""),
        (
            "architecture_other_count",
            str(int(((df["architecture"].notna()) & (~df["architecture"].isin(["single-agent", "multi-agent"]))).sum())),
            "non-standard label",
        ),
    ]
    for t, c in pred_vc.items():
        metrics_rows.append((f"predicted_tier_{int(t)}_count", str(int(c)), ""))
    for r, c in rec_vc.items():
        metrics_rows.append((f"recommendation_{r}_count", str(int(c)), f"fraction {c/n:.4f}"))
    pd.DataFrame(metrics_rows, columns=["metric", "value", "note"]).to_csv(OUT_DIR / "metrics_key_value.csv", index=False)

    # --- SUMMARY.md ---
    pred_line = " · ".join(f"{int(k)}: {int(v)}" for k, v in pred_vc.items())
    rec_order = ["accept", "minor_revisions", "major_revisions", "reject"]
    rec_keys = [r for r in rec_order if r in rec_vc.index] + [r for r in rec_vc.index if r not in rec_order]
    rec_line = " · ".join(f"{r}: {int(rec_vc[r])} ({100 * rec_vc[r] / n:.1f}%)" for r in rec_keys)
    loe_vc = df["loe_oxford"].value_counts()
    loe_line = ", ".join(f"{k} {int(loe_vc[k])}" for k in sorted(loe_vc.index, key=str))

    cal_txt = cal.to_string(index=False)
    rho_txt = spearman_df.to_string(index=False, float_format=lambda x: f"{x:.4f}" if pd.notna(x) else "")
    spec_txt = spec_means.to_string(index=False, float_format=lambda x: f"{x:.3f}")

    ct_pct = (ct_row * 100).round(1).to_string()
    row_norm_blurbs = []
    for t in [1, 2, 3, 4]:
        if t not in ct_row.index:
            continue
        row = ct_row.loc[t]
        parts = [f"{int(col)}: {100 * row[col]:.1f}%" for col in ct_row.columns if row[col] > 0]
        row_norm_blurbs.append(f"- **Source tier {t}** → predicted tier mix (% of row): {', '.join(parts)}")

    md = f"""# {summary_heading}

**Cohort:** `results/{results_model_subdir}/*/run_{RUN_ID}.json` merged with `corpus_tracker.csv` (source journal tier and metadata).

**Generated:** this file is produced by `scripts/10_export_prelim_results.py` — re-run to refresh after new JSONs land.

---

## 1. Headline outcomes

| Quantity | Value |
|----------|-------|
| *n* papers | {n} |
| Mean overall quality (1–10) | {oq.mean():.2f} (SD {oq.std(ddof=1):.2f}; median {oq.median():.0f}) |
| Model highest tier acceptance (1–4) | {pred_line} |
| Recommendation | {rec_line} |
| `predicted_hallucination_flag` | {int(df["predicted_hallucination_flag"].eq(True).sum())} / {n} ({100 * df["predicted_hallucination_flag"].eq(True).mean():.1f}%) |
| `architecture` | single-agent {int((df["architecture"] == "single-agent").sum())}, multi-agent {int((df["architecture"] == "multi-agent").sum())} (prompt specifies multi-agent; treat as metadata drift) |

Overall quality is clustered around mid scores (histogram: `fig07_overall_quality_histogram.pdf`). Very few `accept` recommendations at the model-assigned tier.

---

## 2. Specialist rubric (means on 1–5)

```
{spec_txt}
```

Oxford LoE counts (clinical specialist): {loe_line}. Detail: `loe_counts.csv`.

Lowest mean in this table is typically **data/code availability**; highest is often **writing/presentation**. Interpret cautiously (true absence in blinded text vs. model conservatism).

---

## 3. By source journal tier (design bins)

```
{cal_txt}
```

`summary_by_source_tier.csv` — per-tier *n*, means, hallucination rate.

**Calibration:** mean (predicted tier − source tier) by source tier is in `calibration_delta_pred_minus_source_by_tier.csv`.

**Recommendation row fractions:** `recommendation_row_fraction_by_source_tier.csv` (from `recommendation_crosstab_by_source_tier.csv`).

---

## 4. Tier confusion (source tier × predicted tier)

**Counts:** `tier_confusion_counts.csv`  
**Row fraction:** `tier_confusion_row_fraction.csv`  
**Figure:** `fig01_tier_confusion_rowpct.pdf`, `fig02_tier_confusion_counts.pdf`

Row-normalized (% of each source tier):

```
{ct_pct}
```

{chr(10).join(row_norm_blurbs)}

---

## 5. Associations (Spearman)

Requires SciPy (`scipy`). If missing, `spearman_rho` is NaN.

```
{rho_txt}
```

Machine-readable: `spearman_correlations.csv`.

---

## 6. Tier “mismatches” (for spot checks)

| Pattern | *n* | CSV |
|---------|-----|-----|
| Source tier 1–2, model predicted tier ≥ 4 | {len(hi_ven)} | `tier_mismatch_high_venue_predicted_tier4plus.csv` |
| Source tier 3–4, model predicted tier ≤ 2 | {len(lo_ven)} | `tier_mismatch_low_venue_predicted_tier12.csv` |

---

## 7. Coverage

{coverage_section}

---

## 8. Other artifacts

- Per-paper table: `eval_per_paper.csv`
- Hallucination-flagged subset: `hallucination_flagged_papers.csv`, `fig09_hallucination_flagged_papers.pdf`
- Scalar metrics (long): `metrics_key_value.csv`
- Legacy one-row summary: `summary_global.csv`

---

## Interpretive notes (not re-derived here)

Strong alignment between **source tier** and model scores under blinded text invites interpretation (residual quality signal vs. subtle leakage). Stress-test with QA fields (`journal_hits`, `id_hits`, … in tracker) and manual reads. Chief `architecture` field should not be used as evidence of pipeline mode without post-processing.
"""
    (OUT_DIR / "SUMMARY.md").write_text(md, encoding="utf-8")


def _style_rc() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "axes.linewidth": 1.0,
            "xtick.major.width": 1.0,
            "ytick.major.width": 1.0,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
        }
    )


def _save_both(fig: plt.Figure, stem: str) -> None:
    for ext in ("pdf", "png"):
        fig.savefig(OUT_DIR / f"{stem}.{ext}", facecolor="white", edgecolor="none")


def fig_confusion_norm(ct_row: pd.DataFrame) -> None:
    _style_rc()
    arr = ct_row.values.astype(float)
    fig, ax = plt.subplots(figsize=(3.4, 3.0), layout="constrained")
    im = ax.imshow(arr, cmap="Blues", vmin=0, vmax=100, aspect="equal")
    ax.set_xticks(range(4), labels=[str(i) for i in range(1, 5)])
    ax.set_yticks(range(4), labels=[str(i) for i in range(1, 5)])
    ax.set_xlabel("Model tier (predicted)")
    ax.set_ylabel("Source tier (journal bin)")
    ax.set_title("Tier alignment (row %)")
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            ax.text(j, i, f"{arr[i, j]:.0f}", ha="center", va="center", color="black", fontsize=11)
    cbar = fig.colorbar(im, ax=ax, shrink=0.82, pad=0.02)
    cbar.set_label("% of source tier", fontsize=10)
    _save_both(fig, "fig01_tier_confusion_rowpct")
    plt.close(fig)


def fig_confusion_counts(ct: pd.DataFrame) -> None:
    _style_rc()
    arr = ct.values.astype(float)
    fig, ax = plt.subplots(figsize=(3.4, 3.0), layout="constrained")
    im = ax.imshow(arr, cmap="Oranges", aspect="equal")
    ax.set_xticks(range(4), labels=[str(i) for i in range(1, 5)])
    ax.set_yticks(range(4), labels=[str(i) for i in range(1, 5)])
    ax.set_xlabel("Model tier (predicted)")
    ax.set_ylabel("Source tier (journal bin)")
    ax.set_title("Tier confusion (counts)")
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            ax.text(j, i, f"{int(arr[i, j])}", ha="center", va="center", color="black", fontsize=11)
    cbar = fig.colorbar(im, ax=ax, shrink=0.82, pad=0.02)
    cbar.set_label("Papers", fontsize=10)
    _save_both(fig, "fig02_tier_confusion_counts")
    plt.close(fig)


def fig_overall_by_tier(df: pd.DataFrame) -> None:
    _style_rc()
    data = [df.loc[df["tier"] == t, "overall_quality_1_10"].dropna() for t in [1, 2, 3, 4]]
    fig, ax = plt.subplots(figsize=(3.6, 3.0), layout="constrained")
    bp = ax.boxplot(
        data,
        tick_labels=["1", "2", "3", "4"],
        widths=0.55,
        patch_artist=True,
        medianprops={"color": "black", "linewidth": 1.5},
        boxprops={"facecolor": "#b3cde3", "edgecolor": "black", "linewidth": 1.0},
        whiskerprops={"linewidth": 1.0},
        capprops={"linewidth": 1.0},
        flierprops={"markersize": 3, "markerfacecolor": "0.35"},
    )
    ax.set_xlabel("Source journal tier")
    ax.set_ylabel("Overall quality (1–10)")
    ax.set_title("Chief overall score by source tier")
    ax.set_ylim(0.5, 10.5)
    _save_both(fig, "fig03_overall_quality_by_source_tier")
    plt.close(fig)


def fig_specialist_means(df: pd.DataFrame) -> None:
    _style_rc()
    cols = {
        "meth_score": "Methodological",
        "meth_stat_score": "Statistical",
        "clinical_score": "Clinical",
        "reporting_score": "Reporting",
        "data_availability_score": "Data availability",
        "novelty_score": "Novelty",
        "writing_score": "Writing",
    }
    means = df[list(cols.keys())].mean()
    labels = [cols[k] for k in means.index]
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(4.0, 2.8), layout="constrained")
    ax.barh(y, means.values, height=0.65, color="#6baed6", edgecolor="black", linewidth=0.8)
    ax.set_yticks(y, labels=labels)
    ax.set_xlabel("Mean specialist score (1–5)")
    ax.set_title("Mean rubric subscores")
    ax.set_xlim(1.0, 4.0)
    ax.axvline(3.0, color="0.5", linestyle="--", linewidth=0.8)
    _save_both(fig, "fig04_specialist_dimension_means")
    plt.close(fig)


def fig_recommendation_stacked(df: pd.DataFrame) -> None:
    _style_rc()
    order = ["accept", "minor_revisions", "major_revisions", "reject"]
    ct = pd.crosstab(df["tier"], df["recommendation_at_that_tier"], normalize="index") * 100
    ct = ct.reindex(columns=[c for c in order if c in ct.columns], fill_value=0)
    tiers = [1, 2, 3, 4]
    present = [t for t in tiers if t in ct.index]
    ct = ct.reindex(present, fill_value=0)
    colors = ["#31a354", "#a1d99b", "#fd8d3c", "#e34a33"]
    fig, ax = plt.subplots(figsize=(3.5, 2.9), layout="constrained")
    left = np.zeros(len(ct))
    x = np.arange(len(ct))
    for i, col in enumerate(ct.columns):
        ax.bar(x, ct[col].values, bottom=left, label=col.replace("_", " "), color=colors[i], edgecolor="black", linewidth=0.5)
        left = left + ct[col].values
    ax.set_xticks(x, [str(t) for t in ct.index])
    ax.set_xlabel("Source journal tier")
    ax.set_ylabel("Percent within tier")
    ax.set_title("Recommendation mix")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0, frameon=False, fontsize=9)
    ax.set_ylim(0, 100)
    _save_both(fig, "fig05_recommendation_by_source_tier")
    plt.close(fig)


def fig_predicted_tier_counts(df: pd.DataFrame) -> None:
    _style_rc()
    vc = df["highest_tier_acceptance"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(3.3, 2.7), layout="constrained")
    x = [str(int(i)) for i in vc.index]
    ax.bar(x, vc.values, color="#9ecae1", edgecolor="black", linewidth=0.8)
    ax.set_xlabel("Model-assigned tier")
    ax.set_ylabel("Count")
    ax.set_title("Predicted highest acceptance tier")
    _save_both(fig, "fig06_predicted_tier_counts")
    plt.close(fig)


def fig_overall_hist(df: pd.DataFrame) -> None:
    _style_rc()
    fig, ax = plt.subplots(figsize=(3.5, 2.7), layout="constrained")
    ax.hist(
        df["overall_quality_1_10"].dropna(),
        bins=np.arange(0.5, 10.6, 1),
        color="#bcbddc",
        edgecolor="black",
        linewidth=0.8,
    )
    ax.set_xlabel("Overall quality (1–10)")
    ax.set_ylabel("Count")
    ax.set_title("Chief overall quality")
    ax.set_xticks(range(1, 10))
    _save_both(fig, "fig07_overall_quality_histogram")
    plt.close(fig)


def build_hallucination_flagged_table(df: pd.DataFrame, model_dir: Path) -> pd.DataFrame:
    """Rows where chief `predicted_hallucination_flag` is true; enrich from JSON + tracker."""
    flagged = df[df["predicted_hallucination_flag"].eq(True)].copy()
    if flagged.empty:
        return pd.DataFrame(
            columns=[
                "pmcid",
                "pmid",
                "doi",
                "journal_name",
                "tier",
                "title",
                "study_type",
                "cancer_domain",
                "overall_quality_1_10",
                "highest_tier_acceptance",
                "recommendation_at_that_tier",
                "chief_rationale",
                "key_concerns",
            ]
        )

    extra = []
    for pmcid in flagged["pmcid"].tolist():
        path = model_dir / pmcid / f"run_{RUN_ID}.json"
        r = json.loads(path.read_text())
        cr = r.get("chief_reviewer") or {}
        concerns = cr.get("key_concerns") or []
        extra.append(
            {
                "pmcid": pmcid,
                "chief_rationale": cr.get("rationale", ""),
                "key_concerns": " | ".join(str(x) for x in concerns),
            }
        )
    ex = pd.DataFrame(extra)
    base_cols = [
        "pmcid",
        "pmid",
        "doi",
        "journal_name",
        "tier",
        "title",
        "study_type",
        "cancer_domain",
        "overall_quality_1_10",
        "highest_tier_acceptance",
        "recommendation_at_that_tier",
    ]
    out = flagged[base_cols].merge(ex, on="pmcid", how="left")
    return out.sort_values(["tier", "journal_name", "pmcid"]).reset_index(drop=True)


def fig_hallucination_flagged(hall_df: pd.DataFrame) -> None:
    """Compact bar chart: flagged papers (overall quality); labels = PMCID + venue."""
    if hall_df.empty:
        return
    _style_rc()
    d = hall_df.sort_values(["tier", "overall_quality_1_10", "pmcid"], ascending=[True, False, True])
    n = len(d)
    y = np.arange(n)
    tiers = d["tier"].fillna(0).astype(int)
    colors = {1: "#3182bd", 2: "#6baed6", 3: "#fc9272", 4: "#cb181d"}
    bar_colors = [colors.get(int(t), "#636363") for t in tiers]

    fig, ax = plt.subplots(figsize=(4.0, 0.55 * n + 1.0), layout="constrained")
    ax.barh(y, d["overall_quality_1_10"].astype(float), height=0.62, color=bar_colors, edgecolor="black", linewidth=0.7)
    ax.set_yticks(y)
    labs = []
    for _, r in d.iterrows():
        j = str(r["journal_name"])[:22] + ("…" if len(str(r["journal_name"])) > 22 else "")
        labs.append(f"{r['pmcid']}\n{j}")
    ax.set_yticklabels(labs, fontsize=9)
    ax.set_xlabel("Overall quality (1–10)")
    ax.set_title(f"Chief `predicted_hallucination_flag` (n={n})")
    ax.set_xlim(0, 10.5)
    ax.invert_yaxis()
    leg = [
        Patch(facecolor=colors[t], edgecolor="black", label=f"Source tier {t}")
        for t in sorted(d["tier"].dropna().unique().astype(int))
    ]
    ax.legend(handles=leg, loc="lower right", frameon=False, fontsize=8)
    _save_both(fig, "fig09_hallucination_flagged_papers")
    plt.close(fig)


def fig_loe_counts(df: pd.DataFrame) -> None:
    _style_rc()
    vc = df["loe_oxford"].fillna("NA").value_counts()
    # Oxford order
    loe_order = ["1a", "1b", "2a", "2b", "3a", "3b", "4", "5", "NA"]
    vc = vc.reindex([x for x in loe_order if x in vc.index])
    fig, ax = plt.subplots(figsize=(4.2, 2.6), layout="constrained")
    y = np.arange(len(vc))
    ax.barh(y, vc.values, height=0.65, color="#fdae6b", edgecolor="black", linewidth=0.7)
    ax.set_yticks(y, labels=list(vc.index))
    ax.set_xlabel("Count")
    ax.set_title("Oxford LoE (clinical specialist)")
    _save_both(fig, "fig08_loe_distribution")
    plt.close(fig)


def _save_cross_fig(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    fig.savefig(out_dir / f"{stem}.pdf", facecolor="white", edgecolor="none", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(out_dir / f"{stem}.png", facecolor="white", edgecolor="none", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def _cross_model_subset(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
    cols = [
        "pmcid",
        "overall_quality_1_10",
        "highest_tier_acceptance",
        "recommendation_at_that_tier",
        "predicted_hallucination_flag",
        "meth_score",
        "meth_stat_score",
        "clinical_score",
        "reporting_score",
        "data_availability_score",
        "novelty_score",
        "writing_score",
    ]
    sub = df[[c for c in cols if c in df.columns]].copy()
    ren = {c: f"{c}_{suffix}" for c in sub.columns if c != "pmcid"}
    return sub.rename(columns=ren)


def write_cross_model_compare(
    model_dir_a: Path,
    model_dir_b: Path,
    out_dir: Path,
    label_a: str,
    label_b: str,
) -> None:
    """Join two result trees on pmcid; write CSVs + agreement / Bland–Altman figures."""
    out_dir.mkdir(parents=True, exist_ok=True)
    df_a = _load_merged(model_dir_a)
    df_b = _load_merged(model_dir_b)
    if df_a.empty or df_b.empty:
        print("Cross-model compare: one model has no JSON; skipping.")
        return

    ta = _cross_model_subset(df_a, "a")
    tb = _cross_model_subset(df_b, "b")
    m = ta.merge(tb, on="pmcid", how="inner")
    n = len(m)
    if n == 0:
        print("Cross-model compare: no overlapping PMCIDs; skipping.")
        return

    tracker = pd.read_csv(config.PROJECT_ROOT / "corpus_tracker.csv", dtype=str).fillna("")
    tracker["tier"] = pd.to_numeric(tracker["tier"], errors="coerce")
    keep_tr = ["pmcid", "tier", "journal_name", "title", "study_type"]
    m = m.merge(tracker[[c for c in keep_tr if c in tracker.columns]], on="pmcid", how="left")

    m["delta_overall_a_minus_b"] = m["overall_quality_1_10_a"] - m["overall_quality_1_10_b"]
    m["delta_pred_tier_a_minus_b"] = m["highest_tier_acceptance_a"] - m["highest_tier_acceptance_b"]
    m["exact_pred_tier_agree"] = m["highest_tier_acceptance_a"] == m["highest_tier_acceptance_b"]
    m["exact_recommendation_agree"] = m["recommendation_at_that_tier_a"] == m["recommendation_at_that_tier_b"]
    m["both_hallucination_flag"] = m["predicted_hallucination_flag_a"].eq(True) & m["predicted_hallucination_flag_b"].eq(
        True
    )
    m["any_hallucination_flag"] = m["predicted_hallucination_flag_a"].eq(True) | m["predicted_hallucination_flag_b"].eq(
        True
    )

    m.to_csv(out_dir / "cross_per_paper.csv", index=False)

    ct_pred = pd.crosstab(
        m["highest_tier_acceptance_a"],
        m["highest_tier_acceptance_b"],
        rownames=[f"pred_tier_{label_a}"],
        colnames=[f"pred_tier_{label_b}"],
    )
    ct_pred = ct_pred.reindex(index=[1, 2, 3, 4], columns=[1, 2, 3, 4], fill_value=0)
    ct_pred.to_csv(out_dir / "cross_pred_tier_confusion_counts.csv")

    ct_rec = pd.crosstab(m["recommendation_at_that_tier_a"], m["recommendation_at_that_tier_b"])
    ct_rec.to_csv(out_dir / "cross_recommendation_crosstab.csv")

    oa = m["overall_quality_1_10_a"].astype(float)
    ob = m["overall_quality_1_10_b"].astype(float)
    mean_om = (oa + ob) / 2.0
    diff_o = oa - ob
    pa = m["highest_tier_acceptance_a"].astype(int)
    pb = m["highest_tier_acceptance_b"].astype(int)

    pearson_r = np.nan
    spear_r = np.nan
    if scipy_stats is not None and n >= 3:
        pearson_r, _ = scipy_stats.pearsonr(oa, ob)
        spear_r, _ = scipy_stats.spearmanr(oa, ob)

    kappa_tier_q = np.nan
    kappa_rec = np.nan
    if cohen_kappa_score is not None:
        try:
            kappa_tier_q = float(cohen_kappa_score(pa, pb, weights="quadratic"))
        except Exception:  # noqa: BLE001
            pass
        try:
            kappa_rec = float(
                cohen_kappa_score(
                    m["recommendation_at_that_tier_a"].astype(str),
                    m["recommendation_at_that_tier_b"].astype(str),
                )
            )
        except Exception:  # noqa: BLE001
            pass

    mdiff = float(diff_o.mean())
    sdiff = float(diff_o.std(ddof=1))
    lo_loa = mdiff - 1.96 * sdiff
    hi_loa = mdiff + 1.96 * sdiff

    spec_cols = [
        ("meth_score", "meth"),
        ("meth_stat_score", "meth_stat"),
        ("clinical_score", "clinical"),
        ("reporting_score", "reporting"),
        ("data_availability_score", "data_avail"),
        ("novelty_score", "novelty"),
        ("writing_score", "writing"),
    ]
    spec_rows = [{"metric": "n_paired_papers", "value": str(n), "note": f"{label_a} x {label_b}"}]
    for col, short in spec_cols:
        ca, cb = f"{col}_a", f"{col}_b"
        if ca in m.columns and cb in m.columns:
            d = m[ca].astype(float) - m[cb].astype(float)
            spec_rows.append(
                {
                    "metric": f"mean_diff_{short}_{label_a}_minus_{label_b}",
                    "value": f"{d.mean():.4f}",
                    "note": "",
                }
            )

    summary_rows = [
        ("n_paired_papers", int(n), ""),
        ("mean_overall_quality_" + label_a, float(oa.mean()), ""),
        ("mean_overall_quality_" + label_b, float(ob.mean()), ""),
        ("pearson_r_overall", pearson_r, ""),
        ("spearman_rho_overall", spear_r, ""),
        ("mean_abs_delta_overall", float(diff_o.abs().mean()), ""),
        ("mean_delta_overall_a_minus_b", mdiff, ""),
        ("sd_delta_overall", sdiff, ""),
        ("bland_altman_loa_low", lo_loa, ""),
        ("bland_altman_loa_high", hi_loa, ""),
        ("exact_agreement_pred_tier_frac", float(m["exact_pred_tier_agree"].mean()), ""),
        ("exact_agreement_recommendation_frac", float(m["exact_recommendation_agree"].mean()), ""),
        (
            "cohens_kappa_pred_tier_quadratic",
            kappa_tier_q,
            "" if cohen_kappa_score is not None and pd.notna(kappa_tier_q) else "needs scikit-learn",
        ),
        (
            "cohens_kappa_recommendation",
            kappa_rec,
            "" if cohen_kappa_score is not None and pd.notna(kappa_rec) else "needs scikit-learn",
        ),
        ("both_hallucination_flag_count", int(m["both_hallucination_flag"].sum()), ""),
        ("any_hallucination_flag_count", int(m["any_hallucination_flag"].sum()), ""),
    ]
    pd.DataFrame(summary_rows, columns=["metric", "value", "note"]).to_csv(out_dir / "cross_summary_metrics.csv", index=False)
    pd.DataFrame(spec_rows).to_csv(out_dir / "cross_specialist_mean_deltas.csv", index=False)

    # --- Figures ---
    _style_rc()
    fig, ax = plt.subplots(figsize=(3.6, 3.5), layout="constrained")
    ax.scatter(ob, oa, alpha=0.35, s=12, edgecolors="0.3", linewidths=0.3, c="#3182bd")
    lim = 0.5, 10.5
    ax.plot(lim, lim, "k--", linewidth=1, label="Identity")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(f"Overall quality — {label_b}")
    ax.set_ylabel(f"Overall quality — {label_a}")
    ax.set_title("Chief overall score (paired)")
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    _save_cross_fig(fig, out_dir, "cross_fig01_scatter_overall")

    fig, ax = plt.subplots(figsize=(3.8, 3.0), layout="constrained")
    ax.scatter(mean_om, diff_o, alpha=0.35, s=12, edgecolors="0.3", linewidths=0.3, c="#756bb1")
    ax.axhline(mdiff, color="0.2", linewidth=1.2, label=f"Mean Δ {mdiff:.2f}")
    ax.axhline(lo_loa, color="0.5", linestyle="--", linewidth=0.9, label="±1.96 SD")
    ax.axhline(hi_loa, color="0.5", linestyle="--", linewidth=0.9)
    ax.set_xlabel(f"Mean overall ({label_a} & {label_b})")
    ax.set_ylabel(f"Δ overall ({label_a} − {label_b})")
    ax.set_title("Bland–Altman: overall quality")
    ax.legend(loc="upper right", fontsize=7, frameon=False)
    _save_cross_fig(fig, out_dir, "cross_fig02_bland_altman_overall")

    arr = ct_pred.values.astype(float)
    fig, ax = plt.subplots(figsize=(3.5, 3.1), layout="constrained")
    im = ax.imshow(arr, cmap="Purples", aspect="equal")
    ax.set_xticks(range(4), labels=["1", "2", "3", "4"])
    ax.set_yticks(range(4), labels=["1", "2", "3", "4"])
    ax.set_xlabel(f"Predicted tier — {label_b}")
    ax.set_ylabel(f"Predicted tier — {label_a}")
    ax.set_title("Cross-model predicted tier (counts)")
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{int(arr[i, j])}", ha="center", va="center", color="black", fontsize=9)
    fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    _save_cross_fig(fig, out_dir, "cross_fig03_pred_tier_confusion_counts")

    fig, ax = plt.subplots(figsize=(3.5, 2.8), layout="constrained")
    ax.hist(diff_o, bins=np.arange(-5.5, 6.5, 1), color="#9ebcda", edgecolor="black", linewidth=0.7)
    ax.axvline(0, color="0.3", linestyle="-", linewidth=1)
    ax.set_xlabel(f"Δ overall ({label_a} − {label_b})")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of overall-score difference")
    _save_cross_fig(fig, out_dir, "cross_fig04_delta_overall_histogram")

    na, nb = len(df_a), len(df_b)
    gap_note = ""
    if n < min(na, nb):
        gap_note = (
            f"\n**Coverage:** `{label_a}` *n*={na}, `{label_b}` *n*={nb} — paired rows use intersection only "
            f"({n} papers). Re-parse or re-run eval for invalid JSON if you need full *n*.\n\n"
        )
    md_lines = [
        f"# Cross-model comparison (automated)\n",
        f"**Pair:** `{label_a}` (columns suffix `_a`, y-axes where noted) vs `{label_b}` (`_b`).\n",
        f"**Paired *n*:** {n}\n",
        gap_note,
        "## Summary\n\n",
        f"- Pearson *r* (overall): {pearson_r:.4f}\n" if pd.notna(pearson_r) else "",
        f"- Spearman ρ (overall): {spear_r:.4f}\n" if pd.notna(spear_r) else "",
        f"- Mean Δ overall ({label_a} − {label_b}): {mdiff:.3f} (SD {sdiff:.3f})\n",
        f"- Bland–Altman 95% LoA: [{lo_loa:.2f}, {hi_loa:.2f}]\n",
        f"- Exact agreement (predicted tier): {100 * m['exact_pred_tier_agree'].mean():.1f}%\n",
        f"- Exact agreement (recommendation): {100 * m['exact_recommendation_agree'].mean():.1f}%\n",
    ]
    if cohen_kappa_score is not None and pd.notna(kappa_tier_q):
        md_lines.append(f"- Cohen's κ (pred tier, quadratic): {kappa_tier_q:.4f}\n")
    elif cohen_kappa_score is None:
        md_lines.append("- Cohen's κ (tier): install `scikit-learn` to compute\n")
    if cohen_kappa_score is not None and pd.notna(kappa_rec):
        md_lines.append(f"- Cohen's κ (recommendation): {kappa_rec:.4f}\n")
    elif cohen_kappa_score is None:
        md_lines.append("- Cohen's κ (recommendation): install `scikit-learn` to compute\n")
    md_lines.extend(
        [
            "\n## Files\n\n",
            "- `cross_per_paper.csv` — paired scores per PMCID\n",
            "- `cross_summary_metrics.csv` — scalar agreement stats\n",
            "- `cross_pred_tier_confusion_counts.csv` — tier × tier counts\n",
            "- `cross_recommendation_crosstab.csv`\n",
            "- `cross_specialist_mean_deltas.csv` — mean specialist score differences\n",
            "- Figures `cross_fig01` … `cross_fig04`\n",
        ]
    )
    (out_dir / "CROSS_SUMMARY.md").write_text("".join(md_lines), encoding="utf-8")

    print(f"Wrote cross-model tables + figures to {out_dir}")


def main() -> None:
    global OUT_DIR

    ap = argparse.ArgumentParser(description="Export eval CSVs, SUMMARY.md, and figures for one model tree.")
    ap.add_argument(
        "--model-dir",
        default="claude-opus-4-7",
        help="Subdirectory under results/ containing PMC*/run_<id>.json (default: claude-opus-4-7).",
    )
    ap.add_argument(
        "--output-dir",
        default="prelim_mid_results_18042026",
        help="Output directory name under project root (default: prelim_mid_results_18042026).",
    )
    ap.add_argument(
        "--compare-with",
        default=None,
        help="Optional second model subdirectory under results/ for paired agreement + Bland–Altman.",
    )
    ap.add_argument(
        "--compare-output-dir",
        default="prelim_cross_opus_haiku_18042026",
        help="Where to write cross-model CSVs/figures when --compare-with is set.",
    )
    args = ap.parse_args()
    OUT_DIR = (config.PROJECT_ROOT / args.output_dir).resolve()
    model_path = (config.PROJECT_ROOT / "results" / args.model_dir).resolve()

    _tr = pd.read_csv(config.PROJECT_ROOT / "corpus_tracker.csv", dtype=str).fillna("")
    eligible_n = int((_tr["md_exists"] == "True").sum())
    _on = Path(args.output_dir).name
    fullish = "all_results" in _on or "haiku_all" in _on or "gemini_all" in _on

    summary_heading = f"`{args.model_dir}` — results summary (automated)"
    if fullish:
        coverage_section = (
            f"Finished counts by journal: `summary_by_journal.csv`. "
            f"Target eligible *n* (md_exists): **{eligible_n}**."
        )
    else:
        coverage_section = (
            "Finished counts by journal: `summary_by_journal.csv`. "
            "Partial runs may over-represent some journals until the full eligible set is evaluated."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = _load_merged(model_path)
    _attrs = getattr(df, "attrs", None)
    skipped_json = list(_attrs.pop("json_parse_skipped", [])) if _attrs is not None else []
    if skipped_json:
        pd.DataFrame(skipped_json, columns=["pmcid", "error"]).to_csv(OUT_DIR / "json_parse_skipped.csv", index=False)
        print(f"Warning: skipped {len(skipped_json)} invalid JSON files → {OUT_DIR / 'json_parse_skipped.csv'}")
    if df.empty:
        print("No JSON results found; aborting.")
        return

    # --- CSV exports ---
    keep_cols = [c for c in df.columns if c not in ("chief_rationale",)]
    rationale_path = OUT_DIR / "eval_per_paper_rationale.csv"
    df[["pmcid", "chief_rationale"]].to_csv(rationale_path, index=False)
    df[keep_cols].to_csv(OUT_DIR / "eval_per_paper.csv", index=False)

    ct = pd.crosstab(df["tier"], df["highest_tier_acceptance"])
    ct = ct.reindex(index=[1, 2, 3, 4], columns=[1, 2, 3, 4], fill_value=0)
    ct.to_csv(OUT_DIR / "tier_confusion_counts.csv")
    ct_row = ct.div(ct.sum(axis=1), axis=0)
    ct_row.to_csv(OUT_DIR / "tier_confusion_row_fraction.csv")

    by_tier = (
        df.groupby("tier", dropna=False)
        .agg(
            n=("pmcid", "count"),
            overall_mean=("overall_quality_1_10", "mean"),
            overall_std=("overall_quality_1_10", "std"),
            pred_tier_mean=("highest_tier_acceptance", "mean"),
            meth_mean=("meth_score", "mean"),
            clinical_mean=("clinical_score", "mean"),
            novelty_mean=("novelty_score", "mean"),
            hallucination_rate=("predicted_hallucination_flag", lambda s: s.eq(True).mean()),
        )
        .reset_index()
    )
    by_tier.to_csv(OUT_DIR / "summary_by_source_tier.csv", index=False)

    by_journal = (
        df.groupby(["tier", "journal_name"], dropna=False)
        .agg(
            n=("pmcid", "count"),
            overall_mean=("overall_quality_1_10", "mean"),
            pred_tier_mean=("highest_tier_acceptance", "mean"),
        )
        .reset_index()
        .sort_values(["tier", "n"], ascending=[True, False])
    )
    by_journal.to_csv(OUT_DIR / "summary_by_journal.csv", index=False)

    rec_ct = pd.crosstab(df["tier"], df["recommendation_at_that_tier"])
    rec_ct.to_csv(OUT_DIR / "recommendation_crosstab_by_source_tier.csv")

    loe_ct = df["loe_oxford"].value_counts().sort_index()
    loe_ct.to_csv(OUT_DIR / "loe_counts.csv", header=["count"])

    summary = pd.DataFrame(
        [
            {
                "n_papers": len(df),
                "mean_overall_quality": df["overall_quality_1_10"].mean(),
                "median_overall_quality": df["overall_quality_1_10"].median(),
                "mean_predicted_tier": df["highest_tier_acceptance"].mean(),
                "hallucination_flag_rate": df["predicted_hallucination_flag"].eq(True).mean(),
                "architecture_single_agent_frac": (df["architecture"] == "single-agent").mean(),
            }
        ]
    )
    summary.to_csv(OUT_DIR / "summary_global.csv", index=False)

    hall_df = build_hallucination_flagged_table(df, model_path)
    hall_df.to_csv(OUT_DIR / "hallucination_flagged_papers.csv", index=False)

    _write_derived_summaries(
        df,
        ct,
        ct_row,
        by_tier,
        rec_ct,
        summary_heading=summary_heading,
        coverage_section=coverage_section,
        results_model_subdir=args.model_dir,
    )

    # --- Figures ---
    fig_confusion_norm(ct_row * 100)
    fig_confusion_counts(ct)
    fig_overall_by_tier(df)
    fig_specialist_means(df)
    fig_recommendation_stacked(df)
    fig_predicted_tier_counts(df)
    fig_overall_hist(df)
    fig_loe_counts(df)
    fig_hallucination_flagged(hall_df)

    print(f"Wrote tables + figures to {OUT_DIR}")

    if args.compare_with:
        other_path = (config.PROJECT_ROOT / "results" / args.compare_with).resolve()
        cmp_out = (config.PROJECT_ROOT / args.compare_output_dir).resolve()
        write_cross_model_compare(
            model_path,
            other_path,
            cmp_out,
            label_a=args.model_dir,
            label_b=args.compare_with,
        )


if __name__ == "__main__":
    main()
