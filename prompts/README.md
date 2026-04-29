# Multi-agent reviewer prompts

Implements the orchestrator + 5 specialist + chief reviewer pattern described in `plan_180426.md` §6 and §7. All prompts are frozen at preregistration; the exact text in this directory is what runs against every paper × model × run.

## Files

| File | Role |
|---|---|
| `orchestrator.md` | Top-level coordinator instructions (Claude Code main session / Antigravity main agent / OpenAI driver) |
| `01_specialist_methodological.md` | Methodological rigor + statistical appropriateness (rubric §7 items 1, 2) |
| `02_specialist_clinical_loe.md` | Level of evidence + clinical/translational relevance (rubric items 3, 4) |
| `03_specialist_reporting.md` | Reporting standards adherence + data/code availability (rubric items 6, 8) |
| `04_specialist_novelty.md` | Novelty / originality (rubric item 5) |
| `05_specialist_writing.md` | Writing and presentation (rubric item 7) |
| `06_chief_reviewer.md` | Synthesizes all specialist outputs + emits final JSON |
| `shared/rubric.md` | Canonical rubric with 1–5 anchors |
| `shared/schema.json` | JSON output schema (§6.5) |

## Per-paper flow

```
Manuscript (blinded markdown) ─┐
                                │
                      ┌─────────▼──────────┐
                      │  Orchestrator      │
                      │  loads rubric +    │
                      │  manuscript        │
                      └─────────┬──────────┘
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
            ┌────▼───┐     ┌────▼───┐     ┌────▼────┐
            │ Spec 1 │     │ Spec 2 │ ... │ Spec 5  │   ◀── run in parallel
            └────┬───┘     └────┬───┘     └────┬────┘
                 │              │              │
                 └──────────────┼──────────────┘
                                │
                      ┌─────────▼──────────┐
                      │  Chief Reviewer    │  synthesis call
                      │  → final JSON      │
                      └────────────────────┘
```

## Models

Same prompts used across Claude Opus 4.7, Sonnet 4.6, Gemini 3.1 Pro, GPT-5. Only the orchestrator model identity differs.

## Output location

`results/<model>/<paper_id>/run_<n>.json` conforming to `shared/schema.json`.

## Determinism

- Temperature 0.3 (primary), 0.7 for the temporal-stability subset (§5)
- 3 runs per paper × model combination
- All outputs must parse as valid JSON — orchestrator retries up to 2× on schema failure, then flags
