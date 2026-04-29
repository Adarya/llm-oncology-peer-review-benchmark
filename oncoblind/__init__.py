"""oncoblind — JATS XML → blinded pre-submission markdown.

Implements §8 of the main protocol: extract structured content, strip all
journal/author/affiliation/funding identifiers, emit a uniform markdown
manuscript + a QA report.

Public API:
    normalize(xml_bytes: bytes) -> NormalizedPaper
    strip_journal_identifiers(markdown: str) -> tuple[str, list[str]]
    qa_sweep(markdown: str) -> QAReport
"""

from .extract import extract_paper, ExtractedPaper  # noqa: F401
from .strip import strip_identifiers  # noqa: F401
from .qa import qa_sweep, QAReport  # noqa: F401
from .pipeline import normalize, NormalizedPaper  # noqa: F401
