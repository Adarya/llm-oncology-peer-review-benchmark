"""Pipeline: JATS XML bytes -> normalized blinded markdown + QA report."""

from __future__ import annotations

from dataclasses import dataclass, field

from .extract import extract_paper
from .strip import strip_identifiers
from .qa import qa_sweep, QAReport


SECTION_ORDER = [
    ("introduction", ["introduction", "background"]),
    ("methods",      ["methods", "materials and methods", "methodology", "patients and methods",
                      "experimental procedures", "study design"]),
    ("results",      ["results", "findings"]),
    ("discussion",   ["discussion"]),
    ("conclusions",  ["conclusion", "conclusions", "concluding remarks"]),
]

SECTION_DROP_PREFIXES = (
    "funding", "acknowledg", "conflict", "disclosure", "competing interest",
    "declaration", "author contribution", "author information", "ethic",
    "consent", "data availability", "code availability", "supplementary",
    "supporting information", "financial support",
)


@dataclass
class NormalizedPaper:
    pmcid: str = ""
    markdown: str = ""
    qa: QAReport | None = None
    redactions: list[str] = field(default_factory=list)


def _route_sections(sections: list[tuple[str, str]]) -> tuple[dict[str, str], list[tuple[str, str]]]:
    routed = {k: [] for k, _ in SECTION_ORDER}
    other: list[tuple[str, str]] = []
    for heading, body in sections:
        h = heading.lower().strip()
        if any(h.startswith(p) for p in SECTION_DROP_PREFIXES):
            continue
        placed = False
        for key, aliases in SECTION_ORDER:
            if any(a == h or h.startswith(a) for a in aliases):
                routed[key].append(body)
                placed = True
                break
        if not placed:
            other.append((heading, body))
    return {k: "\n\n".join(v) for k, v in routed.items()}, other


def _build_markdown(paper, routed: dict[str, str], other_sections: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    parts.append("# Manuscript\n")
    if paper.title:
        parts.append(f"## Title\n\n{paper.title}\n")
    if paper.abstract:
        parts.append(f"## Abstract\n\n{paper.abstract}\n")

    for key, heading in [("introduction", "Introduction"),
                          ("methods", "Methods"),
                          ("results", "Results"),
                          ("discussion", "Discussion"),
                          ("conclusions", "Conclusions")]:
        body = routed.get(key, "").strip()
        if body:
            parts.append(f"## {heading}\n\n{body}\n")

    if other_sections:
        parts.append("## Additional Sections\n")
        for h, b in other_sections:
            if b.strip():
                parts.append(f"### {h or 'Section'}\n\n{b}\n")

    if paper.figures:
        parts.append("## Figures\n")
        for i, f in enumerate(paper.figures, 1):
            label = f["label"] or f"Figure {i}"
            cap = f["caption"] or ""
            parts.append(f"**{label}.** {cap}\n")

    if paper.tables:
        parts.append("## Tables\n")
        for i, t in enumerate(paper.tables, 1):
            label = t["label"] or f"Table {i}"
            cap = t["caption"] or ""
            parts.append(f"**{label}.** {cap}\n")

    if paper.references:
        parts.append("## References\n")
        for i, r in enumerate(paper.references, 1):
            parts.append(f"{i}. {r}")

    return "\n".join(parts)


def normalize(xml_bytes: bytes) -> NormalizedPaper:
    paper = extract_paper(xml_bytes)
    routed, other = _route_sections(paper.sections)
    raw_md = _build_markdown(paper, routed, other)

    stripped, redactions = strip_identifiers(raw_md)
    report = qa_sweep(stripped, pmcid=paper.pmcid)

    return NormalizedPaper(pmcid=paper.pmcid, markdown=stripped, qa=report, redactions=redactions)
