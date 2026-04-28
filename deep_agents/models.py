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

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": list(self.authors),
            "abstract": self.abstract,
            "source": self.source,
            "url": self.url,
            "published_on": self.published_on.isoformat(),
            "tier": self.tier,
            "fingerprint": self.fingerprint,
        }


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
    decisiveness_score: int
    tension_score: int
    specificity_score: int
    typical_architect_agrees: bool
    strong_architect_debates: bool
    rejection_reason: str | None = None

    def scorecard(self) -> dict[str, int | bool]:
        return {
            "novelty": self.novelty_score,
            "relevance": self.relevance_score,
            "debate": self.debate_score,
            "contrarian": self.contrarian_score,
            "decisiveness": self.decisiveness_score,
            "tension": self.tension_score,
            "specificity": self.specificity_score,
            "typical_architect_agrees": self.typical_architect_agrees,
            "strong_architect_debates": self.strong_architect_debates,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "why_selected": self.why_selected,
            "why_debatable": self.why_debatable,
            "supporting_papers": [paper.as_dict() for paper in self.supporting_papers],
            "common_belief": self.common_belief,
            "contrarian_view": self.contrarian_view,
            "why_wrong": self.why_wrong,
            "recommendation": self.recommendation,
            "enterprise_implication": self.enterprise_implication,
            "scorecard": self.scorecard(),
            "rejection_reason": self.rejection_reason,
        }


@dataclass(frozen=True)
class Position:
    common_belief: str
    contrarian_view: str
    why_wrong: str
    recommendation: str
    enterprise_implication: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PositionStrengthResult:
    contrarian: int
    decisiveness: int
    tension: int
    specificity: int
    passed: bool
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PostDraft:
    hook: str
    body: str
    word_count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperSummary:
    title: str
    source: str
    authors: list[str]
    url: str
    summary: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationResult:
    novelty: int
    relevance: int
    insight: int
    position_strength: int
    clarity: int
    passed: bool
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeliveryArtifact:
    channel: str
    path: str
    preview: str
    target: str
    sent: bool
    status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunState:
    used_on: date
    recent_themes: list[str] = field(default_factory=list)
    paper_pool: PaperPool | None = None
    lead_paper_summary: PaperSummary | None = None
    candidate_themes: list[ThemeCandidate] = field(default_factory=list)
    selected_theme: ThemeCandidate | None = None
    rejected_themes: list[ThemeCandidate] = field(default_factory=list)
    position: Position | None = None
    position_strength: PositionStrengthResult | None = None
    post: PostDraft | None = None
    evaluation: EvaluationResult | None = None
    storage_path: str | None = None
    run_log_path: str | None = None

    def scores_dict(self) -> dict[str, Any] | None:
        if not (self.selected_theme and self.position_strength and self.evaluation):
            return None
        return {
            "theme_selection": self.selected_theme.scorecard(),
            "position_strength": self.position_strength.as_dict(),
            "evaluation": self.evaluation.as_dict(),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "paper_pool": [paper.as_dict() for paper in self.paper_pool.deduped]
            if self.paper_pool
            else [],
            "candidate_themes": [candidate.as_dict() for candidate in self.candidate_themes],
            "selected_theme": self.selected_theme.theme if self.selected_theme else None,
            "rejected_themes": [candidate.as_dict() for candidate in self.rejected_themes],
            "position": self.position.as_dict() if self.position else None,
            "post": self.post.body if self.post else None,
            "scores": self.scores_dict(),
            "meta": {
                "used_on": self.used_on.isoformat(),
                "recent_themes": list(self.recent_themes),
                "lead_paper_summary": self.lead_paper_summary.as_dict()
                if self.lead_paper_summary
                else None,
                "storage_path": self.storage_path,
                "run_log_path": self.run_log_path,
            },
        }


@dataclass(frozen=True)
class PipelineResult:
    state: RunState
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
    run_log_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "state": self.state.as_dict(),
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
            "lead_paper_summary": self.lead_paper_summary.as_dict(),
            "why_selected": self.selected_theme.why_selected,
            "why_debatable": self.selected_theme.why_debatable,
            "rejected_themes": [candidate.as_dict() for candidate in self.rejected_themes],
            "position": self.position.as_dict(),
            "position_strength": self.position_strength.as_dict(),
            "post": self.post.as_dict(),
            "evaluation": self.evaluation.as_dict(),
            "storage_path": self.storage_path,
            "deliveries": [delivery.as_dict() for delivery in self.deliveries],
        }
        if self.run_log_path:
            payload["run_log_path"] = self.run_log_path
        return payload
