# LLM Oncology Peer Review Benchmark

Code, prompts, model outputs and derived tables for a benchmark in which seven large language models assign a journal tier to 485 blinded oncology manuscripts. The outcome is agreement with the tier of the source journal. This repository accompanies the paper (JMIR AI, manuscript 109122).

## Contents

| Path | Contents |
|---|---|
| `oncoblind/` | Pipeline that converts JATS XML to blinded markdown. |
| `scripts/` | Corpus acquisition, sampling, blinding and model-run scripts. See `scripts/README.md`. |
| `prompts/` | Prompts (version 1.0), rubric and JSON output schema. See `prompts/README.md`. |
| `results/` | Model outputs, one JSON file per model, manuscript and run: `results/<model>/<PMCID>/run_<n>.json`. Run 1 is in the repository. Runs 2 and 3 are in the release asset `outputs_runs_2_3.zip` (release `v1.1-revision`). |
| `corpus_tracker.csv` | The 497 sampled records: tier, journal, cancer domain, study type, blinding checks. |
| `manuscript/` | Main analysis (run 1): scripts, derived tables and figures. See `manuscript/README.md`. |
| `revision/` | Additional analyses: scripts and result tables, venue probe, swapped-examples test, clinician benchmark summary, flow diagram script. See `revision/README.md`. |
| `plan_180426.md` | Study protocol (working draft of April 2026). The study was not registered. |
| `journals_list.md`, `corpus_acquisition_plan.md` | Planning documents: journal list and corpus acquisition plan. |
| `eval_queue.csv` | Queue and status table for Claude Opus 4.7, run 1, written by `scripts/09_eval_queue.py`. |
| `qa_manual_checklist.csv` | The random 10% sample drawn for the manual blinding check. |
| `examples/demo_blinded_manuscript.md` | Synthetic example of the blinded markdown input format. |
| `DATA_NOTICE.md` | What is and is not redistributed. |

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r revision/requirements.txt
export MPLCONFIGDIR="$PWD/.matplotlib"
```

## Main analysis

Run 1 of the seven models on the 485 analysed manuscripts. Run from the repository root:

```bash
python manuscript/analysis/01_build_master_table.py
python manuscript/analysis/02_per_model_metrics.py
python manuscript/analysis/03_intermodel_agreement.py
python manuscript/analysis/04_subgroup_analysis.py
python manuscript/analysis/05_build_tables.py
python manuscript/analysis/08_compose_manuscript_figures.py
python manuscript/analysis/09_compose_supp_figures.py
```

The scripts rewrite `manuscript/out/`, `manuscript/tables/` and the figures. `00_eligibility_filter.py` needs the article texts, which are not distributed, and is not part of this sequence.

## Additional analyses

Download `outputs_runs_2_3.zip` from release `v1.1-revision` and unzip it at the repository root, so that `results/<model>/<PMCID>/run_2.json` and `run_3.json` exist. Then:

```bash
python revision/analyses/run_all.py
python revision/venue_probe/probe_summary.py
python revision/swapped_examples_test/compare_swap.py
python revision/figures/make_flow_diagram.py
```

`run_all.py` rewrites the tables in `revision/analyses/results/`. No step calls a model. Scripts, outputs and table numbers are listed in `revision/README.md`.

## How the model outputs were produced

- **Anthropic models (Claude Opus 4.7, Sonnet 4.6, Haiku 4.5), all three runs.** An interactive Claude Code session sent batches of manuscripts to sub-agents. Each manuscript was assessed in one pass through the five specialist prompts and then the chief prompt, returning one JSON output. Outputs are labelled `single-agent`.
- **Gemini 3 Flash Preview.** `scripts/11_run_eval_gemini.py`, Google Gen AI SDK for Python: five specialist calls, then a chief call, temperature 0.3. Outputs are labelled `multi-agent`. One full run and a partial second run (229 articles).
- **OpenAI models (GPT-5.5, GPT-5.4 mini, GPT-5.2, medium reasoning effort).** Codex command-line interface, with the specialists and the chief as separate agents. Outputs are labelled `multi-agent`.

`scripts/08_run_eval.py` and `scripts/12_run_eval_cursor.py` did not produce the outputs analysed in the paper.

The model string and label recorded in the outputs are counted per model and run in `revision/analyses/results/run_metadata.csv`. Settings per provider are in Supplementary Table S5 of the paper.

## Article texts

The source PMC XML files and the blinded manuscript texts are not redistributed (see `DATA_NOTICE.md`). They can be rebuilt from the PubMed Central Open Access Subset with `scripts/04_fetch_jats.py` and `scripts/05_run_oncoblind.py`, subject to each article's licence.

## Licence

MIT. See `LICENSE`.

## Citation

The accompanying paper (JMIR AI, manuscript 109122) and the archived repository, doi:10.5281/zenodo.21701757.
