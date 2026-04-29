"""Step 11 — Run multi-agent evaluation on the corpus using Gemini 3.1 Pro via API.

Invokes `google-genai` natively in Python:
- Spawns 5 parallel threads, each calling the Gemini API for a specialist.
- Synthesizes their outputs with a Chief Reviewer prompt.
- Forces the final answer to match shared/schema.json using structured outputs.

Output:
    results/<model_slug>/<pmcid>/run_<n>.json

Idempotent: skips runs whose output already exists.

Usage:
    export GEMINI_API_KEY="..."
    .venv/bin/python scripts/11_run_eval_gemini.py --model gemini-3.1-pro --run 1 --limit 5
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from tqdm import tqdm
from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import importlib
import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential
agents_config = importlib.import_module("11_agents_config_gemini")
build_specialist_prompts = agents_config.build_specialist_prompts
build_orchestrator_system_prompt = agents_config.build_orchestrator_system_prompt

PROMPTS = config.PROJECT_ROOT / "prompts"
RESULTS = config.PROJECT_ROOT / "results"

# Standardize the slug for paths
def get_model_slug(model_name: str) -> str:
    return model_name.replace(".", "-")

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
        f"{manuscript_md}\n"
    )

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=10), reraise=True)
def _call_specialist_api(client: genai.Client, model: str, system_prompt: str, user_prompt: str) -> str:
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
            response_mime_type="application/json"
        )
    )
    return response.text

def _call_specialist(client: genai.Client, model: str, name: str, system_prompt: str, user_prompt: str) -> dict:
    """Invokes a specialist sub-agent and returns the JSON output."""
    try:
        response_text = _call_specialist_api(client, model, system_prompt, user_prompt)
        return {"name": name, "output": json.loads(response_text), "error": None}
    except Exception as e:
        return {"name": name, "output": None, "error": str(e)}

def run_one(client: genai.Client, pmcid: str, model: str, run_id: int, 
            schema_dict: dict, specialist_prompts: dict[str, str], orchestrator_prompt: str) -> dict | None:
    
    model_slug = get_model_slug(model)
    out_dir = RESULTS / model_slug / pmcid
    out_path = out_dir / f"run_{run_id}.json"
    raw_path = out_dir / f"run_{run_id}.raw.txt"
    
    if out_path.exists() and out_path.stat().st_size > 100:
        return {"pmcid": pmcid, "status": "skipped_cached"}

    md_path = config.NORMALIZED_DIR / f"{pmcid}.md"
    if not md_path.exists():
        return {"pmcid": pmcid, "status": "error", "error": "missing manuscript"}
    manuscript = md_path.read_text()

    user_prompt = build_user_prompt(pmcid, manuscript, model_slug, run_id)
    
    start = time.time()
    
    specialist_results = {}
    for name, sp_prompt in specialist_prompts.items():
        res = _call_specialist(client, model, name, sp_prompt, user_prompt)
        if res["error"]:
            elapsed = time.time() - start
            return {"pmcid": pmcid, "status": f"error_{res['name']}", "error": res["error"], "elapsed": elapsed}
        specialist_results[res["name"]] = res["output"]
            
    # Assemble specialist results for Chief Reviewer
    chief_input_blocks = [user_prompt, "\n\n# Sub-agent outputs\n\n"]
    for name, output_dict in specialist_results.items():
        chief_input_blocks.append(f"## {name}\n```json\n{json.dumps(output_dict, indent=2)}\n```\n\n")
    
    chief_user_prompt = "".join(chief_input_blocks) + "\n\nSynthesize these into the final structured JSON object matching the schema."

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=10), reraise=True)
    def _call_chief():
        return client.models.generate_content(
            model=model,
            contents=chief_user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=orchestrator_prompt,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=schema_dict
            )
        )

    # Phase 2: Chief Reviewer synthesis (forced JSON schema)
    try:
        response = _call_chief()
        
        result_text = response.text
        # Safety fallback parsing
        if result_text.startswith("```json"):
            result_text = result_text.split("```json")[-1].split("```")[0].strip()
        elif result_text.startswith("```"):
            result_text = result_text.split("```")[-1].split("```")[0].strip()
            
        final_json = json.loads(result_text)
        
    except Exception as e:
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(str(e))
        elapsed = time.time() - start
        return {"pmcid": pmcid, "status": "parse_error", "error": str(e), "elapsed": elapsed}

    elapsed = time.time() - start
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(final_json, indent=2))
    
    return {"pmcid": pmcid, "status": "ok", "elapsed": elapsed}

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.1-pro", help="Model name to use with GenAI SDK")
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--pmcids", nargs="*", help="Optional explicit PMCID list")
    args = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = genai.Client()

    tracker = pd.read_csv(config.PROJECT_ROOT / "corpus_tracker.csv", dtype=str).fillna("")
    tracker = tracker[tracker["md_exists"] == "True"]
    if args.pmcids:
        tracker = tracker[tracker["pmcid"].isin(args.pmcids)]
    tracker = tracker.sort_values(["tier", "journal_name", "pmcid"])
    if args.limit:
        tracker = tracker.head(args.limit)

    schema_dict = json.loads((PROMPTS / "shared" / "schema.json").read_text())
    
    def sanitize_schema(d):
        if isinstance(d, dict):
            return {k: sanitize_schema(v) for k, v in d.items() if k not in ["$schema", "additionalProperties"]}
        elif isinstance(d, list):
            return [sanitize_schema(v) for v in d]
        return d
        
    schema_dict = sanitize_schema(schema_dict)
    
    specialist_prompts = build_specialist_prompts()
    orchestrator_prompt = build_orchestrator_system_prompt()

    print(f"Running eval via Gemini: model={args.model} run={args.run} papers={len(tracker)}")
    log = []
    
    log_df = pd.DataFrame(log)
    model_slug = get_model_slug(args.model)
    log_path = RESULTS / f"_log_{model_slug}_run{args.run}.csv"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize the CSV with headers if it doesn't exist
    if not log_path.exists():
        pd.DataFrame([]).to_csv(log_path, index=False)
    
    for _, row in tqdm(tracker.iterrows(), total=len(tracker), desc="eval"):
        res = run_one(client, row["pmcid"], args.model, args.run, 
                      schema_dict, specialist_prompts, orchestrator_prompt)
        log.append(res)
        
        # Continuously append to CSV for live tracking
        pd.DataFrame([res]).to_csv(log_path, mode='a', header=not log_path.exists(), index=False)
        
        status = res.get("status", "?")
        if status not in ("ok", "skipped_cached"):
            tqdm.write(f"  {row['pmcid']}: {status} {res.get('error','')[:120]}")

    print("\n=== Run summary ===")
    print(pd.DataFrame(log)["status"].value_counts().to_string())
    print(f"Log: {log_path}")

if __name__ == "__main__":
    main()
