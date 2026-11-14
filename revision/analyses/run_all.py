"""Run all analysis scripts in order; each writes its CSVs to revision/analyses/results/.
Usage, from the repository root: python revision/analyses/run_all.py
"""

import importlib
import time

STEPS = [
    "reproduce_table1",
    "agreement_measures",
    "journal_clustering",
    "model_differences",
    "missing_outputs",
    "repeatability",
    "subgroups",
    "output_consistency",
    "predicted_tier_distribution",
    "original_496_records",
    "run_metadata",
    "baselines",
    "retiering_by_jcr",
    "publication_dates",
    "recognition_vs_agreement",
    "auroc_tier_discrimination",
]

if __name__ == "__main__":
    for name in STEPS:
        t = time.time()
        print(f"\n{'=' * 20} {name} {'=' * 20}")
        importlib.import_module(name).main()
        print(f"[{name} done in {time.time() - t:.0f}s]")
