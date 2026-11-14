# Prompts

Version 1.0 prompt files, used in every run reported in the paper (JMIR AI, manuscript 109122). The study was not registered. Settings per provider are in Supplementary Table S5 of the paper.

| File | Role |
|---|---|
| `01_specialist_methodological.md` | Methodological rigor and statistical appropriateness |
| `02_specialist_clinical_loe.md` | Level of evidence and clinical or translational relevance |
| `03_specialist_reporting.md` | Reporting standards and data or code availability |
| `04_specialist_novelty.md` | Novelty and originality |
| `05_specialist_writing.md` | Writing and presentation |
| `06_chief_reviewer.md` | Synthesis of the specialist outputs; assigns the tier and writes the final JSON |
| `orchestrator.md` | Coordinator instructions for runners that use separate agents |
| `shared/rubric.md` | Rubric with 1–5 anchors |
| `shared/schema.json` | JSON output schema |
| `v1.1/` | Version 1.1 of `03_specialist_reporting.md` and `shared/rubric.md`; not used in the paper |

Each manuscript is assessed with the five specialist prompts and then the chief prompt, and one JSON output conforming to `shared/schema.json` is written to `results/<model>/<PMCID>/run_<n>.json`. Delivery differed by provider: one pass per manuscript for the Anthropic models, separate specialist and chief calls for Gemini 3 Flash Preview, and separate agents in Codex for the OpenAI models (see the root `README.md`).
