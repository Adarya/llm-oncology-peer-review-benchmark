"""Counts per model and run of the fields recorded in the output files: model string, architecture label
and timestamp (the timestamp is written by the model as part of its JSON answer).
Output: results/run_metadata.csv
"""

import pandas as pd

from common import LABEL, MODELS, load_runs, save


def main():
    L = load_runs()
    rows = []
    for (m, r), g in L.groupby(["model", "run"]):
        ts = pd.to_datetime(g.timestamp, errors="coerce", utc=True)
        rows.append({"model": LABEL[m], "run": r, "n_output_files": len(g),
                     "n_with_valid_tier": int(g.pred_tier.notna().sum()),
                     "model_string_in_output": "; ".join(f"{k} ({v})" for k, v in
                                                        g.model_string_in_output.fillna("none").value_counts().items()),
                     "architecture_label_in_output": "; ".join(f"{k} ({v})" for k, v in
                                                              g.architecture.fillna("none").value_counts().items()),
                     "first_timestamp": ts.min(), "last_timestamp": ts.max(),
                     "n_distinct_timestamps": ts.nunique(),
                     "n_timestamps_outside_18apr_to_04may_2026": int(((ts < "2026-04-18") | (ts > "2026-05-05")).sum()),
                     "n_timestamps_exactly_midnight": int((ts.dt.strftime("%H:%M:%S") == "00:00:00").sum())})
    out = pd.DataFrame(rows)
    out["order"] = out.model.map({LABEL[m]: i for i, m in enumerate(MODELS)})
    out = out.sort_values(["order", "run"]).drop(columns="order")
    save(out, "run_metadata.csv")
    pd.set_option("display.width", 250, "display.max_colwidth", 80)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
