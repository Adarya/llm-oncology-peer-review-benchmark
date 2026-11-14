# Scripts

Run from the repository root. Steps 1 to 7 build the corpus; the article texts they produce are not distributed (see `DATA_NOTICE.md`).

| Script | What it does | Produced data used in the paper |
|---|---|---|
| `config.py` | Journals, quotas, date window, random seed. `NCBI_EMAIL` is read from the environment | Settings for steps 1 to 7 |
| `01_enumerate_pmids.py` | Lists eligible PubMed records per journal (PMC Open Access, date window) | Yes: enumeration |
| `02_classify_stratify.py` | Assigns cancer domain and study type from MeSH headings and keywords | Yes: strata |
| `03_sample.py` | Stratified random sample per journal quota (seed 42) | Yes: the 497 sampled records |
| `04_fetch_jats.py` | Downloads the JATS XML of each sampled article from PMC | Yes: source texts |
| `05_run_oncoblind.py` | Runs `oncoblind/` to produce the blinded markdown | Yes: blinded texts |
| `06_build_tracker.py` | Builds `corpus_tracker.csv` | Yes |
| `07_qa_sample.py` | Draws the random 10% sample for the manual blinding check and writes `qa_manual_checklist.csv` | Yes: the sample list |
| `08_run_eval.py`, `agents_config.py`, `eval_settings.json` | Scripted multi-agent runner for Claude Code | No. `eval_settings.json` is also read by `revision/swapped_examples_test/run_review_single.py` |
| `09_eval_queue.py` | Builds and reports the run queue `eval_queue.csv` | No |
| `10_export_prelim_results.py` | Exports tables and figures for one model | No |
| `11_run_eval_gemini.py`, `11_agents_config_gemini.py` | Gemini runner: Google Gen AI SDK for Python, five specialist calls then a chief call, temperature 0.3 | Yes: the Gemini 3 Flash Preview outputs |
| `12_run_eval_cursor.py` | Cursor runner | No |

The Anthropic and OpenAI outputs were not produced by a script in this folder. See "How the model outputs were produced" in the root `README.md`.
