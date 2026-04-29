# Seven-model analysis workspace (2026-04-29)

Updated benchmarking report covering **seven 2026-generation frontier LLMs**:
Claude Opus 4.7, Claude Sonnet 4.6, Claude Haiku 4.5, Gemini 3 Flash Preview,
GPT-5.5 medium, GPT-5.4 mini medium, GPT-5.2 medium — single-agent run_1 on the v1.0
blinded oncology corpus, with a post-hoc eligibility refinement that excludes 12
non-research items (retraction notices and a reply/correspondence) from the original
n=496, giving an analytical n=485.

This workspace contains the public analysis code, derived tables, and generated
figures for the seven-model benchmark. The analytical sample has n=485 papers
after excluding 11 retraction notices and one reply/commentary item from the
original n=496 sampled records. `00_eligibility_filter.py` is retained as
provenance for the eligibility rule, but it requires the undistributed full-text
corpus. Pairwise inter-model analyses cover all 21 model pairs; seven-way Fleiss
/ Krippendorff agreement is computed on the all-model intersection.

Nothing here modifies the upstream pipeline. Re-run the public analysis scripts
in numeric order, starting from the frozen analytical sample in `out/`.

## Layout

| Path | Purpose |
|---|---|
| `analysis/` | Python scripts |
| `out/master_per_paper.csv` | Wide 7-model × 485-paper table |
| `_exclusions.csv` | The 12 PMCIDs dropped from the analytical sample, with reason |
| `tables/` | Manuscript tables (CSV + MD) |
| `figures/` | Single-panel figures (PDF + PNG; Arial) |
| `figures_composed/` | Composed multi-panel main figures |
| `figures_composed_supp/` | Composed supplementary figures |

## Reproduce

```bash
.venv/bin/python manuscript/analysis/01_build_master_table.py
.venv/bin/python manuscript/analysis/02_per_model_metrics.py
.venv/bin/python manuscript/analysis/03_intermodel_agreement.py
.venv/bin/python manuscript/analysis/04_subgroup_analysis.py
.venv/bin/python manuscript/analysis/05_build_tables.py
.venv/bin/python manuscript/analysis/08_compose_manuscript_figures.py
.venv/bin/python manuscript/analysis/09_compose_supp_figures.py
```
