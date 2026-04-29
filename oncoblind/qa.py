"""QA sweep — final regex check on normalized markdown for leaked identifiers."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from .strip import _JOURNAL_RE, _PUBLISHER_RE, DOI_RE, PMID_RE, PMCID_RE, ISSN_RE


@dataclass
class QAReport:
    pmcid: str = ""
    passed: bool = True
    journal_hits: list[str] = field(default_factory=list)
    publisher_hits: list[str] = field(default_factory=list)
    id_hits: list[str] = field(default_factory=list)
    url_hits: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def qa_sweep(text: str, pmcid: str = "") -> QAReport:
    rpt = QAReport(pmcid=pmcid)
    rpt.journal_hits = [m.group(0) for m in _JOURNAL_RE.finditer(text)]
    rpt.publisher_hits = [m.group(0) for m in _PUBLISHER_RE.finditer(text)]

    for pat in (DOI_RE, PMID_RE, PMCID_RE, ISSN_RE):
        rpt.id_hits += [m.group(0) for m in pat.finditer(text)]

    rpt.url_hits = re.findall(r"https?://\S+", text)

    rpt.passed = not (rpt.journal_hits or rpt.publisher_hits or rpt.id_hits or rpt.url_hits)
    return rpt
