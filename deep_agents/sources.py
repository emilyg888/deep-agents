from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

from .models import Paper

ARXIV_API_URL = "http://export.arxiv.org/api/query"
OPENALEX_API_URL = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
HACKER_NEWS_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HACKER_NEWS_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
YOUTUBE_SEARCH_API_URL = "https://www.googleapis.com/youtube/v3/search"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class PaperSource(Protocol):
    name: str
    tier: int

    def fetch(self) -> list[Paper]:
        ...


def _fetch_json(url: str, headers: dict[str, str] | None = None) -> dict | list:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_text(url: str, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _safe_date(value: str | None, *, fallback: date | None = None) -> date:
    if not value:
        return fallback or date.today()
    raw = value.strip()
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        return datetime.fromisoformat(raw).date()
    except ValueError:
        try:
            return parsedate_to_datetime(raw).date()
        except (TypeError, ValueError):
            return fallback or date.today()


@dataclass(frozen=True)
class StaticPaperSource:
    name: str
    tier: int
    papers: list[Paper]

    def fetch(self) -> list[Paper]:
        return [
            Paper(
                title=paper.title,
                authors=list(paper.authors),
                abstract=paper.abstract,
                source=self.name,
                url=paper.url,
                published_on=paper.published_on,
                tier=self.tier,
            )
            for paper in self.papers
        ]


@dataclass(frozen=True)
class ArxivPaperSource:
    name: str = "arXiv"
    tier: int = 1
    query: str = "all:agentic AI OR all:enterprise AI OR all:RAG"
    limit: int = 5

    def fetch(self) -> list[Paper]:
        query_string = urllib.parse.urlencode(
            {
                "search_query": self.query,
                "start": 0,
                "max_results": self.limit,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
        feed = _fetch_text(f"{ARXIV_API_URL}?{query_string}")
        root = ET.fromstring(feed)
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", ATOM_NS):
            title = _normalize_whitespace(
                entry.findtext("atom:title", default="", namespaces=ATOM_NS)
            )
            abstract = _normalize_whitespace(
                entry.findtext("atom:summary", default="", namespaces=ATOM_NS)
            )
            url = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
            published = _safe_date(
                entry.findtext("atom:published", default="", namespaces=ATOM_NS)
            )
            authors = [
                _normalize_whitespace(author.findtext("atom:name", default="", namespaces=ATOM_NS))
                for author in entry.findall("atom:author", ATOM_NS)
            ]
            if title and abstract and url:
                papers.append(
                    Paper(
                        title=title,
                        authors=authors or [self.name],
                        abstract=abstract,
                        source=self.name,
                        url=url,
                        published_on=published,
                        tier=self.tier,
                    )
                )
        return papers


@dataclass(frozen=True)
class SemanticScholarPaperSource:
    name: str = "Semantic Scholar"
    tier: int = 1
    query: str = "agentic ai enterprise ai rag workflow governance"
    limit: int = 5

    def fetch(self) -> list[Paper]:
        query_string = urllib.parse.urlencode(
            {
                "query": self.query,
                "limit": self.limit,
                "fields": "title,abstract,authors,url,year,publicationDate",
                "sort": "publicationDate:desc",
            }
        )
        headers = {}
        api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key
        payload = _fetch_json(f"{SEMANTIC_SCHOLAR_API_URL}?{query_string}", headers=headers)
        items = payload.get("data", []) if isinstance(payload, dict) else []
        papers: list[Paper] = []
        for item in items:
            title = _normalize_whitespace(str(item.get("title") or ""))
            abstract = _normalize_whitespace(str(item.get("abstract") or ""))
            url = str(item.get("url") or "")
            authors = [
                _normalize_whitespace(str(author.get("name") or ""))
                for author in item.get("authors", [])
                if author.get("name")
            ]
            published = _safe_date(
                str(item.get("publicationDate") or ""),
                fallback=date(int(item["year"]), 1, 1) if item.get("year") else None,
            )
            if title and abstract and url:
                papers.append(
                    Paper(
                        title=title,
                        authors=authors or [self.name],
                        abstract=abstract,
                        source=self.name,
                        url=url,
                        published_on=published,
                        tier=self.tier,
                    )
                )
        return papers


@dataclass(frozen=True)
class OpenAlexPaperSource:
    name: str = "OpenAlex"
    tier: int = 1
    query: str = "agentic ai enterprise ai rag workflow governance"
    limit: int = 5
    from_publication_date: str | None = None

    def fetch(self) -> list[Paper]:
        api_key = os.getenv("OPENALEX_API_KEY")
        if not api_key:
            return []
        query_params: dict[str, str | int] = {
            "search": self.query,
            "per-page": self.limit,
            "sort": "publication_date:desc,relevance_score:desc",
            "api_key": api_key,
        }
        if self.from_publication_date:
            query_params["filter"] = (
                f"from_publication_date:{self.from_publication_date}"
            )
        payload = _fetch_json(
            f"{OPENALEX_API_URL}?{urllib.parse.urlencode(query_params)}"
        )
        items = payload.get("results", []) if isinstance(payload, dict) else []
        papers: list[Paper] = []
        for item in items:
            title = _normalize_whitespace(str(item.get("display_name") or ""))
            abstract_index = item.get("abstract_inverted_index") or {}
            abstract = _normalize_whitespace(
                _openalex_abstract_from_inverted_index(abstract_index)
            )
            url = str(item.get("id") or item.get("doi") or "")
            authors = [
                _normalize_whitespace(str(author.get("author", {}).get("display_name") or ""))
                for author in item.get("authorships", [])
                if author.get("author", {}).get("display_name")
            ]
            published = _safe_date(str(item.get("publication_date") or ""))
            if title and abstract and url:
                papers.append(
                    Paper(
                        title=title,
                        authors=authors or [self.name],
                        abstract=abstract,
                        source=self.name,
                        url=url,
                        published_on=published,
                        tier=self.tier,
                    )
                )
        return papers


@dataclass(frozen=True)
class HackerNewsPaperSource:
    name: str = "Hacker News"
    tier: int = 3
    limit: int = 5

    def fetch(self) -> list[Paper]:
        story_ids = _fetch_json(HACKER_NEWS_TOP_STORIES_URL)
        if not isinstance(story_ids, list):
            return []
        papers: list[Paper] = []
        for item_id in story_ids[: self.limit]:
            item = _fetch_json(HACKER_NEWS_ITEM_URL.format(item_id=item_id))
            if not isinstance(item, dict):
                continue
            title = _normalize_whitespace(str(item.get("title") or ""))
            url = str(item.get("url") or f"https://news.ycombinator.com/item?id={item_id}")
            author = str(item.get("by") or "Hacker News")
            body = _normalize_whitespace(str(item.get("text") or ""))
            score = int(item.get("score") or 0)
            descendants = int(item.get("descendants") or 0)
            abstract = (
                body
                or f"Hacker News discussion with score {score} and {descendants} comments."
            )
            published = datetime.fromtimestamp(int(item.get("time") or 0), tz=UTC).date()
            if title and url:
                papers.append(
                    Paper(
                        title=title,
                        authors=[author],
                        abstract=abstract,
                        source=self.name,
                        url=url,
                        published_on=published,
                        tier=self.tier,
                    )
                )
        return papers


@dataclass(frozen=True)
class YouTubePaperSource:
    name: str = "YouTube"
    tier: int = 3
    query: str = "enterprise AI architecture agents RAG evaluation"
    limit: int = 5
    published_after: str | None = None

    def fetch(self) -> list[Paper]:
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return []
        query_params: dict[str, str | int] = {
            "part": "snippet",
            "q": self.query,
            "type": "video",
            "order": "date",
            "maxResults": min(self.limit, 50),
            "key": api_key,
        }
        if self.published_after:
            query_params["publishedAfter"] = self.published_after
        payload = _fetch_json(
            f"{YOUTUBE_SEARCH_API_URL}?{urllib.parse.urlencode(query_params)}"
        )
        items = payload.get("items", []) if isinstance(payload, dict) else []
        papers: list[Paper] = []
        for item in items:
            snippet = item.get("snippet", {})
            video_id = str(item.get("id", {}).get("videoId") or "")
            title = _normalize_whitespace(str(snippet.get("title") or ""))
            abstract = _normalize_whitespace(str(snippet.get("description") or ""))
            author = _normalize_whitespace(str(snippet.get("channelTitle") or self.name))
            published = _safe_date(str(snippet.get("publishedAt") or ""))
            url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
            if title and url:
                papers.append(
                    Paper(
                        title=title,
                        authors=[author or self.name],
                        abstract=abstract or f"Recent YouTube video from {author or self.name}.",
                        source=self.name,
                        url=url,
                        published_on=published,
                        tier=self.tier,
                    )
                )
        return papers


@dataclass(frozen=True)
class RSSPaperSource:
    name: str
    tier: int
    feed_url: str
    limit: int = 5

    def fetch(self) -> list[Paper]:
        if not self.feed_url:
            return []
        xml_text = _fetch_text(self.feed_url)
        root = ET.fromstring(xml_text)
        papers: list[Paper] = []
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for item in items[: self.limit]:
            title = _normalize_whitespace(
                item.findtext("title", default="")
                or item.findtext("{http://www.w3.org/2005/Atom}title", default="")
            )
            link = item.findtext("link", default="")
            if not link:
                atom_link = item.find("{http://www.w3.org/2005/Atom}link")
                if atom_link is not None:
                    link = atom_link.attrib.get("href", "")
            abstract = _normalize_whitespace(
                item.findtext("description", default="")
                or item.findtext("summary", default="")
                or item.findtext("{http://www.w3.org/2005/Atom}summary", default="")
            )
            author = _normalize_whitespace(
                item.findtext("author", default="")
                or item.findtext("{http://purl.org/dc/elements/1.1/}creator", default="")
                or item.findtext("{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name", default="")
            )
            published_value = (
                item.findtext("pubDate", default="")
                or item.findtext("published", default="")
                or item.findtext("{http://www.w3.org/2005/Atom}published", default="")
                or item.findtext("{http://www.w3.org/2005/Atom}updated", default="")
            )
            published = _safe_date(published_value)
            if title and link:
                papers.append(
                    Paper(
                        title=title,
                        authors=[author or self.name],
                        abstract=abstract or f"Latest item from {self.name}.",
                        source=self.name,
                        url=link,
                        published_on=published,
                        tier=self.tier,
                    )
                )
        return papers


@dataclass(frozen=True)
class FallbackPaperSource:
    name: str
    tier: int
    primary: PaperSource
    fallback: PaperSource

    def fetch(self) -> list[Paper]:
        try:
            papers = self.primary.fetch()
            if papers:
                return papers
        except (urllib.error.URLError, TimeoutError, ValueError, ET.ParseError, json.JSONDecodeError):
            pass
        return self.fallback.fetch()


class SourceCatalog:
    def __init__(self, sources: list[PaperSource]) -> None:
        self.sources = sources

    def fetch_all(self) -> list[Paper]:
        papers: list[Paper] = []
        for source in self.sources:
            try:
                papers.extend(source.fetch())
            except (urllib.error.URLError, TimeoutError, ValueError, ET.ParseError, json.JSONDecodeError):
                continue
        return papers


def _openalex_abstract_from_inverted_index(payload: dict) -> str:
    if not isinstance(payload, dict) or not payload:
        return ""
    pairs: list[tuple[int, str]] = []
    for token, positions in payload.items():
        if not isinstance(token, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                pairs.append((position, token))
    if not pairs:
        return ""
    pairs.sort(key=lambda item: item[0])
    return " ".join(token for _, token in pairs)
