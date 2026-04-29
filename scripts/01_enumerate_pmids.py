"""Step 1 — Enumerate eligible PMIDs per journal (PMC-OA only, primary research).

Writes corpus/index/enumeration.csv with PMID, PMCID, journal metadata, MeSH, abstract, article types.

Usage:
    .venv/bin/python scripts/01_enumerate_pmids.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
from Bio import Entrez
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

Entrez.email = config.NCBI_EMAIL
Entrez.tool = config.NCBI_TOOL
if config.NCBI_API_KEY:
    Entrez.api_key = config.NCBI_API_KEY

SLEEP = 0.34 if not config.NCBI_API_KEY else 0.11


def esearch_all(query: str, date_from: str, date_to: str) -> list[str]:
    """Return all PMIDs matching the query within the date window."""
    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        datetype="pdat",
        mindate=date_from,
        maxdate=date_to,
        retmax=10000,
        usehistory="y",
    )
    result = Entrez.read(handle)
    handle.close()
    return list(result["IdList"])


def efetch_metadata(pmids: list[str], batch_size: int = 100) -> list[dict]:
    """Fetch structured metadata for a list of PMIDs."""
    records = []
    for i in tqdm(range(0, len(pmids), batch_size), desc="  efetch", leave=False):
        batch = pmids[i : i + batch_size]
        handle = Entrez.efetch(db="pubmed", id=",".join(batch), rettype="medline", retmode="xml")
        parsed = Entrez.read(handle)
        handle.close()
        for article in parsed.get("PubmedArticle", []):
            records.append(_parse_article(article))
        time.sleep(SLEEP)
    return records


def _parse_article(article) -> dict:
    medline = article["MedlineCitation"]
    pmid = str(medline["PMID"])
    art = medline["Article"]
    title = str(art.get("ArticleTitle", "")).strip()
    abstract_parts = art.get("Abstract", {}).get("AbstractText", []) if "Abstract" in art else []
    abstract = " ".join(str(p) for p in abstract_parts).strip()
    pub_types = [str(pt) for pt in art.get("PublicationTypeList", [])]
    journal = str(art.get("Journal", {}).get("Title", "")).strip()
    journal_iso = str(art.get("Journal", {}).get("ISOAbbreviation", "")).strip()

    pub_date = ""
    art_date_list = art.get("ArticleDate", [])
    if art_date_list:
        d = art_date_list[0]
        pub_date = f"{d.get('Year','')}-{d.get('Month','')}-{d.get('Day','')}"
    else:
        jd = art.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
        pub_date = f"{jd.get('Year','')}-{jd.get('Month','')}-{jd.get('Day','')}"

    mesh_terms = []
    for m in medline.get("MeshHeadingList", []):
        mesh_terms.append(str(m["DescriptorName"]))
    mesh = "; ".join(mesh_terms)

    pmcid = ""
    doi = ""
    for aid in article.get("PubmedData", {}).get("ArticleIdList", []):
        if aid.attributes.get("IdType") == "pmc":
            pmcid = str(aid)
        elif aid.attributes.get("IdType") == "doi":
            doi = str(aid)

    return {
        "pmid": pmid,
        "pmcid": pmcid,
        "doi": doi,
        "journal": journal,
        "journal_iso": journal_iso,
        "pub_date": pub_date,
        "title": title,
        "abstract": abstract,
        "pub_types": "; ".join(pub_types),
        "mesh": mesh,
    }


def main() -> None:
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []

    for j in config.JOURNALS:
        print(f"\n[{j['tier']}] {j['name']} ({j['nlm']})")
        query = config.pubmed_query(j["nlm"], j["restrict_cancer"])
        print(f"  query: {query[:120]}...")
        pmids = esearch_all(query, config.DATE_FROM, config.DATE_TO)
        print(f"  PMIDs found: {len(pmids)}")
        if not pmids:
            continue
        records = efetch_metadata(pmids)
        for r in records:
            r["tier"] = j["tier"]
            r["journal_name"] = j["name"]
            r["nlm_abbr"] = j["nlm"]
            r["quota"] = j["quota"]
        all_rows.extend(records)

    df = pd.DataFrame(all_rows)
    df = df[df["pmcid"] != ""].copy()
    out = config.INDEX_DIR / "enumeration.csv"
    cols = ["tier", "journal_name", "nlm_abbr", "quota", "pmid", "pmcid", "doi",
            "journal", "journal_iso", "pub_date", "title", "abstract", "pub_types", "mesh"]
    df[cols].to_csv(out, index=False)
    print(f"\nWrote {len(df)} rows to {out}")
    print(df.groupby(["tier", "journal_name"]).size().to_string())


if __name__ == "__main__":
    main()
