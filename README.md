# LLM Oncology Peer Review Benchmark

Reproducibility package for a blinded, contamination-controlled benchmark of seven frontier large language models as oncology manuscript peer reviewers.

## Repository Name

Suggested GitHub repository name: `llm-oncology-peer-review-benchmark`

## Contents

| Path | Purpose |
|---|---|
| `oncoblind/` | Deterministic JATS XML to blinded markdown pipeline. |
| `scripts/` | Corpus acquisition, stratification, blinding, QA, and model-evaluation scripts. |
| `prompts/` | Locked reviewer prompt tree and JSON schema. |
| `results/` | Per-paper JSON peer-review outputs for the seven included models. |
| `manuscript/analysis/` | Analysis scripts used to generate manuscript tables and figures. |
| `manuscript/out/` | Derived analysis tables, including the wide per-paper master table. |
| `manuscript/tables/` | Publication tables. |
| `manuscript/figures/` | Single-panel generated figures. |
| `manuscript/figures_composed/` | Main composed figures. |
| `manuscript/figures_composed_supp/` | Supplementary composed figures. |
| `examples/demo_blinded_manuscript.md` | Synthetic example of the blinded markdown input format. |

## Reproduce Main Analysis

Create an environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export MPLCONFIGDIR="$PWD/.matplotlib"
```

Run the analysis pipeline from the repository root:

```bash
python manuscript/analysis/01_build_master_table.py
python manuscript/analysis/02_per_model_metrics.py
python manuscript/analysis/03_intermodel_agreement.py
python manuscript/analysis/04_subgroup_analysis.py
python manuscript/analysis/05_build_tables.py
python manuscript/analysis/08_compose_manuscript_figures.py
python manuscript/analysis/09_compose_supp_figures.py
```

The scripts regenerate `manuscript/out/`, `tables/`, and figure outputs from the frozen analytical-sample metadata and model-output JSON files.

`00_eligibility_filter.py` is retained as provenance for the original filtering
rule, but it requires the undistributed full-text corpus and is not part of the
public rerun path.

## Full-Text Corpus

This repository does not redistribute source PMC full-text article XML files or
blinded manuscript markdown files. See `DATA_NOTICE.md`.

## Notes

- The model-output JSON files are fixed run-1 outputs and do not require model-provider credentials to reproduce the analyses.
- Re-running model evaluation requires access to the provider CLIs or SDKs used in the study and may produce different outputs if provider-side model snapshots changed.
- The corpus was derived from the PubMed Central Open Access Subset; full-text article files must be retrieved from PMC under each article's license terms.
