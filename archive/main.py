from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from langchain_openai import ChatOpenAI
from openai import LengthFinishReasonError
from pydantic import BaseModel, Field

from env_utils import load_project_dotenv

load_project_dotenv(Path(__file__).with_name(".env"))

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
CURRENT_YEAR = date.today().year
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "current",
    "for",
    "how",
    "in",
    "is",
    "of",
    "on",
    "state",
    "the",
    "to",
    "what",
    "whats",
    "with",
}
SHORT_KEEPERS = {"ai", "ml"}


class Paper(BaseModel):
    title: str
    authors: list[str]
    abstract: str
    url: str
    year: int
    venue: str
    relevance: float = Field(
        description="Relevance to the user's query on a scale from 0 to 1."
    )


class Formula(BaseModel):
    name: str
    description: str
    latex: str = Field(
        description=(
            "LaTeX representation of the formula without surrounding dollar signs."
        )
    )
    references: list[str] = Field(
        default_factory=list,
        description="Titles or URLs to relevant papers or sources.",
    )


class Trend(BaseModel):
    title: str
    description: str
    references: list[str] = Field(
        default_factory=list,
        description="Titles or URLs to relevant papers or sources.",
    )


class Report(BaseModel):
    topics: list[str]
    research_questions: list[str]
    time_frame: str | None = None
    trends: list[Trend] = Field(default_factory=list)
    formulas: list[Formula] = Field(default_factory=list)
    papers: list[Paper] = Field(
        default_factory=list,
        description=(
            "Relevant papers sorted by relevance to the user's query. Include 5 to 10 "
            "papers when the source material supports that many."
        ),
    )


def _fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8")


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _normalize_query_text(value: str) -> str:
    return _normalize_whitespace(value.replace("-", " ").replace("_", " "))


def _truncate_text(value: str, max_chars: int) -> str:
    normalized = _normalize_whitespace(value)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _paper_reference_urls(papers: list[Paper], limit: int = 3) -> list[str]:
    return [paper.url for paper in papers[:limit] if paper.url]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _select_relevant_paper_urls(
    text: str,
    papers: list[Paper],
    *,
    limit: int = 1,
) -> list[str]:
    keywords = set(_extract_keywords(text, limit=12))
    scored: list[tuple[int, float, Paper]] = []

    for paper in papers:
        haystack = f"{paper.title} {paper.abstract}".lower()
        overlap = sum(1 for keyword in keywords if keyword in haystack)
        scored.append((overlap, int(paper.relevance * 100), paper))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [paper.url for overlap, _, paper in scored if overlap > 0 and paper.url]

    if len(selected) < limit:
        selected.extend(_paper_reference_urls(papers, limit=limit))

    return _dedupe_preserve_order(selected)[:limit]


def _extract_keywords(*parts: str, limit: int = 6) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    combined = " ".join(_normalize_query_text(part).lower() for part in parts if part)
    for token in re.findall(r"[a-z0-9]+", combined):
        if token in STOPWORDS:
            continue
        if len(token) <= 2 and token not in SHORT_KEEPERS:
            continue
        if token.isdigit():
            continue
        if token not in seen:
            seen.add(token)
            keywords.append(token)
        if len(keywords) >= limit:
            break
    return keywords


def _year_bounds_for_timeframe(time_frame: str) -> tuple[int | None, int | None]:
    normalized = _normalize_query_text(time_frame).lower()
    years = sorted(
        {
            int(match)
            for match in re.findall(r"\b(?:19|20)\d{2}\b", normalized)
            if 1900 <= int(match) <= CURRENT_YEAR + 1
        }
    )

    if len(years) >= 2:
        return years[0], years[-1]
    if len(years) == 1:
        target_year = years[0]
        return max(1900, target_year - 2), target_year
    if any(term in normalized for term in ("current", "recent", "latest", "today", "now")):
        return max(1900, CURRENT_YEAR - 2), CURRENT_YEAR
    return None, None


def _paper_matches_year_bounds(
    paper: Paper,
    min_year: int | None,
    max_year: int | None,
) -> bool:
    if paper.year <= 0:
        return False
    if min_year is not None and paper.year < min_year:
        return False
    if max_year is not None and paper.year > max_year:
        return False
    return True


def _sort_papers_by_relevance_and_recency(
    papers: list[Paper],
    max_year: int | None,
) -> list[Paper]:
    if max_year is None:
        return sorted(papers, key=lambda item: (item.relevance, item.year), reverse=True)

    return sorted(
        papers,
        key=lambda item: (
            item.relevance,
            -(abs(max_year - item.year)) if item.year > 0 else -9999,
            item.year,
        ),
        reverse=True,
    )


