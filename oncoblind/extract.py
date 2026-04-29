"""Extract structured content from PMC JATS XML."""

from __future__ import annotations

from dataclasses import dataclass, field
from lxml import etree


JATS_NS = {"xlink": "http://www.w3.org/1999/xlink",
           "mml": "http://www.w3.org/1998/Math/MathML"}


@dataclass
class ExtractedPaper:
    pmcid: str = ""
    title: str = ""
    abstract: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)
    figures: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


def _text(node) -> str:
    if node is None:
        return ""
    parts = [node.text or ""]
    for child in node:
        parts.append(_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _clean(s: str) -> str:
    return " ".join(s.split()).strip()


def _paragraph_text(p) -> str:
    return _clean(_text(p))


def _find_article(root) -> etree._Element | None:
    if root.tag.endswith("article"):
        return root
    found = root.find(".//article")
    return found


def _extract_sections(body) -> list[tuple[str, str]]:
    if body is None:
        return []
    out: list[tuple[str, str]] = []
    for sec in body.findall("./sec"):
        title_el = sec.find("./title")
        heading = _clean(_text(title_el)) if title_el is not None else ""
        paras = []
        for child in sec:
            tag = etree.QName(child).localname
            if tag in ("p",):
                paras.append(_paragraph_text(child))
            elif tag == "sec":
                sub_heading = _clean(_text(child.find("./title"))) if child.find("./title") is not None else ""
                sub_paras = [_paragraph_text(p) for p in child.findall("./p")]
                if sub_heading:
                    paras.append(f"### {sub_heading}")
                paras.extend(sub_paras)
                for subsub in child.findall("./sec"):
                    ss_heading = _clean(_text(subsub.find("./title"))) if subsub.find("./title") is not None else ""
                    ss_paras = [_paragraph_text(p) for p in subsub.findall(".//p")]
                    if ss_heading:
                        paras.append(f"#### {ss_heading}")
                    paras.extend(ss_paras)
        text = "\n\n".join(p for p in paras if p)
        out.append((heading, text))
    return out


def _extract_figures(body) -> list[dict]:
    figs = []
    if body is None:
        return figs
    for f in body.findall(".//fig"):
        label = _clean(_text(f.find("./label")))
        caption_el = f.find("./caption")
        caption = _clean(_text(caption_el)) if caption_el is not None else ""
        figs.append({"label": label, "caption": caption})
    return figs


def _extract_tables(body) -> list[dict]:
    tables = []
    if body is None:
        return tables
    for tw in body.findall(".//table-wrap"):
        label = _clean(_text(tw.find("./label")))
        caption_el = tw.find("./caption")
        caption = _clean(_text(caption_el)) if caption_el is not None else ""
        tables.append({"label": label, "caption": caption})
    return tables


def _extract_references(back) -> list[str]:
    refs: list[str] = []
    if back is None:
        return refs
    for ref in back.findall(".//ref"):
        citation = ref.find(".//mixed-citation")
        if citation is None:
            citation = ref.find(".//element-citation")
        if citation is None:
            citation = ref.find(".//citation")
        text = _clean(_text(citation)) if citation is not None else ""
        if text:
            refs.append(text)
    return refs


def _extract_abstract(front) -> str:
    if front is None:
        return ""
    abstracts = front.findall(".//abstract")
    parts = []
    for a in abstracts:
        if a.get("abstract-type") in ("graphical", "web-summary", "toc"):
            continue
        for p in a.findall(".//p"):
            parts.append(_paragraph_text(p))
    return "\n\n".join(parts).strip()


def _extract_title(front) -> str:
    if front is None:
        return ""
    title_el = front.find(".//article-title")
    return _clean(_text(title_el)) if title_el is not None else ""


def _extract_pmcid(front) -> str:
    if front is None:
        return ""
    for aid in front.findall(".//article-id"):
        if aid.get("pub-id-type") == "pmc":
            return "PMC" + aid.text.strip()
        if aid.get("pub-id-type") == "pmcid":
            return aid.text.strip()
    return ""


def extract_paper(xml_bytes: bytes) -> ExtractedPaper:
    parser = etree.XMLParser(recover=True, remove_blank_text=False)
    root = etree.fromstring(xml_bytes, parser=parser)
    article = _find_article(root)
    if article is None:
        raise ValueError("no <article> element found")

    front = article.find("./front")
    body = article.find("./body")
    back = article.find("./back")

    paper = ExtractedPaper(
        pmcid=_extract_pmcid(front),
        title=_extract_title(front),
        abstract=_extract_abstract(front),
        sections=_extract_sections(body),
        figures=_extract_figures(body),
        tables=_extract_tables(body),
        references=_extract_references(back),
    )
    return paper
