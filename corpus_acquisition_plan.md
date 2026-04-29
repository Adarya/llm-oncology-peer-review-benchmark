# Corpus Acquisition Plan (v1)

**Date:** 2026-04-18 · **Target n:** 500 · **Channel:** PMC-OA only (no manual, no controls this iteration)

Links: [`plan_180426.md`](plan_180426.md) §4 · [`journals_list.md`](journals_list.md)

---

## 1. Scope (decisions locked in this iteration)

- **n = 500** primary research articles
- **14 journals** across 4 tiers (see `journals_list.md`)
- **Window:** 2026-02-01 → corpus freeze date (today = 2026-04-18)
- **Access channel:** PMC-OA only — JATS XML. **No manual institutional downloads.**
- **Lancet Oncology excluded** (0 PMC-OA; 12-mo embargo)
- **No negative controls** (no predatory, no retracted — deferred)
- **Contamination-probe protocol** (§11 of main plan) — deferred decision

## 2. Tier quotas and sampling ratios

| Tier | Pool | Quota | % of n=500 | Sampling |
|---|---|---|---|---|
| 1 | 65 | 65 | 13% | Exhaustive — take all |
| 2 | 265 | 120 | 24% | Random ~0.45 of pool |
| 3 | 934 | 185 | 37% | Random ~0.20 of pool |
| 4 | 186 | 130 | 26% | Random ~0.70 of pool |
| **Total** | **1,450** | **500** | **100%** | |

**Tier 1 deviation from main plan.** §4.4 targets Tier 1 at 15–20%; current data supports 13% without manual downloads. Revisit at corpus-freeze decision point.

### Per-journal quotas

| Tier | Journal | Pool | Quota |
|---|---|---|---|
| 1 | Nature Cancer | 11 | 11 |
| 1 | Nature Medicine (onc) | 13 | 13 |
| 1 | JCO | 29 | 29 |
| 1 | JAMA Oncology | 12 | 12 |
| 2 | Nat Commun (onc) | 107 | 45 |
| 2 | Cancer Research | 31 | 20 |
| 2 | Clinical Cancer Research | 39 | 25 |
| 2 | ESMO Open | 66 | 20 |
| 2 | JCO Precision Oncology | 22 | 10 |
| 3 | Cancers (MDPI) | 428 | 85 |
| 3 | Frontiers in Oncology | 506 | 100 |
| 4 | Oncology Letters | 94 | 65 |
| 4 | Current Oncology | 53 | 35 |
| 4 | Cancer Reports | 39 | 30 |
| **Total** | | | **500** |

## 3. Sampling strategy — **sample, do not harvest**

**Important:** PMC-OA has ~1,350+ eligible papers post-Feb 2026. We do NOT download them all. We pull a **stratified random sample** per quota, then fetch JATS XML only for selected PMIDs.

### Step 1 — Enumerate
For each journal × window, query PubMed via E-utilities (`esearch` → `efetch` metadata) with:

```
<journal>[Journal]
  AND "Journal Article"[PT]
  NOT ("Editorial"[PT] OR "Letter"[PT] OR "Comment"[PT]
       OR "News"[PT] OR "Review"[PT] OR "Case Reports"[PT])
  AND 2026/02/01:<freeze_date>[dp]
  AND "pubmed pmc open access"[Filter]
```

Collect full PMID + PMCID list + minimal metadata (title, abstract, article-type, MeSH headings, pub date) into `corpus_index.csv`.

### Step 2 — Classify for stratification
For each PMID, auto-label via MeSH + abstract:
- **Cancer domain**: breast, lung, GI, GU, hematologic, CNS, gynecologic, H&N, sarcoma, melanoma/skin, pediatric, rare/NOS
- **Study type**: RCT-late / trial-early / observational / meta-analysis / translational-biomarker / preclinical / real-world
- Sanity spot-check on 5% by hand.

### Step 3 — Stratified random sample
For each journal-quota, stratified random sampling across domain × study type (target balanced cells within journal when pool allows; otherwise fall back to random within journal). Set a **frozen random seed** for reproducibility.

### Step 4 — Fetch JATS XML
Only for selected PMCIDs: fetch JATS XML from PMC via `efetch` / PMC OA bulk download API. Store under `corpus/raw/<PMCID>.xml`.

