"""Plot styling, model labels, model order and provider grouping shared by the analysis scripts."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORK_ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = WORK_ROOT / "figures"
TABLE_DIR = WORK_ROOT / "tables"
OUT_DIR = WORK_ROOT / "out"

# Models in descending order of run-1 kappa.
MODEL_ORDER = [
    "claude-opus-4-7",
    "gemini-3-flash-preview",
    "claude-sonnet-4-6",
    "gpt-5-5-medium",
    "gpt-5-2-medium",
    "gpt-5-4-mini-medium",
    "claude-haiku-4-5",
]

MODEL_LABEL = {
    "claude-opus-4-7":        "Claude Opus 4.7",
    "claude-sonnet-4-6":      "Claude Sonnet 4.6",
    "claude-haiku-4-5":       "Claude Haiku 4.5",
    "gemini-3-flash-preview": "Gemini 3 Flash",
    "gpt-5-5-medium":         "GPT-5.5 (medium)",
    "gpt-5-4-mini-medium":    "GPT-5.4 mini (medium)",
    "gpt-5-2-medium":         "GPT-5.2 (medium)",
}

# Short stems for filenames (no spaces, no dots).
MODEL_SHORT = {
    "claude-opus-4-7":        "opus",
    "claude-sonnet-4-6":      "sonnet",
    "claude-haiku-4-5":       "haiku",
    "gemini-3-flash-preview": "gemini",
    "gpt-5-5-medium":         "gpt55",
    "gpt-5-4-mini-medium":    "gpt54mini",
    "gpt-5-2-medium":         "gpt52",
}

# Provider grouping for family-level panels.
MODEL_PROVIDER = {
    "claude-opus-4-7":        "Anthropic",
    "claude-sonnet-4-6":      "Anthropic",
    "claude-haiku-4-5":       "Anthropic",
    "gemini-3-flash-preview": "Google",
    "gpt-5-5-medium":         "OpenAI",
    "gpt-5-4-mini-medium":    "OpenAI",
    "gpt-5-2-medium":         "OpenAI",
}

# Per-provider hue families: deeper = larger model within family.
MODEL_COLOR = {
    "claude-opus-4-7":        "#0b3d6b",   # Anthropic deep
    "claude-sonnet-4-6":      "#3b73a8",   # Anthropic mid
    "claude-haiku-4-5":       "#9ec1de",   # Anthropic light
    "gemini-3-flash-preview": "#1f8a4d",   # Google green
    "gpt-5-5-medium":         "#7d2d2d",   # OpenAI deep
    "gpt-5-2-medium":         "#c46a3a",   # OpenAI mid
    "gpt-5-4-mini-medium":    "#e0a47a",   # OpenAI light
}

PROVIDER_COLOR = {
    "Anthropic": "#3b73a8",
    "Google":    "#1f8a4d",
    "OpenAI":    "#c46a3a",
}

TIER_PALETTE = ["#1f4e79", "#4b89c4", "#f2a541", "#c83c3c"]  # tiers 1..4


def apply_style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",

        "font.size":        13,
        "axes.titlesize":   16,
        "axes.labelsize":   15,
        "xtick.labelsize":  13,
        "ytick.labelsize":  13,
        "legend.fontsize":  11,
        "legend.title_fontsize": 11,

        "axes.titleweight":  "bold",
        "axes.labelweight":  "regular",
        "axes.linewidth":    1.3,
        "axes.edgecolor":    "#222222",
        "xtick.major.width": 1.2,
        "ytick.major.width": 1.2,
        "xtick.major.size":  4.5,
        "ytick.major.size":  4.5,
        "xtick.direction":   "out",
        "ytick.direction":   "out",
        "axes.spines.top":    False,
        "axes.spines.right":  False,

        "figure.dpi":       150,
        "savefig.dpi":      400,
        "savefig.bbox":     "tight",
        "savefig.pad_inches": 0.02,
        "savefig.facecolor": "white",

        "legend.frameon":   False,

        "grid.linewidth":   0.6,
        "grid.alpha":       0.30,
    })


def new_panel(size: tuple[float, float] = (3.1, 2.7)) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=size, layout="constrained")
    return fig, ax


def save_panel(fig: plt.Figure, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG_DIR / f"{stem}.{ext}")
    plt.close(fig)


def format_p(p: float) -> str:
    if p is None or (isinstance(p, float) and (p != p)):
        return "NA"
    if p < 0.001:
        return "<0.001"
    if p < 0.01:
        return f"{p:.3f}"
    return f"{p:.2f}"


def ensure_dirs() -> None:
    for d in (FIG_DIR, TABLE_DIR, OUT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def pair_label(a: str, b: str) -> str:
    return f"{MODEL_SHORT[a]}_vs_{MODEL_SHORT[b]}"


__all__ = [
    "apply_style", "new_panel", "save_panel", "format_p",
    "ensure_dirs", "pair_label",
    "PROJECT_ROOT", "WORK_ROOT", "FIG_DIR", "TABLE_DIR", "OUT_DIR",
    "MODEL_COLOR", "MODEL_LABEL", "MODEL_ORDER", "MODEL_SHORT",
    "MODEL_PROVIDER", "PROVIDER_COLOR", "TIER_PALETTE",
]
