from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from hashlib import md5
from typing import Any


@dataclass(frozen=True)
class Paper:
    title: str
    authors: list[str]
    abstract: str
    source: str
    url: str
    published_on: date
    tier: int = 1

    @property
    def fingerprint(self) -> str:
        author_string = "|".join(author.strip().lower() for author in self.authors)
        raw = f"{self.title.strip().lower()}::{author_string}"
        return md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()


@dataclass(frozen=True)
class PaperPool:
    fetched: list[Paper]
    deduped: list[Paper]
    exact_dropped: list[Paper]
    similarity_deprioritized: list[Paper]


@dataclass(frozen=True)
class ThemeCandidate:
    theme: str
    why_selected: str
    why_debatable: str
    supporting_papers: list[Paper]
    common_belief: str
    contrarian_view: str
    why_wrong: str
    recommendation: str
    enterprise_implication: str
    novelty_score: int
    relevance_score: int
    debate_score: int
    contrarian_score: int
    tension_score: int
    specificity_score: int
    typical_architect_agrees: bool
    strong_architect_debates: bool
    rejection_reason: str | None = None


@dataclass(frozen=True)
class Position:
    common_belief: str
    contrarian_view: str
    why_wrong: str
    recommendation: str
    enterprise_implication: str


@dataclass(frozen=True)
class PositionStrengthResult:
    contrarian: int
    tension: int
    specificity: int
    passed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PostDraft:
    hook: str
    body: str
    word_count: int


@dataclass(frozen=True)
class PaperSummary:
    title: str
    source: str
    authors: list[str]
    url: str
    summary: str


@dataclass(frozen=True)
class EvaluationResult:
    novelty: int
    relevance: int
    insight: int
    position_strength: int
    clarity: int
    passed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeliveryArtifact:
    channel: str
    path: str
    preview: str
    target: str
    sent: bool
    status: str


@dataclass(frozen=True)
class PipelineResult:
    paper_pool: PaperPool
    lead_paper_summary: PaperSummary
    selected_theme: ThemeCandidate
    rejected_themes: list[ThemeCandidate]
    position: Position
    position_strength: PositionStrengthResult
    post: PostDraft
    evaluation: EvaluationResult
    storage_path: str
    deliveries: list[DeliveryArtifact]

    def as_dict(self) -> dict[str, Any]:
        return {
            "paper_pool": {
                "fetched_count": len(self.paper_pool.fetched),
                "deduped_count": len(self.paper_pool.deduped),
                "exact_dropped_count": len(self.paper_pool.exact_dropped),
                "similarity_deprioritized_count": len(
                    self.paper_pool.similarity_deprioritized
                ),
                "sources": [paper.source for paper in self.paper_pool.deduped],
            },
            "selected_theme": self.selected_theme.theme,
            "lead_paper_summary": asdict(self.lead_paper_summary),
            "why_selected": self.selected_theme.why_selected,
            "why_debatable": self.selected_theme.why_debatable,
            "rejected_themes": [
                {
                    "theme": candidate.theme,
                    "rejection_reason": candidate.rejection_reason,
                }
                for candidate in self.rejected_themes
            ],
            "position": asdict(self.position),
            "position_strength": asdict(self.position_strength),
            "post": asdict(self.post),
            "evaluation": asdict(self.evaluation),
            "storage_path": self.storage_path,
            "deliveries": [asdict(delivery) for delivery in self.deliveries],
        }