### Step 5 — Normalize via `oncoblind`
Run §8 blinding pipeline (main plan). Output: `corpus/normalized/<PMCID>.md` + QA report.

### Step 6 — QA sweep
- Auto journal/publisher regex sweep (§8.5.1–2)
- 10% manual QA before corpus freeze

### Step 7 — Freeze
Lock `corpus_index.csv`, hash all normalized markdowns, tag release `corpus-v1.0`.

## 4. Directory structure

```
LLM_publication_audit/
├── plan_180426.md
├── journals_list.md
├── corpus_acquisition_plan.md          <- this file
├── scripts/
│   ├── 01_enumerate_pmids.py           <- per-journal esearch
│   ├── 02_classify_stratify.py         <- MeSH/abstract → domain/study-type
│   ├── 03_sample.py                    <- stratified random sampling
│   ├── 04_fetch_jats.py                <- efetch selected PMCIDs
│   └── 05_run_oncoblind.py             <- blinding + normalization
├── oncoblind/                          <- blinding pipeline package (§8.7)
├── corpus/
│   ├── index/
│   │   ├── enumeration.csv             <- all eligible PMIDs × metadata
│   │   ├── classification.csv          <- + domain/study-type labels
│   │   └── sampled.csv                 <- final sample + random seed
│   ├── raw/                            <- JATS XML by PMCID
│   └── normalized/                     <- blinded markdown + QA reports
└── corpus_tracker.csv                  <- sampled.csv + processing status
```

## 5. Workflow — step-by-step execution

| # | Step | Tool | Output | Est. time |
|---|---|---|---|---|
| 1 | Freeze query date | manual | `FREEZE_DATE` env var | 0 |
| 2 | Enumerate all eligible PMIDs per journal | `01_enumerate_pmids.py` | `enumeration.csv` (~1,450 rows) | 15 min |
| 3 | Pull MeSH + abstracts for all enumerated | `efetch` batch | adds columns | 30 min |
| 4 | Auto-classify domain + study type | `02_classify_stratify.py` (regex + MeSH + optional LLM tiebreak) | `classification.csv` | 1 h |
| 5 | Manual spot-check 5% of classifications | manual review | labeled CSV | 2–3 h |
| 6 | Draw stratified random sample (seed=42) | `03_sample.py` | `sampled.csv` (500 rows) | <1 min |
| 7 | Fetch JATS XML for 500 PMCIDs | `04_fetch_jats.py` | `corpus/raw/*.xml` | 30 min |
| 8 | Run oncoblind normalization + QA | `05_run_oncoblind.py` + `oncoblind/` | `corpus/normalized/*.md` + per-paper QA | depends on pipeline maturity |
| 9 | 10% manual QA of blinding | manual review | QA report | 4–6 h |
| 10 | Corpus freeze + hash + tag | git | `corpus-v1.0` | 15 min |

## 6. Open flags (for later review)

1. **Tier 1 at 13% (vs 15–20% target)** — acceptable as-is, or defer corpus freeze and add manual Lancet Onc batch?
2. **Lancet Oncology entirely excluded** — acceptable given PMC-OA-only rule. Note in limitations.
3. **Contamination-probe protocol** — §11 says "probe-before-review". Revisit before main eval run.
4. **Tier 5 controls (predatory + retracted)** — deferred. May add later as exploratory arm.
5. **Cancer Biomarkers dropped** — 0 post-Feb-2026 papers. Plan note: journal has slow publication cycle.
6. **MDPI / Frontiers dominance in T3** — 185/500 = 37% of corpus. Flag potential OA-acceptance-bias in discussion.
7. **Freeze date** — recommend freezing corpus at end of next pull (e.g., 2026-04-30) to maximize T1 yield.

## 7. What NOT to do

- **Do not bulk-download all of Cancers / Frontiers in Oncology PMC-OA.** Only fetch the sampled PMIDs.
- **Do not include reviews, case reports, editorials, letters, comments, news.** Filter at enumeration step.
- **Do not include papers published before 2026-02-01** (contamination cutoff).
- **Do not fetch anything outside PMC-OA** in this iteration — no paywalled full-text.
