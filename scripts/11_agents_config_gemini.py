"""Build prompts for Gemini multi-agent evaluation.

Each specialist gets its prompt from prompts/ and the shared rubric appended.
The orchestrator gets the chief reviewer synthesis instructions.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

PROMPTS = config.PROJECT_ROOT / "prompts"
RUBRIC = (PROMPTS / "shared" / "rubric.md").read_text()

SPECIALIST_FILES = {
    "spec_methodological":  "01_specialist_methodological.md",
    "spec_clinical_loe":    "02_specialist_clinical_loe.md",
    "spec_reporting":       "03_specialist_reporting.md",
    "spec_novelty":         "04_specialist_novelty.md",
    "spec_writing":         "05_specialist_writing.md",
}


def build_specialist_prompts() -> dict[str, str]:
    prompts = {}
    for agent_name, fname in SPECIALIST_FILES.items():
        prompt = (PROMPTS / fname).read_text()
        system = (
            "# Shared rubric\n\n"
            + RUBRIC
            + "\n\n---\n\n"
            + prompt
            + "\n\nCRITICAL: Return ONLY the JSON object described above. "
              "No prose, no markdown fences, no commentary."
        )
        prompts[agent_name] = system
    return prompts


def build_orchestrator_system_prompt() -> str:
    parts = [
        (PROMPTS / "orchestrator.md").read_text(),
        "\n\n---\n\n# Shared rubric\n\n",
        RUBRIC,
        "\n\n---\n\n# Chief reviewer synthesis instructions\n\n",
        (PROMPTS / "06_chief_reviewer.md").read_text(),
        "\n\nCRITICAL: Your FINAL message must be a single JSON object conforming "
        "exactly to the provided schema. No prose, no markdown fences."
    ]
    return "".join(parts)
