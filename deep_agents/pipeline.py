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
SEMANTIC_STOPWORDS = {
    "about",
    "across",
    "after",
    "agent",
    "agents",
    "architecture",
    "because",
    "before",
    "between",
    "build",
    "design",
    "enterprise",
    "enterprises",
    "into",
    "language",
    "models",
    "paper",
    "papers",
    "problem",
    "should",
    "system",
    "systems",
    "their",
    "there",
    "these",
    "this",
    "through",
    "understanding",
    "using",
    "with",
    "workflow",
    "workflows",
}

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


def _semantic_tokens(text: str) -> set[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
    return {
        token
        for token in normalized.split()
        if len(token) >= 4 and token not in SEMANTIC_STOPWORDS
    }


def _paper_semantic_match_score(paper: Paper, candidate) -> int:
    paper_title_tokens = _semantic_tokens(paper.title)
    paper_abstract_tokens = _semantic_tokens(paper.abstract)
    candidate_tokens = _semantic_tokens(
        " ".join(
            [
                candidate.theme,
                candidate.why_selected,
                candidate.why_debatable,
                candidate.common_belief,
                candidate.contrarian_view,
                candidate.why_wrong,
                candidate.recommendation,
                candidate.enterprise_implication,
            ]
        )
    )
    title_overlap = len(paper_title_tokens & candidate_tokens)
    abstract_overlap = len(paper_abstract_tokens & candidate_tokens)
    return 3 * title_overlap + abstract_overlap


def rank_papers(
    papers: list[Paper],
    *,
    selected_theme,
    alternative_themes,
    limit: int = 5,
) -> list[Paper]:
    score_by_fingerprint: dict[str, int] = {}
    candidate_weights = [(selected_theme, 5), *[(candidate, 3) for candidate in alternative_themes]]
    supporting_fingerprints = {
        paper.fingerprint
        for candidate, _ in candidate_weights
        for paper in candidate.supporting_papers
    }
    minimum_semantic_match = 4

    for paper in papers:
        total_score = 0
        matched = paper.fingerprint in supporting_fingerprints
        for candidate, weight in candidate_weights:
            match_score = _paper_semantic_match_score(paper, candidate)
            if match_score >= minimum_semantic_match:
                matched = True
                total_score += weight * match_score
            if any(paper.fingerprint == supported.fingerprint for supported in candidate.supporting_papers):
                candidate_score = (
                    candidate.debate_score
                    + candidate.relevance_score
                    + candidate.novelty_score
                    + candidate.specificity_score
                )
                total_score += weight * candidate_score
        if matched:
            score_by_fingerprint[paper.fingerprint] = total_score + max(1, 4 - paper.tier)

    ranked = sorted(
        [paper for paper in papers if paper.fingerprint in score_by_fingerprint],
        key=lambda paper: (
            score_by_fingerprint.get(paper.fingerprint, 0),
            -paper.tier,
            paper.published_on.toordinal(),
        ),
        reverse=True,
    )
    deduped: list[Paper] = []
    seen: set[str] = set()
    for paper in ranked:
        if paper.fingerprint in seen:
            continue
        seen.add(paper.fingerprint)
        deduped.append(paper)
        if len(deduped) >= limit:
            break
    return deduped


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
        alternatives = synthesis.alternative_themes
        rejected = synthesis.rejected_themes
        top_papers = rank_papers(
            paper_pool.deduped,
            selected_theme=selected,
            alternative_themes=alternatives,
        )
        lead_paper_summary = summarize_paper(top_papers[0] if top_papers else selected.supporting_papers[0])
        position = synthesis.position
        position_strength = synthesis.position_strength
        post = synthesis.post
        state.top_papers = top_papers
        state.lead_paper_summary = lead_paper_summary
        state.synthesis_provenance = synthesis.provenance
        state.selected_theme = selected
        state.alternative_themes = alternatives
        state.rejected_themes = rejected
        state.candidate_themes = [selected, *alternatives, *rejected]
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
        deliveries = self.delivery_manager.deliver(
            used_on=run_date,
            top_papers=top_papers,
            lead_paper_summary=lead_paper_summary,
            synthesis_provenance=synthesis.provenance,
            theme=selected,
            position=position,
            post=post,
            send_live_email=send_live_email,
            send_live_discord=send_live_discord,
        )
        storage_path = self.research_store.save(
            used_on=run_date,
            paper_pool=paper_pool,
            top_papers=top_papers,
            lead_paper_summary=lead_paper_summary,
            synthesis_provenance=synthesis.provenance,
            theme=selected,
            alternative_themes=alternatives,
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
            self.paper_memory.remember(top_papers)
            self.theme_memory.remember(selected.theme, run_date)
            self.reasoning_memory.remember(
                used_on=run_date,
                selected_theme=selected,
                alternative_themes=alternatives,
                rejected_themes=rejected,
                evaluation=evaluation,
                position_strength=position_strength,
                storage_path=str(storage_path),
                run_log_path=str(run_log_path),
            )
        return PipelineResult(
            state=state,
            paper_pool=paper_pool,
            top_papers=top_papers,
            lead_paper_summary=lead_paper_summary,
            selected_theme=selected,
            alternative_themes=alternatives,
            rejected_themes=rejected,
            position=position,
            position_strength=position_strength,
            post=post,
            evaluation=evaluation,
            storage_path=str(storage_path),
            deliveries=deliveries,
            run_log_path=str(run_log_path),
        )
