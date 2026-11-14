"""Writes the "cleaned" text of the venue probe, cleaned/<pmcid>.md, from corpus/normalized/<pmcid>.md for every
PMCID in sample_probe.csv: removes reference lists and back-matter sections, section numbering, abstract labels,
citation markers, trial numbers and vendor locations, and puts the main sections in a fixed order.
The article texts are not distributed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
DST = OUT / "cleaned"

DROP = re.compile(
    r"^(references?|bibliography|reporting summary|online content|source data|"
    r"(data|code|materials?)( and (code|materials?|data))? (availability|sharing)|data sharing|"
    r"acknowledg|funding|financial support|support|author('?s'?)? contributions?|contributions|"
    r"competing interests?|conflicts? of interest|disclosures?|declarations?|"
    r"ethic|institutional review board|informed consent|consent for publication|patient consent|"
    r"supplementary|peer review|additional information|abbreviations|disclaimer|publisher|"
    r"extended data|key points|simple summary|highlights|graphical abstract|inclusion and ethics|"
    r"footnotes?|notes|prior presentation|trial registration|author information|correspondence|"
    r"rights|context summary|implications for practice|translational relevance|significance|"
    r"statement of significance|what is (already )?known|what this study adds)",
    re.I,
)
CANON = [
    (re.compile(r"^(main|background|introduction)$", re.I), "Introduction"),
    (re.compile(r"^((materials?|patients?|subjects?) and )?(methods?|methodology)$|^online methods$", re.I), "Methods"),
    (re.compile(r"^results$", re.I), "Results"),
    (re.compile(r"^discussion$", re.I), "Discussion"),
    (re.compile(r"^conclusions?$", re.I), "Conclusions"),
]
ORDER = ["Title", "Abstract", "Introduction", "Methods", "Results", "Discussion", "Conclusions"]
TAIL = ["Figures", "Tables"]

HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
NUM = re.compile(r"^\d+(\.\d+)*\.?\s+")
LABEL = re.compile(r"^\**\s*(background|objectives?|aims?|purpose|importance|design[^:]{0,60}|setting[^:]{0,40}|"
                   r"participants|patients|exposures?|interventions?|main outcomes?[^:]{0,40}|methods?|"
                   r"materials and methods|results|findings|conclusions?( and relevance)?|meaning|question|"
                   r"trial registration|significance|introduction|case presentation)\s*\**\s*[:.]\s*\**\s*", re.I)
COUNTRY = (r"USA|UK|United States|United Kingdom|Germany|Japan|China|France|Switzerland|Italy|Spain|Canada|"
           r"Netherlands|The Netherlands|Sweden|Denmark|Belgium|Austria|Australia|Korea|Israel|Ireland|Norway|"
           r"Finland|Poland|India|Singapore|Taiwan|Brazil|Czech Republic|Hungary|Portugal")
VENDOR_LOC = re.compile(r"(\([^()]{1,80}?)(,\s*[A-Z][A-Za-z .'-]+){1,3},\s*(" + COUNTRY + r")\)")
SENTENCE_DROP = re.compile(r"[^.]*\b(Reporting Summary|Nature Portfolio|Springer Nature|linked to this article|"
                           r"BioRender|Research Square|in the Supplementary Information)\b[^.]*\.\s*", re.I)


def split_sections(md: str) -> list[dict]:
    """Return a flat list of {level, title, body} for every heading."""
    secs, cur = [], {"level": 0, "title": "", "body": []}
    for line in md.splitlines():
        m = HEAD.match(line)
        if m:
            secs.append(cur)
            cur = {"level": len(m.group(1)), "title": m.group(2).strip(), "body": []}
        else:
            cur["body"].append(line)
    secs.append(cur)
    return [s for s in secs if s["level"] or "".join(s["body"]).strip()]


def tree(secs: list[dict]) -> list[dict]:
    """Group flat sections into level-2 blocks; flatten 'Additional Sections'.

    Inside 'Additional Sections' all headings are level 3, so hierarchy comes
    from the numbering: "2." starts a block, "2.1." is a subsection of it.
    """
    out, block, promote = [], None, False
    for s in secs:
        if s["level"] <= 1:
            continue
        if s["level"] == 2:
            promote = s["title"].lower() == "additional sections"
            if promote:
                continue
            block = {"title": s["title"], "body": s["body"], "subs": []}
            out.append(block)
            continue
        if promote:
            m = re.match(r"^(\d+(?:\.\d+)*)\.?\s", s["title"])
            depth = m.group(1).count(".") if m else 0
            lvl = s["level"] - 1 + depth
            if lvl == 2 or block is None:
                block = {"title": s["title"], "body": s["body"], "subs": []}
                out.append(block)
            else:
                block["subs"].append({"level": lvl, "title": s["title"], "body": s["body"]})
        elif block is not None:
            block["subs"].append({"level": s["level"], "title": s["title"], "body": s["body"]})
    return out


def drop_subs(subs: list[dict]) -> list[dict]:
    keep, skip_below = [], None
    for s in subs:
        if skip_below is not None and s["level"] > skip_below:
            continue
        skip_below = None
        t = NUM.sub("", s["title"])
        if DROP.match(t):
            skip_below = s["level"]
            continue
        keep.append({**s, "title": t})
    return keep


def clean_abstract(lines: list[str]) -> str:
    paras = [p.strip() for p in "\n".join(lines).split("\n\n") if p.strip()]
    paras = [p for p in paras if "•" not in p and not p.lstrip().startswith(("- ", "* "))]
    if any(LABEL.match(p) for p in paras):  # drop lay summary paragraphs before a labelled abstract
        first = next(i for i, p in enumerate(paras) if LABEL.match(p))
        paras = paras[first:]
    paras = [LABEL.sub("", p) for p in paras]
    # drop a paragraph that only repeats an earlier one (highlights echoed as text)
    out = []
    for p in paras:
        if not any(p in q or q in p for q in out):
            out.append(p)
    return " ".join(out)


def clean_text(t: str) -> str:
    t = SENTENCE_DROP.sub("", t)
    t = t.replace("•", " ")
    t = re.sub(r"\bNCT\s?\d{8}\b", "[trial ID]", t)
    t = re.sub(r"Extended Data (Fig(?:ure)?s?\.?|Tables?)", r"Supplementary \1", t)
    t = re.sub(r"\bAppendix (Tables?|Fig(?:ure)?s?)\.?\s*A?(\d+)", r"Supplementary \1 \2", t)
    t = re.sub(r"\b(and|or|,)\s*A(\d+)\b", r"\1 \2", t)  # "... A1 and A2"
    t = re.sub(r"\bData Supplement\b", "Supplementary material", t)
    t = re.sub(r"\b(?:FIG|Fig)\.?\s+(\d)", r"Figure \1", t)
    t = re.sub(r"\b(?:FIGS|Figs)\.?\s+(\d)", r"Figures \1", t)
    t = re.sub(r"\s?\[\d{1,3}(?:\s*[,–-]\s*\d{1,3})*\]", "", t)          # [12], [3,4], [5–9]
    t = re.sub(r"\s?\((?:refs?\.)\s*\d{1,3}(?:\s*[,–-]\s*\d{1,3})*\)", "", t)  # (ref. 25)
    t = re.sub(r"(?<=[a-z]{3})\d{1,3}(?:[,–-]\d{1,3})*(?=[\s.,;:)])", "", t)  # superscripts glued to words
    t = re.sub(r"(?<=[a-z]{3}[.,])\d{1,3}(?:[,–-]\d{1,3})*(?=\s|$)", "", t)  # after punctuation
    t = VENDOR_LOC.sub(r"\1)", t)
    return t


def clean(md: str) -> str:
    blocks = tree(split_sections(md))
    kept = []
    for b in blocks:
        title = NUM.sub("", b["title"])
        if DROP.match(title):
            continue
        for rx, name in CANON:
            if rx.match(title):
                title = name
        kept.append({**b, "title": title, "subs": drop_subs(b["subs"])})
    # Canonical blocks go in a fixed order; any other block travels with the
    # canonical block it followed, so section content is never reshuffled.
    groups, cur = [], None
    for b in kept:
        if b["title"] in ORDER or b["title"] in TAIL or cur is None:
            cur = [b]
            groups.append(cur)
        else:
            cur.append(b)
    # Nature-family layout: results subsections follow "Main" with no Results
    # heading. Wrap them in one, as the other journals have.
    if not any(b["title"] == "Results" for b in kept):
        for g in groups:
            if g[0]["title"] == "Introduction" and len(g) > 1:
                subs = []
                for b in g[1:]:
                    subs.append({"level": 3, "title": b["title"], "body": b["body"]})
                    subs += [{**s, "level": s["level"] + 1} for s in b["subs"]]
                groups.append([{"title": "Results", "body": [], "subs": subs}])
                del g[1:]
                break
    rank = lambda g: (ORDER.index(g[0]["title"]) if g[0]["title"] in ORDER  # noqa: E731
                      else 100 + TAIL.index(g[0]["title"]) if g[0]["title"] in TAIL else 50)
    kept = [b for g in sorted(groups, key=rank) for b in g]

    out = ["# Manuscript", ""]
    for b in kept:
        out += [f"## {b['title']}", ""]
        if b["title"] == "Abstract":
            out += [clean_text(clean_abstract(b["body"])), ""]
            continue
        body = "\n".join(b["body"]).strip()
        if body:
            out += [clean_text(body) if b["title"] not in ("Title",) else body, ""]
        for s in b["subs"]:
            out += [f"{'#' * s['level']} {s['title']}", ""]
            body = "\n".join(s["body"]).strip()
            if body:
                out += [clean_text(body), ""]
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def main() -> None:
    DST.mkdir(exist_ok=True)
    s = pd.read_csv(OUT / "sample_probe.csv")
    for p in s.pmcid:
        src = (ROOT / f"corpus/normalized/{p}.md").read_text()
        (DST / f"{p}.md").write_text(clean(src))
    print(f"cleaned {len(s)} files -> {DST}")


if __name__ == "__main__":
    main()
