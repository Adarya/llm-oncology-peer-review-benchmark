"""Kappa per model (run 1) by earliest public date relative to the corpus window and to each model's training
cutoff, and exact agreement before versus after the cutoff within tier and within journal.
Input: revision/data/publication_dates.csv (rewritten from corpus/raw/ and Europe PMC when the XML is present).
Outputs: results/post_cutoff_sensitivity.csv, before_vs_after_cutoff_within_tier.csv, before_vs_after_cutoff_within_journal.csv
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from common import DATA, ROOT, analytic_sample, bootstrap, kappa, save, wide

RAW = ROOT / "corpus" / "raw"
DATES_CSV = DATA / "publication_dates.csv"
WINDOW_START = dt.date(2026, 2, 1)
# Training cutoffs published by the providers; end of month where only a month is given.
CUTOFF = {
    "claude-opus-4-7": dt.date(2026, 1, 31),
    "claude-sonnet-4-6": dt.date(2026, 1, 31),
    "gpt-5-5-medium": dt.date(2025, 12, 1),
    "gpt-5-2-medium": dt.date(2025, 8, 31),
    "gpt-5-4-mini-medium": dt.date(2025, 8, 31),
    "claude-haiku-4-5": dt.date(2025, 7, 31),
    "gemini-3-flash-preview": dt.date(2025, 1, 31),
}
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
MEETING = re.compile(r"presented[^.]{0,80}\b(?:meeting|congress|conference|symposium|"
                     r"ASCO|ESMO|AACR|ASH|SABCS|ASTRO|WCLC|SNMMI|annual)\b", re.I)


def _date(node: str) -> dt.date | None:
    y = re.search(r"<year>(\d{4})</year>", node)
    if not y:
        return None
    m = re.search(r"<month>(\d{1,2})</month>", node)
    d = re.search(r"<day>(\d{1,2})</day>", node)
    return dt.date(int(y.group(1)), int(m.group(1)) if m else 1, int(d.group(1)) if d else 1)


def xml_dates(pmcid: str) -> dict:
    x = (RAW / f"{pmcid}.xml").read_text(errors="ignore")
    out = {}
    for m in re.finditer(r'<pub-date([^>]*)>(.*?)</pub-date>', x, re.S):
        attrs, d = m.group(1), _date(m.group(2))
        kind = re.search(r'(?:pub-type|date-type)="([^"]+)"', attrs)
        if not (d and kind):
            continue
        k = kind.group(1)
        if k == "pub" and 'publication-format="electronic"' in attrs:
            k = "epub"
        out.setdefault(k, d)
    for m in re.finditer(r'<date date-type="([^"]+)"[^>]*>(.*?)</date>', x, re.S):
        d = _date(m.group(2))
        if d:
            out.setdefault("history_" + m.group(1), d)
    body = re.sub(r"<ref-list.*?</ref-list>", " ", x, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    hits = [re.sub(r"\s+", " ", body[max(0, h.start() - 120): h.end() + 160]) for h in MEETING.finditer(body)]
    out["meeting_statement"] = " | ".join(hits)
    return out


def epmc(query: str, page_size: int = 100) -> list[dict]:
    url = EPMC + "?" + urllib.parse.urlencode({"query": query, "format": "json", "pageSize": page_size,
                                               "resultType": "core"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)["resultList"]["result"]
        except Exception:  # noqa: BLE001
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(query[:80])


def preprints(pmcids: list[str]) -> dict[str, str]:
    """PMCID -> earliest first-publication date of a linked preprint (Europe PMC)."""
    flagged = []
    for i in range(0, len(pmcids), 40):
        chunk = pmcids[i:i + 40]
        q = "HAS_PREPRINT:Y AND (" + " OR ".join(f"PMCID:{p}" for p in chunk) + ")"
        flagged += [r["pmcid"] for r in epmc(q) if r.get("pmcid")]
    out = {}
    for p in flagged:
        rec = epmc(f"PMCID:{p}", 1)[0]
        dates = []
        for c in (rec.get("commentCorrectionList") or {}).get("commentCorrection", []):
            if "preprint" in c.get("type", "").lower() and c.get("id"):
                src = c.get("source", "PPR")
                hit = epmc(f"EXT_ID:{c['id']} AND SRC:{src}", 1)
                if hit and hit[0].get("firstPublicationDate"):
                    dates.append(hit[0]["firstPublicationDate"])
        out[p] = min(dates) if dates else "linked, date not found"
    return out


def dates_and_sensitivity(from_csv: bool = False) -> None:
    s = analytic_sample()
    if not from_csv and not RAW.is_dir():
        print("corpus/raw/ not found: reading revision/data/publication_dates.csv")
        from_csv = True
    if from_csv:
        dates = pd.read_csv(DATES_CSV, keep_default_na=False)
        dates["preprint_first_date"] = dates.preprint_first_date.replace("", None)
        return analyse(s, dates)
    rows = []
    for p in s.pmcid:
        d = xml_dates(p)
        rows.append({"pmcid": p, "epub": d.get("epub"), "ppub": d.get("ppub"), "collection": d.get("collection"),
                     "received": d.get("history_received"), "accepted": d.get("history_accepted"),
                     "earliest_public": d.get("epub") or d.get("ppub"),
                     "meeting_statement_present": int(d["meeting_statement"] != "")})
    dates = s[["pmcid", "tier", "journal_name"]].merge(pd.DataFrame(rows), on="pmcid")
    pp = preprints(list(dates.pmcid))
    dates["preprint_first_date"] = dates.pmcid.map(pp)
    dates.to_csv(DATES_CSV, index=False)
    analyse(s, dates)


def analyse(s: pd.DataFrame, dates: pd.DataFrame) -> None:
    w = wide(s, run=1).merge(dates[["pmcid", "earliest_public", "preprint_first_date", "meeting_statement_present"]],
                             on="pmcid")
    ep = pd.to_datetime(w.earliest_public).dt.date
    pre = pd.to_datetime(w.preprint_first_date, errors="coerce").dt.date
    earlier_version = w.preprint_first_date.notna() | (w.meeting_statement_present == 1)
    out = []
    for m, cut in CUTOFF.items():
        sets = {
            "all papers (main analysis)": np.ones(len(w), bool),
            "earliest public date on or after 1 Feb 2026": (ep >= WINDOW_START).to_numpy(),
            "earliest public date after model cutoff": (ep > cut).to_numpy(),
            "after model cutoff and no earlier preprint or meeting presentation":
                ((ep > cut) & ~earlier_version).to_numpy(),
            "preprint online on or before model cutoff": (pre <= cut).fillna(False).to_numpy().astype(bool),
        }
        for name, mask in sets.items():
            d = w[mask].dropna(subset=[m]).copy()
            d[m] = d[m].astype(int)
            row = {"model": m, "cutoff_used": cut, "subset": name, "n": len(d),
                   "tiers": "/".join(str((d.tier == t).sum()) for t in (1, 2, 3, 4))}
            if len(d) >= 20 and d.tier.nunique() > 1:
                pt, lo, hi, _ = bootstrap(lambda x: kappa(x.tier.to_numpy(), x[m].to_numpy()), d)
                row.update(kappa_quadratic=pt, ci_low=lo, ci_high=hi)
            out.append(row)
    res = pd.DataFrame(out)
    save(res, "post_cutoff_sensitivity.csv")
    print(dates.assign(before_window=pd.to_datetime(dates.earliest_public).dt.date < WINDOW_START)
          .groupby("journal_name").before_window.agg(["sum", "count"]).to_string())
    print("papers with linked preprint:", dates.preprint_first_date.notna().sum(),
          "| meeting statement:", (dates.meeting_statement_present == 1).sum())
    with pd.option_context("display.width", 220, "display.max_rows", 60):
        print(res.round(3).to_string(index=False))


def within_tier(by: str = "journal_name") -> pd.DataFrame:
    """Exact agreement and mean assigned tier for papers online before vs after each model's cutoff, within
    journal or tier, with the stratified difference in exact agreement and its bootstrap 95% CI."""
    s = analytic_sample()
    w = wide(s, run=1).merge(pd.read_csv(DATES_CSV)[["pmcid", "earliest_public"]],
                             on="pmcid")
    ep = pd.to_datetime(w.earliest_public).dt.date
    rows = []
    rng = np.random.default_rng(42)
    for m, cut in CUTOFF.items():
        d = w.assign(before=(ep <= cut).to_numpy()).dropna(subset=[m])
        d["hit"] = d[m].astype(int) == d.tier
        mixed = [t for t, g in d.groupby(by) if g.before.sum() >= 3 and (~g.before).sum() >= 3]
        for t in mixed:
            g = d[d[by] == t]
            rows.append({"model": m, by: t, "n_before": int(g.before.sum()), "n_after": int((~g.before).sum()),
                         "exact_before": g[g.before].hit.mean(), "exact_after": g[~g.before].hit.mean(),
                         "mean_tier_before": g[g.before][m].mean(), "mean_tier_after": g[~g.before][m].mean()})
        if not mixed:
            continue
        sub = d[d[by].isin(mixed)]

        def strat(x):
            parts = [(len(g), g[g.before].hit.mean() - g[~g.before].hit.mean())
                     for _, g in x.groupby(by) if g.before.any() and (~g.before).any()]
            return sum(n * v for n, v in parts) / sum(n for n, _ in parts)
        draws = []
        groups = [(g[g.before].index.to_numpy(), g[~g.before].index.to_numpy()) for _, g in sub.groupby(by)]
        for _ in range(2000):
            ix = np.concatenate([np.concatenate([rng.choice(b, len(b)), rng.choice(a, len(a))]) for b, a in groups])
            draws.append(strat(sub.loc[ix]))
        lo, hi = np.percentile(draws, [2.5, 97.5])
        rows.append({"model": m, by: "all strata with both groups, stratified", "n_before": int(sub.before.sum()),
                     "n_after": int((~sub.before).sum()), "exact_before": np.nan, "exact_after": np.nan,
                     "difference_exact_before_minus_after": strat(sub), "ci_low": lo, "ci_high": hi})
    out = pd.DataFrame(rows)
    save(out, f"before_vs_after_cutoff_within_{'journal' if by == 'journal_name' else 'tier'}.csv")
    with pd.option_context("display.width", 220, "display.max_rows", 60):
        print(out.round(2).to_string(index=False))
    return out


def main(from_csv: bool = False) -> None:
    dates_and_sensitivity(from_csv)
    within_tier("tier")
    within_tier("journal_name")


if __name__ == "__main__":
    import sys
    main(from_csv="--from-csv" in sys.argv)
