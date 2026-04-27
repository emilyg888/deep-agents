from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .delivery import DeliveryManager
from .heuristics import (
    assess_position_strength,
    build_position,
    build_post,
    build_theme_candidates,
    select_theme,
)
from .memory import PaperMemoryStore, ThemeMemoryStore
from .models import EvaluationResult, Paper, PaperSummary, PipelineResult
from .samples import sample_source_catalog
from .sources import SourceCatalog
from .storage import ResearchStore

DEFAULT_RESEARCH_DIR = Path("/Users/emilygao/LocalDocuments/Obsidian/research")


def evaluate_candidate(
    *,
    novelty_score: int,
    relevance_score: int,
    position_strength_score: int,
    word_count: int,
) -> EvaluationResult:
    clarity = 5 if 150 <= word_count <= 180 else 4 if word_count < 150 else 3
    insight = min(5, max(3, position_strength_score))
    reasons: list[str] = []
    if novelty_score < 3:
        reasons.append("Novelty below threshold.")
    if position_strength_score < 3:
        reasons.append("Position strength below threshold.")
    if word_count > 180:
        reasons.append("Draft exceeds target post length.")

    return EvaluationResult(
        novelty=novelty_score,
        relevance=relevance_score,
        insight=insight,
        position_strength=position_strength_score,
        clarity=clarity,
        passed=not reasons,
        reasons=reasons,
    )


def summarize_paper(paper: Paper) -> PaperSummary:
    abstract = " ".join(paper.abstract.split())
    first_sentence = abstract.split(". ", 1)[0].strip()
    summary = first_sentence if first_sentence.endswith(".") else f"{first_sentence}."
    return PaperSummary(
        title=paper.title,
        source=paper.source,
        authors=list(paper.authors),
        url=paper.url,
        summary=summary,
    )


@dataclass
class PipelineRunner:
    root_dir: Path
    source_catalog: SourceCatalog = field(default_factory=sample_source_catalog)
    research_dir: Path = DEFAULT_RESEARCH_DIR

    def __post_init__(self) -> None:
        self.paper_memory = PaperMemoryStore(self.root_dir / "memory" / "paper_memory.json")
        self.theme_memory = ThemeMemoryStore(self.root_dir / "memory" / "theme_memory.json")
        self.research_store = ResearchStore(self.research_dir)
        self.delivery_manager = DeliveryManager(self.root_dir / "delivery")

    def run(
        self,
        papers: list[Paper] | None = None,
        *,
        used_on: date | None = None,
        respect_memory: bool = True,
        send_live_email: bool = False,
        send_live_discord: bool = False,
    ) -> PipelineResult:
        run_date = used_on or date.today()
        fetched_papers = papers if papers is not None else self.source_catalog.fetch_all()
        paper_pool = self.paper_memory.build_paper_pool(
            fetched_papers,
            ignore_memory=not respect_memory,
        )
        if not paper_pool.deduped:
            raise ValueError("No new papers available after deduplication.")

        recent_themes = self.theme_memory.recent_themes(limit=3) if respect_memory else []
        candidates = build_theme_candidates(paper_pool.deduped, recent_themes)
        if len(candidates) < 3:
            raise ValueError("Could not extract 3 to 5 viable themes from the paper pool.")

        selected, rejected = select_theme(candidates)
        lead_paper_summary = summarize_paper(selected.supporting_papers[0])
        position = build_position(selected)
        position_strength = assess_position_strength(selected)
        if not position_strength.passed:
            raise ValueError("; ".join(position_strength.reasons))

        post = build_post(selected, position)
        evaluation = evaluate_candidate(
            novelty_score=selected.novelty_score,
            relevance_score=selected.relevance_score,
            position_strength_score=min(
                5,
                round(
                    (
                        position_strength.contrarian
                        + position_strength.tension
                        + position_strength.specificity
                    )
                    / 3
                ),
            ),
            word_count=post.word_count,
        )
        if not evaluation.passed:
            raise ValueError("; ".join(evaluation.reasons))

        deliveries = self.delivery_manager.deliver(
            used_on=run_date,
            lead_paper_summary=lead_paper_summary,
            theme=selected,
            position=position,
            post=post,
            send_live_email=send_live_email,
            send_live_discord=send_live_discord,
        )
        storage_path = self.research_store.save(
            used_on=run_date,
            paper_pool=paper_pool,
            lead_paper_summary=lead_paper_summary,
            theme=selected,
            rejected_themes=rejected,
            position=position,
            position_strength=position_strength,
            post=post,
            evaluation=evaluation,
            deliveries=deliveries,
        )

        if respect_memory:
            self.paper_memory.remember(paper_pool.deduped)
            self.theme_memory.remember(selected.theme, run_date)
        return PipelineResult(
            paper_pool=paper_pool,
            lead_paper_summary=lead_paper_summary,
            selected_theme=selected,
            rejected_themes=rejected,
            position=position,
            position_strength=position_strength,
            post=post,
            evaluation=evaluation,
            storage_path=str(storage_path),
            deliveries=deliveries,
        )
