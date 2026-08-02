from __future__ import annotations

import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import requests
from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "papers.json"
STATUS_PATH = ROOT / "docs" / "data" / "status.json"

NCBI_EMAIL = os.getenv("NCBI_EMAIL", "your-email@example.com")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
LOOKBACK_DAYS = 3
MAX_NEW = 20

QUERIES = [
    {
        "category": "尿道カテーテル閉塞",
        "query": '(("Urinary Catheters"[Mesh] OR urinary catheter*[Title/Abstract] OR urethral catheter*[Title/Abstract] OR indwelling catheter*[Title/Abstract] OR Foley catheter*[Title/Abstract]) AND (block*[Title/Abstract] OR obstruct*[Title/Abstract] OR encrust*[Title/Abstract] OR crystalline biofilm*[Title/Abstract] OR catheter patency[Title/Abstract]))',
    },
    {
        "category": "尿路結石・細菌叢",
        "query": '(("Urinary Calculi"[Mesh] OR urolithiasis[Title/Abstract] OR nephrolithiasis[Title/Abstract] OR kidney stone*[Title/Abstract] OR urinary stone*[Title/Abstract] OR struvite[Title/Abstract]) AND (microbiome[Title/Abstract] OR microbiota[Title/Abstract] OR biofilm[Title/Abstract] OR metagenom*[Title/Abstract] OR "16S rRNA"[Title/Abstract] OR urease[Title/Abstract]))',
    },
    {
        "category": "尿路結石・メタボローム",
        "query": '(("Urinary Calculi"[Mesh] OR urolithiasis[Title/Abstract] OR nephrolithiasis[Title/Abstract] OR kidney stone*[Title/Abstract] OR struvite[Title/Abstract]) AND (metabolom*[Title/Abstract] OR metabolite profiling[Title/Abstract] OR LC-MS[Title/Abstract] OR mass spectrometr*[Title/Abstract] OR NMR[Title/Abstract]))',
    },
    {
        "category": "PICRUSt2・機能予測",
        "query": '((urinary tract[Title/Abstract] OR urine[Title/Abstract] OR urobiome[Title/Abstract] OR urolithiasis[Title/Abstract]) AND (PICRUSt[Title/Abstract] OR PICRUSt2[Title/Abstract] OR predicted metagenom*[Title/Abstract] OR functional prediction[Title/Abstract] OR MetaCyc[Title/Abstract] OR KEGG[Title/Abstract]))',
    },
    {
        "category": "カテーテル新技術",
        "query": '(catheter*[Title/Abstract] AND (antibacter*[Title/Abstract] OR antimicrobial[Title/Abstract] OR antibiofilm[Title/Abstract] OR coating*[Title/Abstract] OR surface modification[Title/Abstract] OR nanostructur*[Title/Abstract] OR nanopattern*[Title/Abstract] OR hydrogel[Title/Abstract] OR zwitterionic[Title/Abstract] OR drug-eluting[Title/Abstract] OR smart catheter*[Title/Abstract] OR sensor*[Title/Abstract]) AND (prevent*[Title/Abstract] OR inhibit*[Title/Abstract] OR reduc*[Title/Abstract] OR resist*[Title/Abstract] OR detect*[Title/Abstract]))',
    },
]

def text(el: ET.Element | None) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""

def load_existing() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def esearch(query: str) -> list[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": "50",
        "sort": "pub date",
        "datetype": "edat",
        "reldate": str(LOOKBACK_DAYS),
        "tool": "ShinchakuRonbun",
        "email": NCBI_EMAIL,
    }
    r = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params=params, timeout=45,
    )
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])

def efetch(pmids: list[str]) -> ET.Element:
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "tool": "ShinchakuRonbun",
        "email": NCBI_EMAIL,
    }
    r = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        params=params, timeout=60,
    )
    r.raise_for_status()
    return ET.fromstring(r.text)

def parse_date(parent: ET.Element | None) -> str:
    if parent is None:
        return ""
    year = text(parent.find("Year"))
    month = text(parent.find("Month")) or "01"
    day = text(parent.find("Day")) or "01"
    months = {
        "Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
        "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12",
    }
    month = months.get(month, month)
    if not year:
        medline = text(parent.find("MedlineDate"))
        m = re.search(r"\b(19|20)\d{2}\b", medline)
        return f"{m.group(0)}-01-01" if m else ""
    return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"

def translate(text_value: str) -> str:
    value = text_value.strip()
    if not value:
        return ""
    try:
        chunks = [value[i:i+4000] for i in range(0, len(value), 4000)]
        return "\n".join(GoogleTranslator(source="en", target="ja").translate(c) for c in chunks)
    except Exception:
        return ""

