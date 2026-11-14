"""Corpus flow diagram. Writes flow_diagram.png and flow_diagram.pdf next to this script.
Usage, from the repository root: python revision/figures/make_flow_diagram.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parent
MAIN = [
    "Records enumerated in PubMed: 14 journals, PMC Open Access,\n"
    "PubMed publication date 1 Feb–18 Apr 2026, eligible article types\n"
    "n = 1,442 (Tier 1, 62; Tier 2, 283; Tier 3, 932; Tier 4, 165)",
    "Sampled by journal quota (target 500; stratified by cancer domain × study type, seed 42)\n"
    "n = 497 (Tier 1, 62; Tier 2, 120; Tier 3, 185; Tier 4, 130)",
    "Reviewed by the models (run 1)\nn = 496",
    "Analysed\nn = 485 (Tier 1, 61; Tier 2, 118; Tier 3, 184; Tier 4, 122)",
    "Valid tier output: 485 for Claude Opus 4.7, Claude Sonnet 4.6, GPT-5.5, GPT-5.2 and GPT-5.4 mini;\n"
    "477 for Gemini 3 Flash (8 missing); 467 for Claude Haiku 4.5 (18 failed the schema, all in run 1)",
]
SIDE = {
    1: "Not sampled: 945\n(quota filled; JCO and Nature Medicine\nhad fewer eligible articles than their\nquota, so all were taken)",
    2: "Excluded before review: 1\n(no extractable body text)",
    3: "Excluded after run 1: 11\n(9 retraction notices, 1 reply,\n1 commentary)",
}

fig, ax = plt.subplots(figsize=(10, 9.2))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")
ys = [9.0, 7.0, 5.0, 3.0, 1.0]
for y, text in zip(ys, MAIN):
    ax.add_patch(FancyBboxPatch((0.3, y - 0.6), 6.4, 1.2, boxstyle="round,pad=0.02", fc="white", ec="black", lw=1))
    ax.text(3.5, y, text, ha="center", va="center", fontsize=8.6)
for a, b in zip(ys[:-1], ys[1:]):
    ax.annotate("", xy=(3.5, b + 0.62), xytext=(3.5, a - 0.62), arrowprops=dict(arrowstyle="->", lw=1))
for i, text in SIDE.items():
    y = (ys[i - 1] + ys[i]) / 2
    ax.add_patch(FancyBboxPatch((7.05, y - 0.62), 2.85, 1.24, boxstyle="round,pad=0.02", fc="#f2f2f2", ec="black",
                                lw=0.8))
    ax.text(8.47, y, text, ha="center", va="center", fontsize=7.8)
    ax.annotate("", xy=(7.03, y), xytext=(3.5, y), arrowprops=dict(arrowstyle="->", lw=0.8))
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(OUT / f"flow_diagram.{ext}", dpi=300)
print("saved")
