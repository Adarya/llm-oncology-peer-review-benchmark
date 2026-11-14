# Main analysis

Run 1 of the seven models on the 485 analysed articles (JMIR AI, manuscript 109122).

The 485 articles are the 497 sampled records minus the 12 records in `_exclusions.csv`: 9 retraction notices, 1 reply, 1 commentary and 1 article without extractable text. The article without extractable text was not run; the other 11 were excluded after run 1, so 496 records have a run-1 output.

Pairwise inter-model analyses cover all 21 model pairs. Seven-way agreement is computed on the articles with a valid tier from all seven models.

## Layout

| Path | Contents |
|---|---|
| `analysis/` | Analysis and figure scripts |
| `out/_analytical_sample.csv` | The 485 analysed articles |
| `out/master_per_paper.csv` | One row per article, columns per model |
| `out/` | Other derived tables |
| `_exclusions.csv` | The 12 excluded records, with reasons |
| `tables/` | Tables (CSV and Markdown) |
| `figures/` | Single-panel figures (PDF and PNG) |
| `figures_composed/` | Composed main figures |
| `figures_composed_supp/` | Composed supplementary figures |

## Run

From the repository root, in the environment described in the root `README.md`:

```bash
python manuscript/analysis/01_build_master_table.py
python manuscript/analysis/02_per_model_metrics.py
python manuscript/analysis/03_intermodel_agreement.py
python manuscript/analysis/04_subgroup_analysis.py
python manuscript/analysis/05_build_tables.py
python manuscript/analysis/08_compose_manuscript_figures.py
python manuscript/analysis/09_compose_supp_figures.py
```

`analysis/00_eligibility_filter.py` applies the exclusion rule. It needs the article texts, which are not distributed, and is not part of this sequence.

Analyses of runs 2 and 3 and the other additional analyses are in `revision/`.
