# Additional analyses

Additional analyses of the paper (JMIR AI, manuscript 109122). All scripts run from the repository root. None of the analysis or summary scripts calls a model.

## Folders

| Folder | Contents |
|---|---|
| `analyses/` | Analysis scripts and their output tables in `analyses/results/`. `common.py` holds data loading, agreement statistics and the bootstrap; `run_all.py` runs every script. |
| `data/` | Input tables: `jcr_values.csv` (Journal Impact Factors and categories read from Journal Citation Reports on 28 October 2026, and the tier under each band set), `publication_dates.csv` (dates from the PMC XML, linked preprints from Europe PMC, presence of a meeting-presentation statement), `text_features.csv` (length, counts and keyword flags of the blinded texts). |
| `venue_probe/` | `run_probe.py` (runner), `probe_prompt.md` (prompt), `clean.py` (writes the cleaned text), `sample_probe.csv` (the 496 records probed), call logs in `probe_claude-opus-4-7_original/` (blinded text, 496 logs), `probe_claude-opus-4-7_cleaned/` (cleaned text, 496 logs) and `probe_claude-sonnet-4-6_original/` (blinded text, 460 logs), `probe_summary.py` and its output `probe_summary.txt`. |
| `swapped_examples_test/` | `run_review_single.py` (runner), `prompts_swap/` (chief prompt with swapped example journals), `sample.csv` (the 100 manuscripts), call logs in `original_examples/` and `swapped_examples/` (100 each), `compare_swap.py` and its outputs `swapped_examples_tiers.csv` and `swapped_examples_summary.txt`. |
| `clinician_benchmark/` | `benchmark_summary.py` and its output `benchmark_summary.csv`. The individual ratings are available from the corresponding author on request. |
| `figures/` | `make_flow_diagram.py` (corpus flow diagram). |

The article texts (PMC XML, blinded text, cleaned text) are not distributed. The call logs hold the SHA-256 of the manuscript and of the prompt, the model answer, the timing and, for the swapped-examples test, the cost reported by Claude Code; they do not hold the manuscript text. Local file paths in the logged command lines are elided.

## Run

1. Unzip the release asset `outputs_runs_2_3.zip` (release `v1.1-revision`) at the repository root, so that `results/<model>/<PMCID>/run_2.json` and `run_3.json` exist next to `run_1.json`.
2. In the environment described in the root `README.md`:

```bash
python revision/analyses/run_all.py                      # rewrites revision/analyses/results/
python revision/venue_probe/probe_summary.py             # rewrites probe_summary.txt
python revision/swapped_examples_test/compare_swap.py    # rewrites swapped_examples_tiers.csv and swapped_examples_summary.txt
python revision/figures/make_flow_diagram.py             # writes flow_diagram.png and flow_diagram.pdf
```

`baselines.py` and `publication_dates.py` read `data/text_features.csv` and `data/publication_dates.csv` when the article texts are absent; with `corpus/normalized/` and `corpus/raw/` present they rewrite the two tables. `run_probe.py`, `clean.py` and `run_review_single.py` need the article texts; the two runners call Claude Code. `benchmark_summary.py` needs the individual ratings.

## Scripts, outputs and tables

Outputs are in `analyses/results/` unless a path is given. Table numbers refer to Multimedia Appendix 1 of the paper.

| Script | Output | Table |
|---|---|---|
| `analyses/reproduce_table1.py` | `table1.csv` | Table 1 |
| `analyses/predicted_tier_distribution.py` | `predicted_tier_by_source_tier.csv` | |
| `analyses/agreement_measures.py` | `agreement_by_weighting.csv` | S7 |
| | `constant_rule_baselines.csv` | S19 |
| `analyses/journal_clustering.py` | `journal_clustered_ci.csv` | S7 |
| | `per_journal_results.csv`, `leave_one_journal_out.csv`, `leave_one_journal_out_range.csv` | S17 |
| `analyses/model_differences.py` | `kappa_differences_adjacent.csv`, `kappa_differences_vs_opus.csv` | S10 |
| | `kappa_differences_all_pairs.csv` | |
| `analyses/missing_outputs.py` | `missing_outputs_by_tier.csv`, `missing_outputs_sensitivity.csv` | S9 |
| | `missing_outputs_list.csv`, `missing_outputs_vs_length.csv`, `haiku_failures_across_runs.csv` | |
| `analyses/repeatability.py` | `kappa_vs_source_by_run.csv` | S11 |
| | `repeatability_three_runs.csv`, `repeatability_weighted.csv` | S14 |
| | `repeatability_rank_by_metric.csv` | |
| `analyses/subgroups.py` | `subgroup_kappa_study_type.csv`, `subgroup_kappa_cancer_domain.csv` | S3 |
| | `subgroup_tier_distribution.csv` | |
| `analyses/output_consistency.py` | `recommendation_by_source_tier.csv`, `consistency_quality_vs_tier.csv`, `subscores_vs_predicted_tier.csv` | S12 |
| | `recommendation_by_predicted_tier.csv` | |
| `analyses/original_496_records.py` | `original_496_sensitivity.csv` | |
| `analyses/run_metadata.py` | `run_metadata.csv` | |
| `analyses/baselines.py` | `baseline_predictors.csv`, `opus_kappa_within_feature_strata.csv` | S19 |
| `analyses/retiering_by_jcr.py` | `retiering_by_jcr.csv`, `retiering_papers_changed.csv` | S20 |
| (input) | `data/jcr_values.csv` | S4 |
| `analyses/publication_dates.py` | `post_cutoff_sensitivity.csv`, `before_vs_after_cutoff_within_journal.csv` | S18 |
| | `before_vs_after_cutoff_within_tier.csv` | |
| `analyses/recognition_vs_agreement.py` | `recognition_vs_agreement.csv`, `recognition_vs_agreement_differences.csv` | |
| `analyses/auroc_tier_discrimination.py` | `auroc_tier_discrimination.csv` | S15 |
| `venue_probe/probe_summary.py` | `venue_probe/probe_summary.txt` | |
| `swapped_examples_test/compare_swap.py` | `swapped_examples_test/swapped_examples_summary.txt`, `swapped_examples_tiers.csv` | S8 |
| `clinician_benchmark/benchmark_summary.py` | `clinician_benchmark/benchmark_summary.csv` | |

Tables S13 (pairwise inter-model agreement) and S16 (specialist scores) are produced by `manuscript/analysis/`.

## Software versions

`requirements.txt` lists the versions used to produce `analyses/results/` (Python 3.9.6). Bootstrap seeds are fixed (42).
