"""Step 12 — Run multi-agent evaluation on the corpus using Cursor Agent headless.

Invokes `cursor agent -p` via the local Cursor installation:
- Runs 5 specialist reviews in parallel, each reading the manuscript + prompt files
  from the workspace in read-only ask mode.
- Runs 1 chief-reviewer synthesis pass over the manuscript + specialist JSON outputs.

Output:
    results/<results_slug>/<pmcid>/run_<n>.json

Idempotent: skips runs whose output already exists.

Usage:
    .venv/bin/python scripts/12_run_eval_cursor.py --model gpt-5.4 --run 1 --limit 5
    .venv/bin/python scripts/12_run_eval_cursor.py --model gpt-5.4 --run 1
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

PROMPTS = config.PROJECT_ROOT / "prompts"
RESULTS = config.PROJECT_ROOT / "results"
DEFAULT_CURSOR_BIN = Path("/Applications/Cursor.app/Contents/Resources/app/bin/cursor")

SPECIALIST_FILES = {
    "spec_methodological": "01_specialist_methodological.md",
    "spec_clinical_loe": "02_specialist_clinical_loe.md",
    "spec_reporting": "03_specialist_reporting.md",
    "spec_novelty": "04_specialist_novelty.md",
    "spec_writing": "05_specialist_writing.md",
}


def slugify_model(model_name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", model_name).strip("-").lower()


def resolve_cursor_binary(explicit_path: str | None) -> str:
    if explicit_path:
        return explicit_path
    if shutil.which("cursor"):
        return "cursor"
    if DEFAULT_CURSOR_BIN.exists():
        return str(DEFAULT_CURSOR_BIN)
    raise FileNotFoundError(
        "Could not find Cursor CLI. Install Cursor CLI or pass --cursor-binary explicitly."
    )


def ensure_cursor_login(cursor_bin: str, workspace: Path) -> None:
    proc = subprocess.run(
        [cursor_bin, "agent", "status"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=30,
    )
    status_text = (proc.stdout + "\n" + proc.stderr).strip()
    if proc.returncode != 0 or "not logged in" in status_text.lower():
        raise RuntimeError(
            "Cursor Agent is not logged in on this machine. Run "
            f"`{cursor_bin} agent login` once, then rerun this script."
        )


def build_specialist_prompt(
    pmcid: str,
    model_name: str,
    run_id: int,
    manuscript_rel: str,
    prompt_rel: str,
) -> str:
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "You are running one specialist review in a blinded oncology manuscript audit.\n\n"
        "Read these workspace files before answering:\n"
        f"1. `{manuscript_rel}`\n"
        "2. `prompts/shared/rubric.md`\n"
        f"3. `{prompt_rel}`\n\n"
        "Evaluation metadata:\n"
        f"- paper_id: {pmcid}\n"
        f"- model: {model_name}\n"
        "- architecture: multi-agent\n"
        f"- run_id: {run_id}\n"
        f"- timestamp: {timestamp}\n\n"
        "Instructions:\n"
        "- Use only the manuscript contents and the prompt files above.\n"
        "- Treat the manuscript as blinded; do not infer venue, authors, or institution.\n"
        "- Follow the specialist prompt exactly.\n"
        "- Return ONLY the specialist JSON object described in the specialist prompt.\n"
        "- Do not wrap the JSON in markdown fences and do not add commentary.\n"
    )


def build_specialist_retry_prompt(original_prompt: str) -> str:
    return (
        original_prompt
        + "\n\nYour previous answer was not valid JSON. Retry now and return only one valid JSON object."
    )


def build_chief_prompt(
    pmcid: str,
    model_name: str,
    run_id: int,
    manuscript_rel: str,
    specialist_paths_rel: dict[str, str],
) -> str:
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    specialist_list = "\n".join(
        f"- `{name}`: `{path}`" for name, path in specialist_paths_rel.items()
    )
    return (
        "You are the chief reviewer in a blinded multi-agent oncology manuscript audit.\n\n"
        "Read these workspace files before answering:\n"
        f"1. `{manuscript_rel}`\n"
        "2. `prompts/orchestrator.md`\n"
        "3. `prompts/shared/rubric.md`\n"
        "4. `prompts/06_chief_reviewer.md`\n"
        "5. `prompts/shared/schema.json`\n"
        "6. The specialist JSON outputs listed below:\n"
        f"{specialist_list}\n\n"
        "Evaluation metadata to use in the final JSON:\n"
        f"- paper_id: {pmcid}\n"
        f"- model: {model_name}\n"
        "- architecture: multi-agent\n"
        f"- run_id: {run_id}\n"
        f"- timestamp: {timestamp}\n\n"
        "Instructions:\n"
        "- Follow the orchestrator guidance, shared rubric, chief reviewer prompt, and schema.\n"
        "- Synthesize the listed specialist JSON outputs into one final review.\n"
        "- The final answer must be a single JSON object conforming exactly to `prompts/shared/schema.json`.\n"
        "- Set the top-level metadata fields exactly to the values listed above.\n"
        "- Return ONLY the final JSON object. No markdown fences and no commentary.\n"
    )


def build_chief_retry_prompt(original_prompt: str) -> str:
    return (
        original_prompt
        + "\n\nYour previous answer was not valid final JSON. Retry now and return only one valid JSON object matching the schema."
    )


def parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned.split("```json", 1)[1]
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        data = json.loads(cleaned[start : end + 1])
        if isinstance(data, dict):
            return data

    raise json.JSONDecodeError("Expected a JSON object", cleaned, 0)


def run_cursor_prompt(
    cursor_bin: str,
    workspace: Path,
    model_name: str,
    prompt: str,
    timeout: int,
) -> str:
    cmd = [
        cursor_bin,
        "agent",
        "-p",
        "--workspace",
        str(workspace),
        "--trust",
        "--mode",
        "ask",
        "--model",
        model_name,
        "--output-format",
        "json",
        prompt,
    ]
    proc = subprocess.run(
        cmd,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Cursor Agent call failed")

    wrapper = json.loads(proc.stdout)
    result = wrapper.get("result", "")
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError("Cursor Agent returned no final text result")
    return result


def call_json_agent(
    *,
    cursor_bin: str,
    workspace: Path,
    model_name: str,
    prompt: str,
    retry_prompt: str,
    timeout: int,
    raw_path: Path,
) -> dict:
    last_error: Exception | None = None
    last_output = ""
    for idx, active_prompt in enumerate((prompt, retry_prompt), start=1):
        try:
            last_output = run_cursor_prompt(cursor_bin, workspace, model_name, active_prompt, timeout)
            return parse_json_object(last_output)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(
                f"attempt={idx}\n\n{last_output}\n\nERROR:\n{exc}\n",
                encoding="utf-8",
            )
    assert last_error is not None
    raise last_error


def validate_result_shape(result: dict) -> None:
    required_top = {
        "paper_id",
        "model",
        "architecture",
        "run_id",
        "timestamp",
        "specialist_scores",
        "chief_reviewer",
    }
    missing_top = sorted(required_top - set(result))
    if missing_top:
        raise ValueError(f"Missing top-level keys: {', '.join(missing_top)}")

    specialist_required = {
        "methodological_rigor",
        "clinical_relevance_loe",
        "reporting_quality",
        "novelty_literature",
        "writing_presentation",
    }
    chief_required = {
        "overall_quality_1_10",
        "highest_tier_acceptance",
        "recommendation_at_that_tier",
        "key_strengths",
        "key_concerns",
        "predicted_hallucination_flag",
    }
    spec = result.get("specialist_scores")
    chief = result.get("chief_reviewer")
    if not isinstance(spec, dict):
        raise ValueError("`specialist_scores` must be an object")
    if not isinstance(chief, dict):
        raise ValueError("`chief_reviewer` must be an object")

    missing_spec = sorted(specialist_required - set(spec))
    missing_chief = sorted(chief_required - set(chief))
    if missing_spec:
        raise ValueError(f"Missing specialist score blocks: {', '.join(missing_spec)}")
    if missing_chief:
        raise ValueError(f"Missing chief reviewer fields: {', '.join(missing_chief)}")


def run_one(
    *,
    cursor_bin: str,
    workspace: Path,
    pmcid: str,
    model_name: str,
    results_slug: str,
    run_id: int,
    timeout: int,
    specialist_workers: int,
) -> dict:
    out_dir = RESULTS / results_slug / pmcid
    out_path = out_dir / f"run_{run_id}.json"
    if out_path.exists() and out_path.stat().st_size > 100:
        return {"pmcid": pmcid, "status": "skipped_cached"}

    manuscript_path = config.NORMALIZED_DIR / f"{pmcid}.md"
    if not manuscript_path.exists():
        return {"pmcid": pmcid, "status": "error", "error": "missing manuscript"}

    work_dir = RESULTS / "_cursor_work" / results_slug / pmcid / f"run_{run_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    manuscript_rel = manuscript_path.relative_to(workspace).as_posix()

    start = time.time()
    specialist_jsons: dict[str, dict] = {}

    def _run_specialist(name: str, prompt_file: str) -> tuple[str, dict]:
        prompt_rel = (PROMPTS / prompt_file).relative_to(workspace).as_posix()
        raw_path = work_dir / f"{name}.raw.txt"
        prompt = build_specialist_prompt(pmcid, model_name, run_id, manuscript_rel, prompt_rel)
        parsed = call_json_agent(
            cursor_bin=cursor_bin,
            workspace=workspace,
            model_name=model_name,
            prompt=prompt,
            retry_prompt=build_specialist_retry_prompt(prompt),
            timeout=timeout,
            raw_path=raw_path,
        )
        return name, parsed

    try:
        with ThreadPoolExecutor(max_workers=max(1, specialist_workers)) as pool:
            futures = [
                pool.submit(_run_specialist, name, prompt_file)
                for name, prompt_file in SPECIALIST_FILES.items()
            ]
            for future in as_completed(futures):
                name, parsed = future.result()
                specialist_jsons[name] = parsed
    except subprocess.TimeoutExpired:
        return {"pmcid": pmcid, "status": "timeout_specialist", "elapsed": time.time() - start}
    except Exception as exc:  # noqa: BLE001
        return {
            "pmcid": pmcid,
            "status": "error_specialist",
            "error": str(exc)[:500],
            "elapsed": time.time() - start,
        }

    specialist_paths_rel: dict[str, str] = {}
    for name, parsed in specialist_jsons.items():
        sp_path = work_dir / f"{name}.json"
        sp_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        specialist_paths_rel[name] = sp_path.relative_to(workspace).as_posix()

    chief_raw = out_dir / f"run_{run_id}.raw.txt"
    prompt = build_chief_prompt(pmcid, model_name, run_id, manuscript_rel, specialist_paths_rel)
    try:
        final_json = call_json_agent(
            cursor_bin=cursor_bin,
            workspace=workspace,
            model_name=model_name,
            prompt=prompt,
            retry_prompt=build_chief_retry_prompt(prompt),
            timeout=timeout,
            raw_path=chief_raw,
        )
        final_json["paper_id"] = pmcid
        final_json["model"] = model_name
        final_json["architecture"] = "multi-agent"
        final_json["run_id"] = run_id
        final_json.setdefault("timestamp", dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
        validate_result_shape(final_json)
    except subprocess.TimeoutExpired:
        return {"pmcid": pmcid, "status": "timeout_chief", "elapsed": time.time() - start}
    except Exception as exc:  # noqa: BLE001
        return {
            "pmcid": pmcid,
            "status": "parse_error",
            "error": str(exc)[:500],
            "elapsed": time.time() - start,
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(final_json, indent=2), encoding="utf-8")
    shutil.rmtree(work_dir, ignore_errors=True)
    if chief_raw.exists():
        chief_raw.unlink()
    return {"pmcid": pmcid, "status": "ok", "elapsed": time.time() - start}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.4", help="Cursor model slug (default: gpt-5.4)")
    ap.add_argument(
        "--results-slug",
        default=None,
        help="Results subdirectory under results/ (default: slugified model name)",
    )
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--pmcids", nargs="*", help="Optional explicit PMCID list")
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument(
        "--specialist-workers",
        type=int,
        default=5,
        help="Parallel specialist Cursor calls per paper (default: 5)",
    )
    ap.add_argument(
        "--cursor-binary",
        default=None,
        help="Path to Cursor CLI binary (default: PATH lookup, then Cursor.app bundle)",
    )
    args = ap.parse_args()

    workspace = config.PROJECT_ROOT.resolve()
    cursor_bin = resolve_cursor_binary(args.cursor_binary)
    ensure_cursor_login(cursor_bin, workspace)

    tracker = pd.read_csv(config.PROJECT_ROOT / "corpus_tracker.csv", dtype=str).fillna("")
    tracker = tracker[tracker["md_exists"] == "True"]
    if args.pmcids:
        tracker = tracker[tracker["pmcid"].isin(args.pmcids)]
    tracker = tracker.sort_values(["tier", "journal_name", "pmcid"])
    if args.limit:
        tracker = tracker.head(args.limit)

    results_slug = args.results_slug or slugify_model(args.model)
    print(
        f"Running eval via Cursor Agent: model={args.model} results_slug={results_slug} "
        f"run={args.run} papers={len(tracker)}"
    )
    log: list[dict] = []
    for _, row in tqdm(tracker.iterrows(), total=len(tracker), desc="eval"):
        res = run_one(
            cursor_bin=cursor_bin,
            workspace=workspace,
            pmcid=row["pmcid"],
            model_name=args.model,
            results_slug=results_slug,
            run_id=args.run,
            timeout=args.timeout,
            specialist_workers=args.specialist_workers,
        )
        log.append(res)
        status = res.get("status", "?")
        if status not in ("ok", "skipped_cached"):
            tqdm.write(f"  {row['pmcid']}: {status} {res.get('error', '')[:120]}")

    log_df = pd.DataFrame(log)
    log_path = RESULTS / f"_log_{results_slug}_run{args.run}.csv"
    log_df.to_csv(log_path, index=False)
    print("\n=== Run summary ===")
    print(log_df["status"].value_counts().to_string())
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
