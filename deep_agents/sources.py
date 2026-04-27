from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import Paper


class PaperSource(Protocol):
    name: str
    tier: int

    def fetch(self) -> list[Paper]:
        ...


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


class SourceCatalog:
    def __init__(self, sources: list[PaperSource]) -> None:
        self.sources = sources

    def fetch_all(self) -> list[Paper]:
        papers: list[Paper] = []
        for source in self.sources:
            papers.extend(source.fetch())
        return papers
