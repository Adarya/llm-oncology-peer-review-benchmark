# Publication tables — seven-model benchmark


## Table 1. Cohort characteristics

| Characteristic                   |   Value | Percent   |
|:---------------------------------|--------:|:----------|
| Total papers (analytical sample) |     485 |           |
| Tier 1 (source journal)          |      61 | 12.6%     |
| Tier 2 (source journal)          |     118 | 24.3%     |
| Tier 3 (source journal)          |     184 | 37.9%     |
| Tier 4 (source journal)          |     122 | 25.2%     |
| Cancer-domain strata represented |      12 |           |
| Study-type strata represented    |       7 |           |



## Table 2. Primary outcomes per model

| Model                 |   n | κ (95% CI)           | Exact match   | Within ±1   | Spearman ρ       |   Δ (pred − source) |   Mean overall (1–10) | Recommendation: accept   | minor   | major   | reject   |
|:----------------------|----:|:---------------------|:--------------|:------------|:-----------------|--------------------:|----------------------:|:-------------------------|:--------|:--------|:---------|
| Claude Opus 4.7       | 485 | 0.772 (0.735, 0.802) | 60.8%         | 99.2%       | 0.764 (p <0.001) |              -0.066 |                  5.83 | 0.6%                     | 59.8%   | 39.6%   | 0.0%     |
| Gemini 3 Flash        | 477 | 0.627 (0.578, 0.669) | 53.5%         | 95.6%       | 0.719 (p <0.001) |              -0.4   |                  7.21 | 1.5%                     | 83.0%   | 15.5%   | 0.0%     |
| Claude Sonnet 4.6     | 485 | 0.596 (0.545, 0.642) | 48.0%         | 96.5%       | 0.618 (p <0.001) |              -0.072 |                  5.91 | 1.0%                     | 80.8%   | 18.1%   | 0.0%     |
| GPT-5.5 (medium)      | 485 | 0.587 (0.522, 0.648) | 51.8%         | 95.7%       | 0.603 (p <0.001) |               0.031 |                  6.39 | 0.2%                     | 42.1%   | 57.3%   | 0.4%     |
| GPT-5.2 (medium)      | 485 | 0.486 (0.422, 0.544) | 47.6%         | 92.6%       | 0.509 (p <0.001) |               0.025 |                  6.54 | 0.6%                     | 35.9%   | 63.3%   | 0.2%     |
| GPT-5.4 mini (medium) | 485 | 0.449 (0.378, 0.512) | 47.0%         | 92.4%       | 0.489 (p <0.001) |               0.194 |                  6.27 | 0.0%                     | 45.8%   | 51.8%   | 2.5%     |
| Claude Haiku 4.5      | 467 | 0.265 (0.188, 0.341) | 35.5%         | 82.0%       | 0.279 (p <0.001) |               0.52  |                  5.3  | 12.8%                    | 47.7%   | 30.0%   | 9.6%     |



## Table 3. Pairwise inter-model agreement

