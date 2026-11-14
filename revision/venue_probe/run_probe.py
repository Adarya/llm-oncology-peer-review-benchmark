"""Venue probe runner: one `claude -p` call per manuscript in sample_probe.csv, without tools; the model is
asked which of the 14 source journals published the text. --text original reads corpus/normalized/<pmcid>.md,
--text cleaned reads cleaned/<pmcid>.md (written by clean.py); the article texts are not distributed.
Each call is logged to probe_<model>_<text>/<pmcid>.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MODEL = "claude-opus-4-7"  # overridden by --model
# Empty working directory for the CLI calls.
CWD = OUT / "_cwd"

SYSTEM = "You are an expert in oncology research publishing."

TEMPLATE = """Below is an oncology research article. The journal name, authors, affiliations and identifiers were removed before you received it.

It was published in exactly one of these 14 journals (alphabetical order):
{journals}

Which journal published it? Reply with ONLY a JSON object, no other text:
{{"journal_guess": "<one name copied exactly from the list>", "second_guess": "<another name from the list>", "confidence": <integer 0-100, your probability that journal_guess is correct>, "cues": "<one sentence naming the cues you used>"}}

---

{manuscript}
"""


def run_one(pmcid: str, journals: list[str], cli_version: str, text: str) -> dict:
    raw = OUT / f"probe_{MODEL}_{text}"
    out_path = raw / f"{pmcid}.json"
    if out_path.exists():
        return json.loads(out_path.read_text())
    src = ROOT / f"corpus/normalized/{pmcid}.md" if text == "original" else OUT / text / f"{pmcid}.md"
    manuscript = src.read_text()
    prompt = TEMPLATE.format(journals="\n".join(f"- {j}" for j in journals), manuscript=manuscript)
    argv = ["claude", "-p", prompt, "--model", MODEL, "--output-format", "json",
            "--system-prompt", SYSTEM, "--tools", "", "--setting-sources", "",
            "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"]
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.time()
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=CWD, timeout=600)
    rec = {
        "pmcid": pmcid,
        "text": text,
        "manuscript_sha256": hashlib.sha256(manuscript.encode()).hexdigest(),
        "model_requested": MODEL,
        "cli_version": cli_version,
        "argv": argv[:2] + ["<prompt elided>"] + argv[3:],
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "system_prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
        "started_utc": started,
        "elapsed_s": round(time.time() - t0, 1),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr[-2000:],
    }
    try:
        wrapper = json.loads(proc.stdout)
        rec["models_used"] = list((wrapper.get("modelUsage") or {}).keys())
        text = wrapper.get("result", "")
        rec["answer"] = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    except Exception as e:  # noqa: BLE001
        rec["parse_error"] = str(e)
    if "answer" in rec:  # only parsed answers are saved; other calls are repeated on rerun
        out_path.write_text(json.dumps(rec, indent=2))
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--text", default="original", help="original | cleaned (folder of cleaned .md)")
    ap.add_argument("--model", default="claude-opus-4-7")
    args = ap.parse_args()
    global MODEL
    MODEL = args.model
    (OUT / f"probe_{MODEL}_{args.text}").mkdir(parents=True, exist_ok=True)
    CWD.mkdir(exist_ok=True)

    sample = pd.read_csv(OUT / "sample_probe.csv")
    # the 14 source journals
    journals = sorted(pd.read_csv(ROOT / "corpus_tracker.csv", dtype=str).journal_name.unique())
    assert len(journals) == 14, journals
    cli_version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()

    with ThreadPoolExecutor(args.workers) as ex:
        recs = list(ex.map(lambda p: run_one(p, journals, cli_version, args.text), sample.pmcid))

    ok = sum("answer" in r for r in recs)
    print(f"done: {ok}/{len(recs)} parsed; CLI {cli_version}")
    for r in recs:
        if "answer" not in r:
            print("FAILED", r["pmcid"], r.get("parse_error"), r["stderr"][-300:])


if __name__ == "__main__":
    main()