def split_sentences(value: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", value.replace("\n", " ")) if x.strip()]

def structured_sections(abstract: str) -> dict[str, str]:
    out = {"purpose": "", "methods": "", "results": "", "conclusion": ""}
    pattern = re.compile(
        r"(?:^|\n)(BACKGROUND|OBJECTIVE|OBJECTIVES|PURPOSE|AIM|METHODS|MATERIALS AND METHODS|RESULTS|CONCLUSION|CONCLUSIONS)\s*:\s*",
        re.I,
    )
    matches = list(pattern.finditer(abstract))
    for i, m in enumerate(matches):
        body = abstract[m.end(): matches[i+1].start() if i+1 < len(matches) else len(abstract)].strip()
        label = m.group(1).upper()
        if label in {"BACKGROUND","OBJECTIVE","OBJECTIVES","PURPOSE","AIM"}:
            out["purpose"] += (" " if out["purpose"] else "") + body
        elif label in {"METHODS","MATERIALS AND METHODS"}:
            out["methods"] += (" " if out["methods"] else "") + body
        elif label == "RESULTS":
            out["results"] += (" " if out["results"] else "") + body
        else:
            out["conclusion"] += (" " if out["conclusion"] else "") + body
    return out

def find_sentences(abstract: str, pattern: str, limit: int) -> str:
    rx = re.compile(pattern, re.I)
    return " ".join([s for s in split_sentences(abstract) if rx.search(s)][:limit])

def detect_design(abstract: str) -> str:
    t = abstract.lower()
    tests = [
        (r"systematic review|meta-analysis", "系統的レビュー／メタ解析"),
        (r"randomized|randomised|clinical trial", "ランダム化比較試験／臨床試験"),
        (r"case-control", "症例対照研究"),
        (r"cross-sectional", "横断研究"),
        (r"prospective cohort|prospective study", "前向き研究"),
        (r"retrospective cohort|retrospective study", "後ろ向き研究"),
        (r"cohort", "コホート研究"),
        (r"in vitro|artificial urine|laboratory model", "in vitro研究"),
        (r"mouse|mice|rat|rats|animal model", "動物実験"),
    ]
    for pat, label in tests:
        if re.search(pat, t):
            return label
    return "Abstractから明確に判定できません"

def extract_numbers(abstract: str) -> list[dict[str, str]]:
    patterns = [
        ("対象数", r"\b(?:n\s*=\s*\d+|\d+\s+(?:patients|participants|subjects|samples|isolates|catheters))\b"),
        ("割合", r"\b\d+(?:\.\d+)?\s*%"),
        ("P値", r"\bp\s*(?:<|>|=|≤|≥)\s*0?\.\d+\b"),
        ("95%信頼区間", r"\b95%\s*CI[^.;\n]*"),
        ("オッズ比", r"\bOR\s*[=:]?\s*\d+(?:\.\d+)?"),
        ("ハザード比", r"\bHR\s*[=:]?\s*\d+(?:\.\d+)?"),
    ]
    sentences = split_sentences(abstract)
    rows = []
    for label, pat in patterns:
        for value in list(dict.fromkeys(re.findall(pat, abstract, flags=re.I)))[:8]:
            source = next((s for s in sentences if str(value) in s), "")
            rows.append({"item": label, "value": str(value), "source": source})
    return rows

def relevance(category: str, title: str, abstract: str) -> tuple[int, str, list[str]]:
    combined = f"{title} {abstract}".lower()
    terms = [
        "catheter blockage","encrustation","crystalline biofilm","struvite",
        "proteus mirabilis","urease","urolithiasis","microbiome","microbiota",
        "metabolomics","lc-ms","picrust2","kegg","metacyc","hydrogel","coating",
    ]
    found = [t for t in terms if t in combined]
    score = 2
    if any(t in combined for t in ["catheter blockage","encrustation","crystalline biofilm","struvite"]):
        score += 2
    if any(t in combined for t in ["proteus mirabilis","urease","microbiome","metabolomics","picrust2"]):
        score += 1
    return min(score, 5), f"{category}に関連し、特に「{'、'.join(found[:6]) or '関連テーマ'}」の観点から確認価値があります。", found[:8]

def parse_article(article: ET.Element, category: str) -> dict[str, Any]:
    medline = article.find("MedlineCitation")
    art = medline.find("Article") if medline is not None else None
    journal = art.find("Journal") if art is not None else None

    pmid = text(medline.find("PMID")) if medline is not None else ""
    title = text(art.find("ArticleTitle")) if art is not None else ""

    abstract_parts = []
    abstract_el = art.find("Abstract") if art is not None else None
    if abstract_el is not None:
        for el in abstract_el.findall("AbstractText"):
            label = el.attrib.get("Label") or el.attrib.get("NlmCategory") or ""
            body = text(el)
            abstract_parts.append(f"{label}: {body}" if label else body)
    abstract = "\n".join(abstract_parts)

    authors = []
    author_list = art.find("AuthorList") if art is not None else None
    if author_list is not None:
        for a in author_list.findall("Author"):
            collective = text(a.find("CollectiveName"))
            name = collective or " ".join(filter(None, [text(a.find("LastName")), text(a.find("ForeName"))]))
            if name:
                authors.append(name)

    doi = ""
    pubmed_data = article.find("PubmedData")
    if pubmed_data is not None:
        for ident in pubmed_data.findall("./ArticleIdList/ArticleId"):
            if ident.attrib.get("IdType") == "doi":
                doi = text(ident)

    entry_date = ""
    if pubmed_data is not None:
        for h in pubmed_data.findall("./History/PubMedPubDate"):
            if h.attrib.get("PubStatus") in {"entrez", "pubmed"}:
                entry_date = parse_date(h)

    pub_date = parse_date(journal.find("./JournalIssue/PubDate") if journal is not None else None)
    journal_title = text(journal.find("Title")) if journal is not None else ""

    sections = structured_sections(abstract)
    sentences = split_sentences(abstract)
    purpose_en = sections["purpose"] or " ".join(sentences[:2])
    methods_en = sections["methods"] or find_sentences(abstract, r"patient|participant|sample|study|trial|cohort|case-control|random|method|analy|assay|sequenc|LC-MS|NMR|PICRUSt", 3)
    results_en = sections["results"] or find_sentences(abstract, r"result|significant|increase|decrease|associated|difference|p\s*[<=>]|%|odds ratio|hazard ratio|confidence interval", 4)
    conclusion_en = sections["conclusion"] or " ".join(sentences[-2:])

    score, rel_text, keywords = relevance(category, title, abstract)

    return {
        "pmid": pmid,
        "doi": doi,
        "category": category,
        "title_en": title,
        "title_ja": translate(title),
        "authors": ", ".join(authors),
        "journal": journal_title,
        "publication_date": pub_date,
        "entry_date": entry_date,
        "study_design": detect_design(abstract),
        "purpose": translate(purpose_en),
        "methods": translate(methods_en),
        "results": translate(results_en),
        "conclusion": translate(conclusion_en),
        "limitations": "無料版ではAbstractに明記された内容のみ確認できます。本文にのみ記載された限界は反映されません。",
        "research_relevance": rel_text,
        "relevance_score": score,
        "keywords": keywords,
        "abstract_en": abstract,
        "abstract_ja": translate(abstract),
        "detail_methods": translate(methods_en),
        "detail_results": translate(results_en),
        "result_table": extract_numbers(abstract),
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "doi_url": f"https://doi.org/{doi}" if doi else "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

def slack_notify(new_papers: list[dict[str, Any]]) -> None:
    if not SLACK_WEBHOOK_URL or not new_papers:
        return
    lines = []
    for i, p in enumerate(new_papers[:10], 1):
        lines.append(
            f"{i}. *{p['title_ja'] or p['title_en']}*\n"
            f"{p['category']} {'★' * p['relevance_score']}\n"
            f"{p['results'][:240]}\n"
            f"<{p['pubmed_url']}|PubMed>"
            + (f" | <{p['doi_url']}|DOI>" if p["doi_url"] else "")
        )
    requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": f"🌸 *新着論文 {len(new_papers)}件*\n\n" + "\n\n".join(lines)},
        timeout=30,
    )

def main() -> None:
    existing = load_existing()
    existing_ids = {str(p.get("pmid")) for p in existing}
    hits = []
    seen = set()

    for q in QUERIES:
        for pmid in esearch(q["query"]):
            if pmid not in seen:
                seen.add(pmid)
                hits.append({"pmid": pmid, "category": q["category"]})
        time.sleep(0.4)

    targets = [h for h in hits if h["pmid"] not in existing_ids][:MAX_NEW]
    new_papers = []

    if targets:
        root = efetch([x["pmid"] for x in targets])
        categories = {x["pmid"]: x["category"] for x in targets}
        for article in root.findall("PubmedArticle"):
            pmid = text(article.find("./MedlineCitation/PMID"))
            new_papers.append(parse_article(article, categories.get(pmid, "その他")))
            time.sleep(0.2)

    combined = existing + new_papers
    combined.sort(key=lambda p: (p.get("entry_date") or p.get("created_at") or ""), reverse=True)

    DATA_PATH.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    STATUS_PATH.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "new_count": len(new_papers),
        "total_count": len(combined),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    slack_notify(new_papers)
    print(f"Added {len(new_papers)} papers. Total: {len(combined)}")

if __name__ == "__main__":
    main()
