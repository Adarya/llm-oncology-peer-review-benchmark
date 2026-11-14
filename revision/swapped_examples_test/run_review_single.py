"""Swapped-examples test runner: one `claude -p` call per manuscript, without tools, with the rubric, the five
specialist prompts and the chief prompt in the system prompt and the output schema enforced.
--arm control uses prompts/06_chief_reviewer.md (logs in original_examples/); --arm swap uses
prompts_swap/06_chief_reviewer_swapped_examples.md (logs in swapped_examples/). Needs corpus/normalized/ (not distributed).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PROMPTS = ROOT / "prompts"
MODEL = "claude-opus-4-7"
CWD = OUT / "_cwd"
SPECIALISTS = ["01_specialist_methodological.md", "02_specialist_clinical_loe.md", "03_specialist_reporting.md",
               "04_specialist_novelty.md", "05_specialist_writing.md"]
ARMS = {
    "control": {"chief": PROMPTS / "06_chief_reviewer.md", "text": ROOT / "corpus/normalized"},
    "swap": {"chief": OUT / "prompts_swap/06_chief_reviewer_swapped_examples.md", "text": ROOT / "corpus/normalized"},
}
LOG_DIR = {"control": OUT / "original_examples", "swap": OUT / "swapped_examples"}
STOP = threading.Event()
LIMIT_MESSAGES = ("spend limit", "usage limit", "rate limit", "hit your limit")


def build_system_prompt(chief: Path) -> str:
    parts = [
        "# Single-pass oncology manuscript review\n\n"
        "You review one blinded oncology manuscript. Work through the five specialist assessments below "
        "yourself, one after another, each judged only by its own instructions; then act as the chief "
        "reviewer and synthesize them. Never use prior knowledge about the paper's authors, institution or "
        "publication venue. `architecture` must be \"single-agent\".",
        "\n\n---\n\n# Shared rubric\n\n" + (PROMPTS / "shared/rubric.md").read_text(),
    ]
    for i, f in enumerate(SPECIALISTS, start=1):
        parts.append(f"\n\n---\n\n# Specialist {i} of 5\n\n" + (PROMPTS / f).read_text())
    parts.append("\n\n---\n\n# Chief reviewer synthesis instructions\n\n" + chief.read_text())
    parts.append("\n\nCRITICAL: Your FINAL message must be a single JSON object conforming exactly to the "
                 "provided schema. No prose, no markdown fences, no commentary.")
    return "".join(parts)


def build_user_prompt(pmcid: str, manuscript_md: str, run_id: int) -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "# Manuscript under review\n\n"
        f"paper_id: {pmcid}\n"
        f"model: {MODEL}\n"
        "architecture: single-agent\n"
        f"run_id: {run_id}\n"
        f"timestamp: {timestamp}\n\n"
        "---\n\n"
        f"{manuscript_md}\n\n"
        "---\n\n"
        "# Task\n\n"
        "Carry out the five specialist assessments in order, then the chief reviewer synthesis, and emit "
        "ONLY the final JSON object matching the schema."
    )


def sha(x) -> str:
    return hashlib.sha256(x.read_bytes() if isinstance(x, Path) else x.encode()).hexdigest()


def run_one(pmcid: str, arm: str, files: dict, cli_version: str, run_id: int = 1) -> dict:
    out_dir = LOG_DIR[arm]
    out_path = out_dir / f"{pmcid}.json"
    if out_path.exists():
        return json.loads(out_path.read_text())
    if STOP.is_set() or (OUT / "STOP").exists():
        STOP.set()
        return {"pmcid": pmcid, "skipped": True}
    manuscript = (ARMS[arm]["text"] / f"{pmcid}.md").read_text()
    user_prompt = build_user_prompt(pmcid, manuscript, run_id)
    argv = [
        "claude", "-p", user_prompt,
        "--model", MODEL,
        "--output-format", "json",
        "--json-schema", files["schema_inline"],
        "--append-system-prompt-file", str(files["system"]),
        "--tools", "",
        "--no-session-persistence",
        "--settings", str(ROOT / "scripts/eval_settings.json"),
        "--setting-sources", "",
        "--strict-mcp-config",
        "--disable-slash-commands",
    ]
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.time()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, cwd=CWD, timeout=1200,
                              stdin=subprocess.DEVNULL)
        stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, rc = "", "timeout", -1
    rec = {
        "pmcid": pmcid, "arm": arm, "model_requested": MODEL, "cli_version": cli_version,
        "argv": argv[:2] + ["<user prompt elided>"] + argv[3:],
        "sha256": {"manuscript": sha(manuscript), "user_prompt": sha(user_prompt),
                   "system_prompt": sha(files["system"]), "schema": sha(files["schema"])},
        "started_utc": started, "elapsed_s": round(time.time() - t0, 1),
        "returncode": rc, "stdout": stdout, "stderr": stderr[-2000:],
    }
    try:
        wrapper = json.loads(stdout)
        rec["models_used"] = list((wrapper.get("modelUsage") or {}).keys())
        rec["total_cost_usd"] = wrapper.get("total_cost_usd")
        res = wrapper.get("structured_output") or wrapper.get("result")
        rec["review"] = res if isinstance(res, dict) else json.loads(res)
        rec["tier"] = int(rec["review"]["chief_reviewer"]["highest_tier_acceptance"])
    except Exception as e:  # noqa: BLE001
        rec["parse_error"] = repr(e)
        if any(m in (stdout + stderr).lower() for m in LIMIT_MESSAGES):
            STOP.set()
            print(f"STOPPING: limit message for {pmcid}", flush=True)
    out_dir.mkdir(exist_ok=True)
    print(f"{dt.datetime.now():%H:%M} {pmcid} tier={rec.get('tier', 'FAILED')} "
          f"cost=${rec.get('total_cost_usd') or 0:.2f} {rec['elapsed_s']:.0f}s", flush=True)
    if "tier" in rec:
        out_path.write_text(json.dumps(rec, indent=2))
    else:
        (out_dir / f"{pmcid}.failed.json").write_text(json.dumps(rec, indent=2))
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=list(ARMS), required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sample", default="sample.csv")
    ap.add_argument("--tiers", help="comma-separated tiers to include, e.g. 4")
    args = ap.parse_args()
    CWD.mkdir(exist_ok=True)
    work = OUT / f"_work_{args.arm}"
    work.mkdir(exist_ok=True)
    files = {"system": work / "system_prompt.md", "schema": PROMPTS / "shared/schema.json"}
    files["system"].write_text(build_system_prompt(ARMS[args.arm]["chief"]))
    # the "$schema" key is not accepted by the CLI validator and is removed
    schema = json.loads(files["schema"].read_text())
    schema.pop("$schema", None)
    files["schema_inline"] = json.dumps(schema)
    cli_version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()

    sample = pd.read_csv(OUT / args.sample)
    if args.tiers:
        sample = sample[sample.tier.isin([int(t) for t in args.tiers.split(",")])]
    pmcids = list(sample.pmcid)[: args.limit]
    with ThreadPoolExecutor(args.workers) as ex:
        recs = list(ex.map(lambda p: run_one(p, args.arm, files, cli_version), pmcids))
    ok = [r for r in recs if "tier" in r]
    skipped = sum(1 for r in recs if r.get("skipped"))
    print(f"{args.arm}: {len(ok)}/{len(recs)} ok, {skipped} not started (stopped); CLI {cli_version}")
    for r in recs:
        if "tier" not in r and not r.get("skipped"):
            print("FAILED", r["pmcid"], r.get("parse_error"), r["stderr"][-300:], r["stdout"][-300:])


if __name__ == "__main__":
    main()
