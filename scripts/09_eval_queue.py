"""Build / refresh the evaluation queue CSV.

Status values: pending | running | done | error

Usage:
    .venv/bin/python scripts/09_eval_queue.py          # rebuild from scratch
    .venv/bin/python scripts/09_eval_queue.py --status # show current status counts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

MODEL_SLUG = "claude-opus-4-7"
RUN_ID = 1
QUEUE_PATH = config.PROJECT_ROOT / "eval_queue.csv"
RESULTS = config.PROJECT_ROOT / "results" / MODEL_SLUG


def scan_results() -> dict[str, dict]:
    out = {}
    if not RESULTS.exists():
        return out
    for d in RESULTS.iterdir():
        if not d.is_dir():
            continue
        rp = d / f"run_{RUN_ID}.json"
        if not rp.exists():
            continue
        try:
            r = json.loads(rp.read_text())
            out[d.name] = {
                "status": "done",
                "overall_quality_1_10": r.get("chief_reviewer", {}).get("overall_quality_1_10"),
                "highest_tier_acceptance": r.get("chief_reviewer", {}).get("highest_tier_acceptance"),
                "architecture": r.get("architecture"),
            }
        except Exception as e:  # noqa: BLE001
            out[d.name] = {"status": "error", "error": str(e)[:200]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="show counts and exit")
    args = ap.parse_args()

    tracker = pd.read_csv(config.PROJECT_ROOT / "corpus_tracker.csv", dtype=str).fillna("")
    tracker = tracker[tracker["md_exists"] == "True"].copy()

    if QUEUE_PATH.exists():
        q = pd.read_csv(QUEUE_PATH, dtype=str).fillna("")
    else:
        q = tracker[["tier", "journal_name", "pmcid"]].copy()
        q["status"] = "pending"
        q["overall_quality_1_10"] = ""
        q["highest_tier_acceptance"] = ""
        q["architecture"] = ""
        q["error"] = ""

    # Refresh from disk: rows with results → status + fields; rows without → pending + cleared
    done = scan_results()
    have = set(done.keys())
    for pmcid in q["pmcid"]:
        mask = q["pmcid"] == pmcid
        if pmcid in have:
            info = done[pmcid]
            for k, v in info.items():
                if k in q.columns:
                    q.loc[mask, k] = "" if v is None else str(v)
        else:
            q.loc[mask, "status"] = "pending"
            for col in ("overall_quality_1_10", "highest_tier_acceptance", "architecture", "error"):
                if col in q.columns:
                    q.loc[mask, col] = ""

    q.to_csv(QUEUE_PATH, index=False)

    if args.status:
        print("\n=== Eval queue status ===")
        print(q["status"].value_counts().to_string())
        done_df = q[q["status"] == "done"]
        if len(done_df):
            print(f"\nDone: {len(done_df)}")
            print("Tier distribution of done papers:")
            print(done_df["tier"].value_counts().sort_index().to_string())
            print("\nPredicted-tier distribution:")
            pred = done_df["highest_tier_acceptance"].value_counts().sort_index()
            print(pred.to_string())
    else:
        print(f"Wrote {QUEUE_PATH} ({len(q)} rows)")


if __name__ == "__main__":
    main()