| model_a               | model_b               |   n_tier |   κ tier |   κ recommendation |   n_overall |   Pearson r (overall) |   Bland–Altman (mean diff) | LoA           |
|:----------------------|:----------------------|---------:|---------:|-------------------:|------------:|----------------------:|---------------------------:|:--------------|
| Claude Opus 4.7       | Gemini 3 Flash        |      477 |    0.687 |              0.272 |         477 |                 0.778 |                     -1.375 | (-3.21, 0.46) |
| Claude Opus 4.7       | Claude Sonnet 4.6     |      485 |    0.74  |              0.277 |         485 |                 0.814 |                     -0.078 | (-1.77, 1.61) |
| Claude Opus 4.7       | GPT-5.5 (medium)      |      485 |    0.704 |              0.437 |         485 |                 0.816 |                     -0.563 | (-2.23, 1.11) |
| Claude Opus 4.7       | GPT-5.2 (medium)      |      485 |    0.636 |              0.3   |         485 |                 0.734 |                     -0.707 | (-2.68, 1.27) |
| Claude Opus 4.7       | GPT-5.4 mini (medium) |      485 |    0.56  |              0.232 |         485 |                 0.711 |                     -0.439 | (-2.47, 1.60) |
| Claude Opus 4.7       | Claude Haiku 4.5      |      467 |    0.293 |              0.104 |         470 |                 0.383 |                      0.553 | (-2.74, 3.84) |
| Gemini 3 Flash        | Claude Sonnet 4.6     |      477 |    0.653 |              0.225 |         477 |                 0.717 |                      1.296 | (-0.50, 3.09) |
| Gemini 3 Flash        | GPT-5.5 (medium)      |      477 |    0.592 |              0.149 |         477 |                 0.734 |                      0.818 | (-0.79, 2.43) |
| Gemini 3 Flash        | GPT-5.2 (medium)      |      477 |    0.55  |              0.113 |         477 |                 0.675 |                      0.673 | (-0.90, 2.25) |
| Gemini 3 Flash        | GPT-5.4 mini (medium) |      477 |    0.431 |              0.13  |         477 |                 0.614 |                      0.943 | (-0.92, 2.81) |
| Gemini 3 Flash        | Claude Haiku 4.5      |      459 |    0.224 |              0.02  |         462 |                 0.394 |                      1.939 | (-0.97, 4.85) |
| Claude Sonnet 4.6     | GPT-5.5 (medium)      |      485 |    0.703 |              0.172 |         485 |                 0.748 |                     -0.485 | (-2.22, 1.25) |
| Claude Sonnet 4.6     | GPT-5.2 (medium)      |      485 |    0.639 |              0.14  |         485 |                 0.675 |                     -0.629 | (-2.52, 1.26) |
| Claude Sonnet 4.6     | GPT-5.4 mini (medium) |      485 |    0.55  |              0.097 |         485 |                 0.65  |                     -0.361 | (-2.37, 1.65) |
| Claude Sonnet 4.6     | Claude Haiku 4.5      |      467 |    0.323 |              0.024 |         470 |                 0.425 |                      0.626 | (-2.40, 3.65) |
| GPT-5.5 (medium)      | GPT-5.2 (medium)      |      485 |    0.744 |              0.382 |         485 |                 0.778 |                     -0.144 | (-1.60, 1.31) |
| GPT-5.5 (medium)      | GPT-5.4 mini (medium) |      485 |    0.651 |              0.348 |         485 |                 0.724 |                      0.124 | (-1.55, 1.80) |
| GPT-5.5 (medium)      | Claude Haiku 4.5      |      467 |    0.328 |              0.103 |         470 |                 0.445 |                      1.111 | (-1.77, 3.99) |
| GPT-5.2 (medium)      | GPT-5.4 mini (medium) |      485 |    0.63  |              0.356 |         485 |                 0.684 |                      0.268 | (-1.37, 1.91) |
| GPT-5.2 (medium)      | Claude Haiku 4.5      |      467 |    0.345 |              0.083 |         470 |                 0.404 |                      1.249 | (-1.59, 4.08) |
| GPT-5.4 mini (medium) | Claude Haiku 4.5      |      467 |    0.375 |              0.058 |         470 |                 0.343 |                      0.977 | (-2.09, 4.05) |



## Table 4. Specialist rubric means by model

| Dimension                   |   Claude Opus 4.7 |   Gemini 3 Flash |   Claude Sonnet 4.6 |   GPT-5.5 (medium) |   GPT-5.2 (medium) |   GPT-5.4 mini (medium) |   Claude Haiku 4.5 |
|:----------------------------|------------------:|-----------------:|--------------------:|-------------------:|-------------------:|------------------------:|-------------------:|
| Methodological rigor        |              3.27 |             3.63 |                3.22 |               3.11 |               3.31 |                    3.2  |               3.14 |
| Statistical appropriateness |              3.16 |             3.6  |                3.18 |               3    |               3.33 |                    3.06 |               3.18 |
| Clinical / LoE              |              3.3  |             3.64 |                3.2  |               3.42 |               3.64 |                    3.48 |               3.05 |
| Reporting quality           |              3.37 |             3.99 |                3.4  |               3.35 |               3.44 |                    3.45 |               3.1  |
| Data availability           |              2.25 |             2.4  |                2.4  |               2.1  |               2.13 |                    1.84 |               1.95 |
| Novelty                     |              3.15 |             3.13 |                3.28 |               3.29 |               3.26 |                    3.49 |               2.72 |
| Writing                     |              3.6  |             4.68 |                3.66 |               3.62 |               3.83 |                    3.68 |               3.5  |



## Table 5. Seven-way multi-model agreement

|   n_intersection_tier |   fleiss_kappa_tier_7way |   krippendorff_alpha_ordinal_tier_7way |   n_intersection_overall_quality |   icc21_absolute_overall_quality_7way |
|----------------------:|-------------------------:|---------------------------------------:|---------------------------------:|--------------------------------------:|
|                   459 |                    0.294 |                                  0.518 |                              462 |                                 0.483 |