def _build_arxiv_search_queries(topic: str, question: str) -> list[str]:
    keywords = _extract_keywords(topic, question, limit=6)
    if not keywords:
        normalized_topic = _normalize_query_text(topic).strip()
        return [f'all:"{normalized_topic}"'] if normalized_topic else []

    queries: list[str] = []
    primary_terms = keywords[:4]
    queries.append(" AND ".join(f"all:{term}" for term in primary_terms))

    if len(keywords) >= 2:
        queries.append(" AND ".join(f"ti:{term}" for term in keywords[:2]))

    queries.append(" OR ".join(f"all:{term}" for term in keywords[:5]))

    normalized_topic = _normalize_query_text(topic).strip()
    if normalized_topic:
        queries.append(f'all:"{normalized_topic}"')

    return queries


def _relevance_score(query: str, title: str, abstract: str) -> float:
    terms = _extract_keywords(query, limit=12)
    if not terms:
        return 0.5

    haystack = f"{title} {abstract}".lower()
    matches = sum(1 for term in set(terms) if term in haystack)
    return round(min(1.0, matches / max(1, len(set(terms)))), 2)


def _parse_arxiv_entry(entry: ET.Element, query: str) -> Paper:
    title = _normalize_whitespace(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
    abstract = _normalize_whitespace(
        entry.findtext("atom:summary", default="", namespaces=ATOM_NS)
    )
    authors = [
        _normalize_whitespace(author.findtext("atom:name", default="", namespaces=ATOM_NS))
        for author in entry.findall("atom:author", ATOM_NS)
    ]
    published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
    paper_url = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
    year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else 0

    return Paper(
        title=title,
        authors=[author for author in authors if author],
        abstract=abstract,
        url=paper_url,
        year=year,
        venue="arXiv",
        relevance=_relevance_score(query, title, abstract),
    )


def _search_papers_with_query(search_query: str, relevance_query: str, limit: int) -> list[Paper]:
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max(1, min(limit, 10)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    xml_text = _fetch_text(f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}")
    root = ET.fromstring(xml_text)
    return [
        _parse_arxiv_entry(entry, relevance_query)
        for entry in root.findall("atom:entry", ATOM_NS)
    ]


def search_papers(
    topic: str,
    question: str = "",
    time_frame: str = "",
    limit: int = 10,
) -> list[Paper]:
    relevance_query = " ".join(part for part in [topic, question] if part).strip()
    min_year, max_year = _year_bounds_for_timeframe(time_frame)
    seen_urls: set[str] = set()
    papers: list[Paper] = []

    for search_query in _build_arxiv_search_queries(topic, question):
        try:
            matches = _search_papers_with_query(search_query, relevance_query, limit)
        except Exception:
            continue

        for paper in matches:
            if paper.url and paper.url not in seen_urls:
                seen_urls.add(paper.url)
                papers.append(paper)
                if len(papers) >= limit * 3:
                    break

    if min_year is not None or max_year is not None:
        papers = [
            paper
            for paper in papers
            if _paper_matches_year_bounds(paper, min_year, max_year)
        ]

    return _sort_papers_by_relevance_and_recency(papers, max_year)[:limit]


def get_paper_details(url: str) -> Paper:
    paper_id = url.rstrip("/").split("/")[-1]
    params = {"id_list": paper_id}
    xml_text = _fetch_text(f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}")
    root = ET.fromstring(xml_text)
    entry = root.find("atom:entry", ATOM_NS)
    if entry is None:
        raise ValueError(f"Could not find paper details for {url}")
    return _parse_arxiv_entry(entry, paper_id)


def search_formulas(query: str, limit: int = 10) -> list[Formula]:
    query_lower = _normalize_query_text(query).lower()
    formulas: list[Formula] = []

    if any(
        term in query_lower
        for term in ("transformer", "attention", "llm", "language model", "generative ai", "genai")
    ):
        formulas.append(
            Formula(
                name="Scaled Dot-Product Attention",
                description="Core attention computation used in transformer models.",
                latex=r"\mathrm{Attention}(Q, K, V) = \mathrm{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V",
                references=["https://arxiv.org/abs/1706.03762"],
            )
        )
        formulas.append(
            Formula(
                name="Autoregressive Next-Token Objective",
                description="Standard training objective used by many generative language models.",
                latex=r"\mathcal{L} = -\sum_{t=1}^{T} \log p(x_t \mid x_{<t})",
                references=["https://arxiv.org/abs/1706.03762"],
            )
        )
    if any(term in query_lower for term in ("bayes", "probability", "uncertainty", "inference")):
        formulas.append(
            Formula(
                name="Bayes' Rule",
                description="Relates posterior, likelihood, prior, and evidence.",
                latex=r"P(A \mid B) = \frac{P(B \mid A) P(A)}{P(B)}",
                references=["https://en.wikipedia.org/wiki/Bayes%27_theorem"],
            )
        )
    if any(term in query_lower for term in ("optimization", "gradient", "training", "loss")):
        formulas.append(
            Formula(
                name="Gradient Descent Update",
                description="Standard parameter update used in iterative optimization.",
                latex=r"\theta_{t+1} = \theta_t - \eta \nabla_\theta \mathcal{L}(\theta_t)",
                references=["https://en.wikipedia.org/wiki/Gradient_descent"],
            )
        )

    return formulas[:limit]


def search_trends(query: str, papers: list[Paper], limit: int = 10) -> list[Trend]:
    query_lower = _normalize_query_text(query).lower()
    trends: list[Trend] = []

    if any(
        term in query_lower
        for term in ("llm", "language model", "agent", "transformer", "generative ai", "genai")
    ):
        trends.append(
            Trend(
                title="Tool-Using and Agentic LLM Systems",
                description="Research is shifting from plain text generation toward systems that plan, call tools, and maintain state across tasks.",
                references=[],
            )
        )
        trends.append(
            Trend(
                title="Enterprise Shift from Pilots to Production",
                description="Organizations are moving beyond experimentation toward governed deployments tied to measurable workflow and cost outcomes.",
                references=[],
            )
        )
        trends.append(
            Trend(
                title="Governance, Security, and Evaluation Layers",
                description="Adoption increasingly depends on approval workflows, retrieval controls, observability, and domain-specific evaluation rather than model quality alone.",
                references=[],
            )
        )
        trends.append(
            Trend(
                title="Efficiency and Distillation",
                description="Recent work emphasizes smaller models, cheaper inference, and targeted distillation without losing core capabilities.",
                references=[],
            )
        )
    if any(term in query_lower for term in ("multimodal", "vision", "audio", "video")):
        trends.append(
            Trend(
                title="Unified Multimodal Modeling",
                description="Architectures increasingly combine text, image, audio, and video reasoning in a single training and inference stack.",
                references=[],
            )
        )
    if any(term in query_lower for term in ("safety", "alignment", "evaluation", "benchmark")):
        trends.append(
            Trend(
                title="Evaluation Beyond Static Benchmarks",
                description="Researchers are using scenario-based and interactive evaluations to measure robustness, safety, and real-world utility.",
                references=[],
            )
        )

    fallback_refs = _paper_reference_urls(papers, limit=1) or ["https://arxiv.org"]
    trends = [
        trend.model_copy(
            update={
                "references": _select_relevant_paper_urls(
                    f"{trend.title} {trend.description}",
                    papers,
                    limit=1,
                )
                or fallback_refs
            }
        )
        for trend in trends
    ]

    return trends[:limit]


def _build_messages(
    topic: str,
    question: str,
    time_frame: str,
    papers: list[Paper],
    formulas: list[Formula],
    trends: list[Trend],
    *,
    max_papers: int = 6,
    abstract_chars: int = 500,
) -> list[tuple[str, str]]:
    paper_context = [
        {
            "title": paper.title,
            "authors": paper.authors[:5],
            "abstract": _truncate_text(paper.abstract, abstract_chars),
            "url": paper.url,
            "year": paper.year,
            "venue": paper.venue,
            "relevance": paper.relevance,
        }
        for paper in papers[:max_papers]
    ]
    context = {
        "topic": topic,
        "research_question": question or None,
        "time_frame": time_frame or None,
        "papers": paper_context,
        "formulas": [formula.model_dump() for formula in formulas],
        "trends": [trend.model_dump() for trend in trends],
    }

    system_prompt = (
        "You are a research assistant. Return only data that fits the provided schema. "
        "Use concise field values, preserve citations as URLs, and do not invent "
        "papers that are not in the provided context."
    )
    user_prompt = (
        "Create a concise structured research report for the following request.\n\n"
        f"Topic: {topic}\n"
        f"Research Question: {question or 'None'}\n"
        f"Time Frame: {time_frame or 'None'}\n\n"
        "Use the source material below to populate every field in the schema. "
        "Use short descriptions. Keep paper abstracts brief in the output. "
        "Every paper must include its source URL. Every trend/formula reference must "
        "be a URL, not a paper title. "
        "If there is not enough evidence for a formula or trend, return an empty list "
        "instead of inventing one.\n\n"
        f"Source material:\n{json.dumps(context, indent=2)}"
    )
    return [("system", system_prompt), ("user", user_prompt)]


def _finalize_report(
    report: Report,
    source_papers: list[Paper],
    source_formulas: list[Formula],
    source_trends: list[Trend],
) -> Report:
    paper_by_title = {paper.title.casefold(): paper for paper in source_papers}
    source_papers_by_url = {paper.url: paper for paper in source_papers if paper.url}
    finalized_papers: list[Paper] = []
    used_paper_urls: set[str] = set()

    for paper in report.papers:
        source = paper_by_title.get(paper.title.casefold())
        if source is None:
            if paper.url and paper.url not in used_paper_urls:
                used_paper_urls.add(paper.url)
                finalized_papers.append(paper)
            continue

        if source.url in used_paper_urls:
            continue

        used_paper_urls.add(source.url)
        finalized_papers.append(
            source.model_copy(
                update={
                    "abstract": paper.abstract or _truncate_text(source.abstract, 600),
                }
            )
        )

    for source in source_papers:
        if len(finalized_papers) >= min(len(source_papers), 8):
            break
        if source.url and source.url not in used_paper_urls:
            used_paper_urls.add(source.url)
            finalized_papers.append(source)

    formula_ref_map = {formula.name.casefold(): formula.references for formula in source_formulas}
    trend_ref_map = {trend.title.casefold(): trend.references for trend in source_trends}

    finalized_formulas = [
        formula.model_copy(
            update={
                "references": _dedupe_preserve_order([
                    ref for ref in (formula.references or formula_ref_map.get(formula.name.casefold(), []))
                    if ref.startswith("http")
                ])
            }
        )
        for formula in report.formulas
    ]

    finalized_trends: list[Trend] = []
    for trend in report.trends:
        source_refs = trend_ref_map.get(trend.title.casefold(), [])
        current_refs = [ref for ref in trend.references if ref.startswith("http")]
        relevant_refs = _select_relevant_paper_urls(
            f"{trend.title} {trend.description}",
            finalized_papers or source_papers,
            limit=1,
        )
        finalized_trends.append(
            trend.model_copy(
                update={
                    "references": _dedupe_preserve_order(
                        (current_refs[:1]) or (source_refs[:1]) or relevant_refs or ["https://arxiv.org"]
                    )
                }
            )
        )

    if not finalized_formulas:
        finalized_formulas = source_formulas[:]
    if not finalized_trends:
        finalized_trends = source_trends[:]

    return report.model_copy(
        update={
            "papers": finalized_papers,
            "formulas": finalized_formulas,
            "trends": finalized_trends,
        }
    )


async def _generate_report(
    topic: str,
    question: str,
    time_frame: str,
    papers: list[Paper],
    formulas: list[Formula],
    trends: list[Trend],
) -> Report:
    model = ChatOpenAI(
        model="gpt-5",
        temperature=0.1,
        max_tokens=3000,
        timeout=60,
        reasoning_effort="low",
    ).with_structured_output(Report)

    try:
        report = await model.ainvoke(
            _build_messages(
                topic,
                question,
                time_frame,
                papers,
                formulas,
                trends,
                max_papers=6,
                abstract_chars=500,
            )
        )
        return _finalize_report(report, papers, formulas, trends)
    except LengthFinishReasonError:
        report = await model.ainvoke(
            _build_messages(
                topic,
                question,
                time_frame,
                papers,
                formulas,
                trends,
                max_papers=4,
                abstract_chars=220,
            )
        )
        return _finalize_report(report, papers, formulas, trends)


async def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env or export it in your shell."
        )

    topic = input("Enter a research topic: ").strip()
    question = input("Enter a specific research question (optional): ").strip()
    time_frame = input("Enter a time frame for the report (optional): ").strip()

    if not topic:
        raise ValueError("A research topic is required.")

    normalized_query = " ".join(part for part in [topic, question, time_frame] if part)
    papers = await asyncio.to_thread(search_papers, topic, question, time_frame, 8)
    formulas = search_formulas(normalized_query, 5)
    trends = search_trends(normalized_query, papers, 5)

    result = await _generate_report(
        topic, question, time_frame, papers, formulas, trends
    )
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
