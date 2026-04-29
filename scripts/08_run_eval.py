"""Step 8 — Run multi-agent evaluation on the corpus using Claude Code headless.

Invokes `claude -p` once per paper with --agents defining 5 specialists,
--append-system-prompt set to the orchestrator+chief instructions, and
--json-schema forcing the final answer to match shared/schema.json.

Output:
    results/<model_slug>/<pmcid>/run_<n>.json

Idempotent: skips runs whose output already exists.

Usage:
    .venv/bin/python scripts/08_run_eval.py --model opus --run 1 --limit 5
    .venv/bin/python scripts/08_run_eval.py --model opus --run 1       # full corpus
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from agents_config import build_agents  # noqa: E402

PROMPTS = config.PROJECT_ROOT / "prompts"
RESULTS = config.PROJECT_ROOT / "results"

MODEL_SLUG = {"opus": "claude-opus-4-7", "sonnet": "claude-sonnet-4-6"}


def build_user_prompt(pmcid: str, manuscript_md: str, model_slug: str, run_id: int) -> str:
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "# Manuscript under review\n\n"
        f"paper_id: {pmcid}\n"
        f"model: {model_slug}\n"
        f"architecture: multi-agent\n"
        f"run_id: {run_id}\n"
        f"timestamp: {timestamp}\n\n"
        "---\n\n"
        f"{manuscript_md}\n\n"
        "---\n\n"
        "# Task\n\n"
        "Invoke the five specialist sub-agents in parallel using the Task tool: "
        "`spec_methodological`, `spec_clinical_loe`, `spec_reporting`, "
        "`spec_novelty`, `spec_writing`. Pass each the full manuscript above.\n\n"
        "Each specialist will return a JSON object with their scores. "
        "Collect all five. Then act as the chief reviewer (see your system prompt) "
        "and synthesize them into the final consolidated JSON object matching the schema. "
        "Emit ONLY the final JSON as your last message — no Markdown, no commentary."
    )


def build_orchestrator_system_prompt() -> str:
    parts = [
        (PROMPTS / "orchestrator.md").read_text(),
        "\n\n---\n\n# Shared rubric\n\n",
        (PROMPTS / "shared" / "rubric.md").read_text(),
        "\n\n---\n\n# Chief reviewer synthesis instructions\n\n",
        (PROMPTS / "06_chief_reviewer.md").read_text(),
        "\n\nCRITICAL: Your FINAL message must be a single JSON object conforming "
        "exactly to the provided schema. No prose, no markdown fences.",
    ]
    return "".join(parts)


def run_one(pmcid: str, model: str, run_id: int, agents_json_path: Path,
            schema_path: Path, sys_prompt_path: Path, timeout: int = 900) -> dict | None:
    model_slug = MODEL_SLUG[model]
    out_dir = RESULTS / model_slug / pmcid
    out_path = out_dir / f"run_{run_id}.json"
    if out_path.exists() and out_path.stat().st_size > 100:
        return {"pmcid": pmcid, "status": "skipped_cached"}

    md_path = config.NORMALIZED_DIR / f"{pmcid}.md"
    if not md_path.exists():
        return {"pmcid": pmcid, "status": "error", "error": "missing manuscript"}
    manuscript = md_path.read_text()

    user_prompt = build_user_prompt(pmcid, manuscript, model_slug, run_id)

    cmd = [
        "claude", "-p", user_prompt,
        "--model", model,
        "--output-format", "json",
        "--json-schema", f"@{schema_path}",
        "--append-system-prompt", f"@{sys_prompt_path}",
        "--agents", f"@{agents_json_path}",
        "--tools", "Task",
        "--bare",
        "--no-session-persistence",
        "--settings", str(Path(__file__).resolve().parent / "eval_settings.json"),
    ]

    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"pmcid": pmcid, "status": "timeout"}
    elapsed = time.time() - start

    if proc.returncode != 0:
        return {"pmcid": pmcid, "status": "error", "error": proc.stderr[:500], "elapsed": elapsed}

    try:
        wrapper = json.loads(proc.stdout)
        result_str = wrapper.get("result", "") if isinstance(wrapper, dict) else proc.stdout
        result = json.loads(result_str)
    except Exception as e:  # noqa: BLE001
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"run_{run_id}.raw.txt").write_text(proc.stdout)
        return {"pmcid": pmcid, "status": "parse_error", "error": str(e), "elapsed": elapsed}

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    return {"pmcid": pmcid, "status": "ok", "elapsed": elapsed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(MODEL_SLUG), default="opus")
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--pmcids", nargs="*", help="Optional explicit PMCID list")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    tracker = pd.read_csv(config.PROJECT_ROOT / "corpus_tracker.csv", dtype=str).fillna("")
    tracker = tracker[tracker["md_exists"] == "True"]
    if args.pmcids:
        tracker = tracker[tracker["pmcid"].isin(args.pmcids)]
    tracker = tracker.sort_values(["tier", "journal_name", "pmcid"])
    if args.limit:
        tracker = tracker.head(args.limit)

    work_dir = RESULTS / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    agents_path = work_dir / "agents.json"
    schema_path = work_dir / "schema.json"
    sys_prompt_path = work_dir / "orchestrator_system.md"

    agents_path.write_text(json.dumps(build_agents(), indent=2))
    schema_path.write_text((PROMPTS / "shared" / "schema.json").read_text())
    sys_prompt_path.write_text(build_orchestrator_system_prompt())

    print(f"Running eval: model={args.model} run={args.run} papers={len(tracker)}")
    log = []
    for _, row in tqdm(tracker.iterrows(), total=len(tracker), desc="eval"):
        res = run_one(row["pmcid"], args.model, args.run, agents_path, schema_path, sys_prompt_path, timeout=args.timeout)
        log.append(res)
        status = res.get("status", "?")
        if status not in ("ok", "skipped_cached"):
            tqdm.write(f"  {row['pmcid']}: {status} {res.get('error','')[:120]}")

    log_df = pd.DataFrame(log)
    log_path = RESULTS / f"_log_{args.model}_run{args.run}.csv"
    log_df.to_csv(log_path, index=False)
    print("\n=== Run summary ===")
    print(log_df["status"].value_counts().to_string())
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
