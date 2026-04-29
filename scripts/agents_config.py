"""Build the --agents JSON that defines the 5 specialist sub-agents for Claude Code.

Each specialist gets its prompt from prompts/ and the shared rubric appended.
"""

from __future__ import annotations

import json
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

SPECIALIST_DESCRIPTIONS = {
    "spec_methodological": "Biostatistics/methods reviewer — scores methodological rigor + statistical appropriateness.",
    "spec_clinical_loe":   "Oncologist reviewer — assigns Oxford LoE + scores clinical/translational relevance.",
    "spec_reporting":      "Methods reviewer — identifies the applicable reporting standard, scores adherence + data/code availability.",
    "spec_novelty":        "Senior scientist reviewer — scores novelty and positioning vs prior literature.",
    "spec_writing":        "Scientific editor — scores writing, organization, and presentation quality.",
}


def build_agents() -> dict:
    agents = {}
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
        agents[agent_name] = {
            "description": SPECIALIST_DESCRIPTIONS[agent_name],
            "prompt": system,
        }
    return agents


if __name__ == "__main__":
    print(json.dumps(build_agents(), indent=2))
