from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .delivery import DeliveryManager
from .evaluation import EvaluationEngine, build_default_evaluation_engine
from .memory import PaperMemoryStore, ReasoningMemoryStore, ThemeMemoryStore
from .models import Paper, PaperSummary, PipelineResult, RunState
from .samples import build_default_source_catalog
from .sources import SourceCatalog
from .storage import ResearchStore, RunLogStore
from .synthesis import SynthesisEngine, build_default_synthesis_engine

DEFAULT_RESEARCH_DIR = Path("/Users/emilygao/LocalDocuments/Obsidian/research")

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
    source_catalog: SourceCatalog = field(default_factory=build_default_source_catalog)
    synthesis_engine: SynthesisEngine = field(default_factory=build_default_synthesis_engine)
    evaluation_engine: EvaluationEngine = field(default_factory=build_default_evaluation_engine)
    research_dir: Path = DEFAULT_RESEARCH_DIR

    def __post_init__(self) -> None:
        self.paper_memory = PaperMemoryStore(self.root_dir / "memory" / "paper_memory.json")
        self.theme_memory = ThemeMemoryStore(self.root_dir / "memory" / "theme_memory.json")
        self.reasoning_memory = ReasoningMemoryStore(
            self.root_dir / "memory" / "reasoning_memory.json"
        )
        self.research_store = ResearchStore(self.research_dir)
        self.run_log_store = RunLogStore(self.root_dir / "runs")
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
        state = RunState(used_on=run_date)
        fetched_papers = papers if papers is not None else self.source_catalog.fetch_all()
        paper_pool = self.paper_memory.build_paper_pool(
            fetched_papers,
            ignore_memory=not respect_memory,
        )
        state.paper_pool = paper_pool
        if not paper_pool.deduped:
            raise ValueError("No new papers available after deduplication.")

        state.recent_themes = (
            self.theme_memory.recent_themes(as_of=run_date, months=6)
            if respect_memory
            else []
        )
        synthesis = self.synthesis_engine.synthesize(
            paper_pool.deduped,
            state.recent_themes,
        )
        selected = synthesis.selected_theme
        rejected = synthesis.rejected_themes
        lead_paper_summary = summarize_paper(selected.supporting_papers[0])
        position = synthesis.position
        position_strength = synthesis.position_strength
        post = synthesis.post
        state.lead_paper_summary = lead_paper_summary
        state.selected_theme = selected
        state.rejected_themes = rejected
        state.candidate_themes = [selected, *rejected]
        state.position = position
        state.position_strength = position_strength
        state.post = post
        evaluation = self.evaluation_engine.evaluate(
            theme=selected,
            position=position,
            position_strength=position_strength,
            post=post,
        )
        state.evaluation = evaluation
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
        state.storage_path = str(storage_path)
        state.run_log_path = str(
            self.run_log_store.base_dir / f"run_{run_date.isoformat()}.json"
        )
        run_log_path = self.run_log_store.save(state, deliveries)

        if respect_memory:
            self.paper_memory.remember(paper_pool.deduped)
            self.theme_memory.remember(selected.theme, run_date)
            self.reasoning_memory.remember(
                used_on=run_date,
                selected_theme=selected,
                rejected_themes=rejected,
                evaluation=evaluation,
                position_strength=position_strength,
                storage_path=str(storage_path),
                run_log_path=str(run_log_path),
            )
        return PipelineResult(
            state=state,
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
            run_log_path=str(run_log_path),
        )
