from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from deep_agents.memory import PaperMemoryStore, ThemeMemoryStore
from deep_agents.models import Paper
from deep_agents.pipeline import PipelineRunner
from deep_agents.samples import sample_source_catalog
from deep_agents.sources import (
    FallbackPaperSource,
    OpenAlexPaperSource,
    SourceCatalog,
    StaticPaperSource,
    YouTubePaperSource,
)
from deep_agents.evaluation import (
    DeterministicEvaluationEngine,
    FallbackEvaluationEngine,
)
from deep_agents.synthesis import (
    DeterministicSynthesisEngine,
    FallbackSynthesisEngine,
    OpenAISynthesisEngine,
    SynthesisResult,
)


class MemoryStoreTests(unittest.TestCase):
    def test_paper_memory_deduplicates_exact_fingerprints(self) -> None:
        papers = sample_source_catalog().fetch_all()
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PaperMemoryStore(Path(tmpdir) / "paper_memory.json")
            pool = store.build_paper_pool(papers)
            self.assertEqual(len(pool.fetched), len(papers))
            self.assertEqual(len(pool.exact_dropped), 0)

            store.remember([papers[0]])
            pool = store.build_paper_pool(papers)
            self.assertEqual(len(pool.exact_dropped), 1)
            self.assertEqual(len(pool.deduped), len(papers) - 1)

    def test_paper_memory_deprioritizes_high_similarity_titles(self) -> None:
        similar_papers = [
            Paper(
                title="Agent reliability needs explicit failure recovery",
                authors=["A. One"],
                abstract="Agent reliability and failure recovery.",
                source="Source A",
                url="https://example.org/a",
                published_on=date(2026, 4, 20),
                tier=1,
            ),
            Paper(
                title="Agent reliability needs explicit failure-recovery",
                authors=["B. Two"],
                abstract="A variant paper about the same theme.",
                source="Source B",
                url="https://example.org/b",
                published_on=date(2026, 4, 21),
                tier=2,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PaperMemoryStore(Path(tmpdir) / "paper_memory.json")
            pool = store.build_paper_pool(similar_papers)
            self.assertEqual(len(pool.similarity_deprioritized), 1)
            self.assertEqual(pool.deduped[-1].title, similar_papers[1].title)

    def test_theme_memory_marks_recent_themes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ThemeMemoryStore(Path(tmpdir) / "theme_memory.json")
            store.remember("Theme A", date(2025, 9, 24))
            store.remember("Theme B", date(2025, 11, 25))
            store.remember("Theme C", date(2026, 4, 26))
            self.assertTrue(
                store.was_used_recently(
                    "theme b",
                    as_of=date(2026, 4, 29),
                    months=6,
                )
            )
            self.assertFalse(
                store.was_used_recently(
                    "theme a",
                    as_of=date(2026, 4, 29),
                    months=6,
                )
            )
            self.assertFalse(store.was_used_recently("Theme D"))


class SourceCatalogTests(unittest.TestCase):
    def test_default_source_catalog_covers_all_design_tiers(self) -> None:
        catalog = sample_source_catalog()
        fetched = catalog.fetch_all()
        self.assertGreaterEqual(len(catalog.sources), 8)
        self.assertTrue(any(paper.tier == 1 for paper in fetched))
        self.assertTrue(any(paper.tier == 2 for paper in fetched))
        self.assertTrue(any(paper.tier == 3 for paper in fetched))

    def test_fallback_source_uses_static_when_primary_fails(self) -> None:
        class FailingSource:
            name = "arXiv"
            tier = 1

            def fetch(self) -> list[Paper]:
                raise ValueError("boom")

        static_source = sample_source_catalog().sources[0]
        source = FallbackPaperSource(
            name="arXiv",
            tier=1,
            primary=FailingSource(),
            fallback=static_source,
        )
        papers = source.fetch()
        self.assertGreater(len(papers), 0)
        self.assertEqual(papers[0].source, "arXiv")

    @patch.dict("os.environ", {"OPENALEX_API_KEY": "test-key"})
    @patch("deep_agents.sources._fetch_json")
    def test_openalex_source_parses_work_results(self, mock_fetch_json) -> None:
        mock_fetch_json.return_value = {
            "results": [
                {
                    "display_name": "Workflow contracts matter more than agent autonomy",
                    "abstract_inverted_index": {
                        "Workflow": [0],
                        "contracts": [1],
                        "matter": [2],
                        "for": [3],
                        "enterprise": [4],
                        "agents": [5],
                    },
                    "id": "https://openalex.org/W123",
                    "publication_date": "2026-04-23",
                    "authorships": [
                        {"author": {"display_name": "A. Researcher"}},
                    ],
                }
            ]
        }
        papers = OpenAlexPaperSource(limit=1).fetch()
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].source, "OpenAlex")
        self.assertEqual(papers[0].authors, ["A. Researcher"])
        self.assertIn("enterprise agents", papers[0].abstract.lower())

    @patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"})
    @patch("deep_agents.sources._fetch_json")
    def test_youtube_source_parses_search_results(self, mock_fetch_json) -> None:
        mock_fetch_json.return_value = {
            "items": [
                {
                    "id": {"videoId": "abc123"},
                    "snippet": {
                        "title": "Architects are reframing agent memory as governed state",
                        "description": "A practitioner talk about enterprise memory controls.",
                        "channelTitle": "AI Architecture Weekly",
                        "publishedAt": "2026-04-20T10:00:00Z",
                    },
                }
            ]
        }
        papers = YouTubePaperSource(limit=1).fetch()
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].source, "YouTube")
        self.assertEqual(papers[0].url, "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(papers[0].authors, ["AI Architecture Weekly"])


class SynthesisEngineTests(unittest.TestCase):
    def test_fallback_synthesis_uses_deterministic_engine_on_failure(self) -> None:
        class FailingEngine:
            def synthesize(self, papers: list[Paper], recent_themes: list[str]) -> SynthesisResult:
                raise RuntimeError("llm unavailable")

        deterministic = DeterministicSynthesisEngine()
        engine = FallbackSynthesisEngine(FailingEngine(), deterministic)
        result = engine.synthesize(sample_source_catalog().fetch_all(), [])
        self.assertTrue(result.position_strength.passed)
        self.assertGreater(len(result.post.body), 0)

    def test_fallback_synthesis_fails_closed_on_validation_errors(self) -> None:
        class InvalidEngine:
            def synthesize(self, papers: list[Paper], recent_themes: list[str]) -> SynthesisResult:
                raise ValueError("position rejected")

        deterministic = DeterministicSynthesisEngine()
        engine = FallbackSynthesisEngine(InvalidEngine(), deterministic)
        with self.assertRaisesRegex(ValueError, "position rejected"):
            engine.synthesize(sample_source_catalog().fetch_all(), [])

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_openai_synthesis_clamps_out_of_range_scores(self) -> None:
        class FakeResponse:
            def __init__(self, content: str) -> None:
                self.content = content

        class FakeModel:
            def __init__(self) -> None:
                self.calls = 0

            def invoke(self, prompt: str) -> FakeResponse:
                del prompt
                self.calls += 1
                if self.calls == 1:
                    return FakeResponse(
                        """
                        {
                          "themes": [
                            {
                              "theme": "Agents need reliability boundaries",
                              "why_selected": "This theme best matches the paper pool.",
                              "why_debatable": "Architects disagree on how much autonomy is safe.",
                              "common_belief": "Smarter models should own more workflow steps.",
                              "contrarian_view": "Bounded agents outperform autonomous agents in production.",
                              "why_wrong": "Autonomy expands failure modes faster than controls.",
                              "recommendation": "Use deterministic boundaries and explicit approvals.",
                              "enterprise_implication": "This shifts agent design toward governed orchestration.",
                              "novelty_score": 8,
                              "relevance_score": 7,
                              "debate_score": 9,
                              "contrarian_score": 8,
                              "decisiveness_score": 8,
                              "tension_score": 6,
                              "specificity_score": 7,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": null,
                              "supporting_paper_urls": ["https://example.org/papers/agent-reliability"]
                            },
                            {
                              "theme": "Evaluation before scale",
                              "why_selected": "Evaluation is important.",
                              "why_debatable": "Teams disagree on sequencing.",
                              "common_belief": "You can scale first and evaluate later.",
                              "contrarian_view": "Evaluation has to come first.",
                              "why_wrong": "Scale locks in weak behavior.",
                              "recommendation": "Define gates before rollout.",
                              "enterprise_implication": "This improves governance.",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 2,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Another theme had stronger debate and novelty scores.",
                              "supporting_paper_urls": ["https://example.org/papers/evaluation-gates"]
                            },
                            {
                              "theme": "Memory as governance",
                              "why_selected": "Memory drives policy risk.",
                              "why_debatable": "Teams disagree on personalization vs control.",
                              "common_belief": "Memory mostly improves UX.",
                              "contrarian_view": "Memory is mainly a governance problem.",
                              "why_wrong": "Persistent memory accumulates stale assumptions.",
                              "recommendation": "Constrain memory and audit it.",
                              "enterprise_implication": "This reduces compliance risk.",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 2,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Theme used recently.",
                              "supporting_paper_urls": ["https://example.org/papers/memory-governance"]
                            }
                          ]
                        }
                        """
                    )
                if self.calls == 2:
                    return FakeResponse(
                        """
                        {
                          "common_belief": "Most enterprises keep giving agents too much workflow authority.",
                          "why_wrong": "That is wrong because unchecked autonomy expands failure modes faster than controls.",
                          "contrarian_view": "Bounded agents outperform autonomous agents in production.",
                          "recommendation": "Use deterministic boundaries and explicit approvals.",
                          "enterprise_implication": "This shifts agent design toward governed orchestration.",
                          "contrarian_score": 8,
                          "decisiveness_score": 8,
                          "tension_score": 6,
                          "specificity_score": 7
                        }
                        """
                    )
                return FakeResponse(
                    """
                    {
                      "post_paragraphs": [
                        "Agents need reliability boundaries, not more autonomy.",
                        "Most enterprises are wrong to let autonomy outrun controls in production systems.",
                        "Design governed orchestration instead of unchecked agent freedom."
                      ]
                    }
                    """
                )

        engine = OpenAISynthesisEngine()
        engine.model = FakeModel()
        result = engine.synthesize(sample_source_catalog().fetch_all(), [])
        self.assertEqual(result.selected_theme.novelty_score, 5)
        self.assertEqual(result.selected_theme.relevance_score, 5)
        self.assertTrue(result.position_strength.passed)
        self.assertEqual(result.position_strength.decisiveness, 5)
        self.assertIn("governed orchestration", result.post.body.lower())

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_openai_synthesis_retries_position_after_rejection_feedback(self) -> None:
        class FakeResponse:
            def __init__(self, content: str) -> None:
                self.content = content

        class FakeModel:
            def __init__(self) -> None:
                self.calls = 0

            def invoke(self, prompt: str) -> FakeResponse:
                del prompt
                self.calls += 1
                if self.calls == 1:
                    return FakeResponse(
                        """
                        {
                          "themes": [
                            {
                              "theme": "Agents need deterministic boundaries",
                              "why_selected": "The paper pool clusters around agent reliability and control.",
                              "why_debatable": "Architects disagree on how much autonomy is safe in production.",
                              "common_belief": "Smarter models should own more workflow steps.",
                              "contrarian_view": "Bounded agents outperform autonomous agents in production.",
                              "why_wrong": "Unchecked autonomy expands failure modes faster than controls.",
                              "recommendation": "Use deterministic boundaries and explicit approvals.",
                              "enterprise_implication": "This shifts agent design toward governed orchestration.",
                              "novelty_score": 5,
                              "relevance_score": 5,
                              "debate_score": 5,
                              "contrarian_score": 5,
                              "decisiveness_score": 5,
                              "tension_score": 5,
                              "specificity_score": 5,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": null,
                              "supporting_paper_urls": ["https://example.org/papers/agent-reliability"]
                            },
                            {
                              "theme": "Evaluation before scale",
                              "why_selected": "Evaluation matters.",
                              "why_debatable": "Teams disagree on sequencing.",
                              "common_belief": "You can scale first and evaluate later.",
                              "contrarian_view": "Evaluation has to come first.",
                              "why_wrong": "Scale locks in weak behavior.",
                              "recommendation": "Define gates before rollout.",
                              "enterprise_implication": "This improves governance.",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 2,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Another theme had stronger debate and novelty scores.",
                              "supporting_paper_urls": ["https://example.org/papers/evaluation-gates"]
                            },
                            {
                              "theme": "Memory as governance",
                              "why_selected": "Memory drives policy risk.",
                              "why_debatable": "Teams disagree on personalization vs control.",
                              "common_belief": "Memory mostly improves UX.",
                              "contrarian_view": "Memory is mainly a governance problem.",
                              "why_wrong": "Persistent memory accumulates stale assumptions.",
                              "recommendation": "Constrain memory and audit it.",
                              "enterprise_implication": "This reduces compliance risk.",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 2,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Theme used recently.",
                              "supporting_paper_urls": ["https://example.org/papers/memory-governance"]
                            }
                          ]
                        }
                        """
                    )
                if self.calls == 2:
                    return FakeResponse(
                        """
                        {
                          "common_belief": "Most enterprises are increasing agent autonomy in production.",
                          "why_wrong": "That approach expands risk faster than teams can manage it.",
                          "contrarian_view": "Bounded agents outperform autonomous agents in production.",
                          "recommendation": "Use deterministic boundaries and explicit approvals.",
                          "enterprise_implication": "This shifts agent design toward governed orchestration.",
                          "contrarian_score": 4,
                          "decisiveness_score": 4,
                          "tension_score": 4,
                          "specificity_score": 4
                        }
                        """
                    )
                if self.calls == 3:
                    return FakeResponse(
                        """
                        {
                          "common_belief": "Most enterprises still let agents own too much workflow authority.",
                          "why_wrong": "That is wrong because unchecked autonomy breaks control design and pushes failure recovery onto operators.",
                          "contrarian_view": "Enterprise agents should act as bounded judgment layers inside deterministic workflows.",
                          "recommendation": "Use deterministic boundaries, explicit approvals, and recovery paths.",
                          "enterprise_implication": "This changes agent architecture from autonomy theater into governed orchestration.",
                          "contrarian_score": 5,
                          "decisiveness_score": 5,
                          "tension_score": 4,
                          "specificity_score": 5
                        }
                        """
                    )
                return FakeResponse(
                    """
                    {
                      "post_paragraphs": [
                        "Most enterprises are wrong to let agent autonomy outrun workflow controls.",
                        "Bounded agents create more value because deterministic boundaries make failure recovery and approvals enforceable.",
                        "Architectures should wrap model judgment inside governed orchestration, not pretend autonomy is the product."
                      ]
                    }
                    """
                )

        engine = OpenAISynthesisEngine()
        engine.model = FakeModel()
        engine.max_position_attempts = 2
        result = engine.synthesize(sample_source_catalog().fetch_all(), [])
        self.assertTrue(result.position_strength.passed)
        self.assertIn("that is wrong", result.position.why_wrong.lower())

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_openai_synthesis_retries_theme_generation_when_all_themes_are_rejected(self) -> None:
        class FakeResponse:
            def __init__(self, content: str) -> None:
                self.content = content

        class FakeModel:
            def __init__(self) -> None:
                self.calls = 0

            def invoke(self, prompt: str) -> FakeResponse:
                del prompt
                self.calls += 1
                if self.calls == 1:
                    return FakeResponse(
                        """
                        {
                          "themes": [
                            {
                              "theme": "Theme A",
                              "why_selected": "A",
                              "why_debatable": "A",
                              "common_belief": "A",
                              "contrarian_view": "A",
                              "why_wrong": "A is wrong.",
                              "recommendation": "A",
                              "enterprise_implication": "A",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 2,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Rejected",
                              "supporting_paper_urls": ["https://example.org/papers/agent-reliability"]
                            },
                            {
                              "theme": "Theme B",
                              "why_selected": "B",
                              "why_debatable": "B",
                              "common_belief": "B",
                              "contrarian_view": "B",
                              "why_wrong": "B is wrong.",
                              "recommendation": "B",
                              "enterprise_implication": "B",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 2,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Rejected",
                              "supporting_paper_urls": ["https://example.org/papers/evaluation-gates"]
                            },
                            {
                              "theme": "Theme C",
                              "why_selected": "C",
                              "why_debatable": "C",
                              "common_belief": "C",
                              "contrarian_view": "C",
                              "why_wrong": "C is wrong.",
                              "recommendation": "C",
                              "enterprise_implication": "C",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 2,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Rejected",
                              "supporting_paper_urls": ["https://example.org/papers/memory-governance"]
                            }
                          ]
                        }
                        """
                    )
                if self.calls == 2:
                    return FakeResponse(
                        """
                        {
                          "themes": [
                            {
                              "theme": "Agents need deterministic boundaries",
                              "why_selected": "The paper pool clusters around agent reliability and control.",
                              "why_debatable": "Architects disagree on how much autonomy is safe in production.",
                              "common_belief": "Smarter models should own more workflow steps.",
                              "contrarian_view": "Bounded agents outperform autonomous agents in production.",
                              "why_wrong": "Unchecked autonomy is wrong because it expands failure modes faster than controls.",
                              "recommendation": "Use deterministic boundaries and explicit approvals.",
                              "enterprise_implication": "This shifts agent design toward governed orchestration.",
                              "novelty_score": 5,
                              "relevance_score": 5,
                              "debate_score": 5,
                              "contrarian_score": 5,
                              "decisiveness_score": 5,
                              "tension_score": 5,
                              "specificity_score": 5,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": null,
                              "supporting_paper_urls": ["https://example.org/papers/agent-reliability"]
                            },
                            {
                              "theme": "Evaluation before scale",
                              "why_selected": "Evaluation matters.",
                              "why_debatable": "Teams disagree on sequencing.",
                              "common_belief": "You can scale first and evaluate later.",
                              "contrarian_view": "Evaluation has to come first.",
                              "why_wrong": "Scale first is wrong because it locks in weak behavior.",
                              "recommendation": "Define gates before rollout.",
                              "enterprise_implication": "This improves governance.",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 4,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Another theme had stronger debate and novelty scores.",
                              "supporting_paper_urls": ["https://example.org/papers/evaluation-gates"]
                            },
                            {
                              "theme": "Memory as governance",
                              "why_selected": "Memory drives policy risk.",
                              "why_debatable": "Teams disagree on personalization vs control.",
                              "common_belief": "Memory mostly improves UX.",
                              "contrarian_view": "Memory is mainly a governance problem.",
                              "why_wrong": "Persistent memory is wrong when it accumulates stale assumptions.",
                              "recommendation": "Constrain memory and audit it.",
                              "enterprise_implication": "This reduces compliance risk.",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 4,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Theme used recently.",
                              "supporting_paper_urls": ["https://example.org/papers/memory-governance"]
                            }
                          ]
                        }
                        """
                    )
                if self.calls == 3:
                    return FakeResponse(
                        """
                        {
                          "common_belief": "Most enterprises still give agents too much workflow authority.",
                          "why_wrong": "That is wrong because unchecked autonomy expands failure modes faster than controls.",
                          "contrarian_view": "Bounded agents outperform autonomous agents in production.",
                          "recommendation": "Use deterministic boundaries and explicit approvals.",
                          "enterprise_implication": "This shifts agent design toward governed orchestration.",
                          "contrarian_score": 5,
                          "decisiveness_score": 5,
                          "tension_score": 4,
                          "specificity_score": 5
                        }
                        """
                    )
                return FakeResponse(
                    """
                    {
                      "post_paragraphs": [
                        "Most enterprises are wrong to let agent autonomy outrun controls.",
                        "Bounded agents create more value because deterministic boundaries make failure recovery enforceable.",
                        "Architectures should wrap model judgment inside governed orchestration."
                      ]
                    }
                    """
                )

        engine = OpenAISynthesisEngine()
        engine.model = FakeModel()
        engine.max_theme_attempts = 2
        result = engine.synthesize(sample_source_catalog().fetch_all(), [])
        self.assertEqual(result.selected_theme.theme, "Agents need deterministic boundaries")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_openai_synthesis_ranks_multiple_valid_candidates(self) -> None:
        class FakeResponse:
            def __init__(self, content: str) -> None:
                self.content = content

        class FakeModel:
            def __init__(self) -> None:
                self.calls = 0

            def invoke(self, prompt: str) -> FakeResponse:
                del prompt
                self.calls += 1
                if self.calls == 1:
                    return FakeResponse(
                        """
                        {
                          "themes": [
                            {
                              "theme": "Agents need deterministic boundaries",
                              "why_selected": "This theme challenges current agent deployment practice.",
                              "why_debatable": "It forces architects to trade autonomy for operational control.",
                              "common_belief": "More autonomous agents create more value.",
                              "contrarian_view": "Bounded agents should sit inside deterministic workflows rather than own the workflow.",
                              "why_wrong": "That is wrong because autonomy expands failure modes faster than observability and approvals.",
                              "recommendation": "Use deterministic boundaries and explicit handoffs instead of unchecked autonomy.",
                              "enterprise_implication": "This structurally shifts agent architecture toward governed workflows and rollback-ready operations.",
                              "novelty_score": 5,
                              "relevance_score": 5,
                              "debate_score": 5,
                              "contrarian_score": 5,
                              "decisiveness_score": 5,
                              "tension_score": 4,
                              "specificity_score": 5,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": null,
                              "supporting_paper_urls": ["https://example.org/papers/agent-reliability"]
                            },
                            {
                              "theme": "Evaluation before scale",
                              "why_selected": "This theme challenges the current scale-first rollout pattern.",
                              "why_debatable": "It forces a trade-off between growth speed and decision quality.",
                              "common_belief": "Teams can scale first and formalize evaluation later.",
                              "contrarian_view": "Evaluation has to come before scale in enterprise systems rather than after incidents.",
                              "why_wrong": "That is wrong because scale locks weak behavior into workflows before teams know what good looks like.",
                              "recommendation": "Define pass-fail gates before rollout instead of scaling on usage signals.",
                              "enterprise_implication": "This structurally shifts AI delivery from experimentation theater into governed product operations.",
                              "novelty_score": 5,
                              "relevance_score": 5,
                              "debate_score": 5,
                              "contrarian_score": 5,
                              "decisiveness_score": 5,
                              "tension_score": 5,
                              "specificity_score": 5,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "LLM thought this theme was too familiar.",
                              "supporting_paper_urls": ["https://example.org/papers/evaluation-gates"]
                            },
                            {
                              "theme": "Memory as governance",
                              "why_selected": "Memory creates policy risk.",
                              "why_debatable": "Teams disagree on convenience versus control.",
                              "common_belief": "Persistent memory mainly improves UX.",
                              "contrarian_view": "Memory is mostly a governance problem.",
                              "why_wrong": "That is wrong because persistent state quietly accumulates stale assumptions.",
                              "recommendation": "Constrain memory and audit it.",
                              "enterprise_implication": "This reduces compliance risk.",
                              "novelty_score": 4,
                              "relevance_score": 4,
                              "debate_score": 4,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "Theme used recently.",
                              "supporting_paper_urls": ["https://example.org/papers/memory-governance"]
                            }
                          ]
                        }
                        """
                    )
                if self.calls == 2:
                    return FakeResponse(
                        """
                        {
                          "common_belief": "Most enterprises scale first and evaluate later.",
                          "why_wrong": "That is wrong because scale locks in weak behavior before teams know what good looks like.",
                          "contrarian_view": "Evaluation has to come before scale in enterprise systems.",
                          "recommendation": "Define pass-fail gates before rollout.",
                          "enterprise_implication": "This turns AI delivery into a governable product discipline.",
                          "contrarian_score": 5,
                          "decisiveness_score": 5,
                          "tension_score": 4,
                          "specificity_score": 5
                        }
                        """
                    )
                return FakeResponse(
                    """
                    {
                      "post_paragraphs": [
                        "Most enterprises are wrong to scale AI before they design evaluation.",
                        "That failure turns usage into a fake proxy for quality.",
                        "Architectures need gates before traffic, not after incidents."
                      ]
                    }
                    """
                )

        engine = OpenAISynthesisEngine()
        engine.model = FakeModel()
        result = engine.synthesize(sample_source_catalog().fetch_all(), [])
        self.assertEqual(result.selected_theme.theme, "Evaluation before scale")
        self.assertIsNone(result.selected_theme.rejection_reason)
        self.assertIn(
            "Another theme had a stronger weighted selection score.",
            {candidate.rejection_reason for candidate in result.rejected_themes},
        )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_openai_synthesis_accepts_two_themes_for_narrow_topics(self) -> None:
        class FakeResponse:
            def __init__(self, content: str) -> None:
                self.content = content

        class FakeModel:
            def __init__(self) -> None:
                self.calls = 0

            def invoke(self, prompt: str) -> FakeResponse:
                del prompt
                self.calls += 1
                if self.calls == 1:
                    return FakeResponse(
                        """
                        {
                          "themes": [
                            {
                              "theme": "Evaluation is measuring the wrong unit",
                              "why_selected": "The papers focus on case-specific evaluation and workflow misses.",
                              "why_debatable": "This is a paradigm challenge because it questions model-first evaluation.",
                              "common_belief": "Clinical AI quality is mostly a model scoring problem.",
                              "contrarian_view": "The real issue is system behavior across workflow context rather than isolated model quality.",
                              "why_wrong": "That is the wrong problem because model metrics hide failures in handoffs, escalation, and workflow behavior.",
                              "recommendation": "Design evaluation around system behavior gates before optimizing model scores.",
                              "enterprise_implication": "This reframes clinical AI from benchmark optimization into workflow control design.",
                              "novelty_score": 5,
                              "enterprise_relevance_score": 5,
                              "debate_score": 5,
                              "contrarian_score": 5,
                              "decisiveness_score": 5,
                              "tension_score": 4,
                              "specificity_score": 5,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": null,
                              "supporting_paper_urls": ["https://example.org/papers/agent-reliability"]
                            },
                            {
                              "theme": "Case-specific rubrics still miss workflow control",
                              "why_selected": "The papers discuss case-level evaluation detail.",
                              "why_debatable": "This is a paradigm challenge because it rejects better rubrics as the main answer.",
                              "common_belief": "Better rubrics will solve clinical AI evaluation quality.",
                              "contrarian_view": "The real issue is that workflow control is the unit of failure, not rubric precision.",
                              "why_wrong": "That is the wrong framing because better rubrics still evaluate outputs instead of system behavior.",
                              "recommendation": "Move evaluation toward workflow control points and escalation checks rather than richer scoring alone.",
                              "enterprise_implication": "This changes evaluation from annotation quality to operational control architecture.",
                              "novelty_score": 4,
                              "enterprise_relevance_score": 5,
                              "debate_score": 4,
                              "contrarian_score": 4,
                              "decisiveness_score": 4,
                              "tension_score": 4,
                              "specificity_score": 4,
                              "typical_architect_agrees": false,
                              "strong_architect_debates": true,
                              "rejection_reason": "weak",
                              "supporting_paper_urls": ["https://example.org/papers/evaluation-gates"]
                            }
                          ]
                        }
                        """
                    )
                if self.calls == 2:
                    return FakeResponse(
                        """
                        {
                          "common_belief": "Most enterprises still evaluate clinical AI as if model scores are the main unit of quality.",
                          "why_wrong": "That is the wrong problem framing because workflow behavior, escalation, and control points determine real clinical failure.",
                          "contrarian_view": "The real issue is system behavior across workflow context, not isolated model quality.",
                          "recommendation": "Design evaluation around workflow control gates and escalation behavior.",
                          "enterprise_implication": "This reframes clinical AI evaluation into a system control problem.",
                          "contrarian_score": 5,
                          "decisiveness_score": 5,
                          "tension_score": 4,
                          "specificity_score": 5
                        }
                        """
                    )
                return FakeResponse(
                    """
                    {
                      "post_paragraphs": [
                        "Clinical AI is solving the wrong evaluation problem.",
                        "Most enterprises measure model quality when the real failure sits in workflow behavior and control.",
                        "Evaluation should gate system behavior, not just score outputs."
                      ]
                    }
                    """
                )

        papers = [
            Paper(
                title="Case-specific evaluation improves clinical AI assessment",
                authors=["A. Researcher"],
                abstract="Clinical AI teams are shifting toward case-specific evaluation.",
                source="Scenario",
                url="https://example.org/papers/agent-reliability",
                published_on=date(2026, 4, 20),
                tier=1,
            ),
            Paper(
                title="Clinical AI metrics need clinician-authored scoring",
                authors=["B. Researcher"],
                abstract="Researchers propose richer clinician-authored metrics.",
                source="Scenario",
                url="https://example.org/papers/evaluation-gates",
                published_on=date(2026, 4, 21),
                tier=1,
            ),
            Paper(
                title="Case-level clinical evaluation exposes hidden model failures",
                authors=["C. Researcher"],
                abstract="Case-level evaluation identifies workflow-specific failures.",
                source="Scenario",
                url="https://example.org/papers/memory-governance",
                published_on=date(2026, 4, 22),
                tier=1,
            ),
        ]

        engine = OpenAISynthesisEngine()
        engine.model = FakeModel()
        result = engine.synthesize(papers, [])
        self.assertEqual(result.selected_theme.theme, "Evaluation is measuring the wrong unit")


class EvaluationEngineTests(unittest.TestCase):
    def test_fallback_evaluation_uses_deterministic_engine_on_failure(self) -> None:
        class FailingEvaluationEngine:
            def evaluate(self, **kwargs):  # type: ignore[no-untyped-def]
                raise ValueError("llm unavailable")

        papers = sample_source_catalog().fetch_all()
        synthesis_result = DeterministicSynthesisEngine().synthesize(papers, [])
        engine = FallbackEvaluationEngine(
            FailingEvaluationEngine(),
            DeterministicEvaluationEngine(),
        )
        evaluation = engine.evaluate(
            theme=synthesis_result.selected_theme,
            position=synthesis_result.position,
            position_strength=synthesis_result.position_strength,
            post=synthesis_result.post,
        )
        self.assertTrue(evaluation.passed)
        self.assertGreaterEqual(evaluation.clarity, 3)


class PipelineRunnerTests(unittest.TestCase):
    def test_pipeline_generates_research_and_delivery_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = PipelineRunner(
                root_dir=Path(tmpdir),
                source_catalog=sample_source_catalog(),
                synthesis_engine=DeterministicSynthesisEngine(),
                research_dir=Path(tmpdir) / "research",
            )
            result = runner.run(used_on=date(2026, 4, 27))

            self.assertTrue(result.position_strength.passed)
            self.assertTrue(result.evaluation.passed)
            self.assertGreaterEqual(len(result.rejected_themes), 2)
            self.assertTrue(Path(result.storage_path).exists())
            self.assertIsNotNone(result.run_log_path)
            self.assertTrue(Path(result.run_log_path).exists())
            self.assertEqual(result.state.used_on, date(2026, 4, 27))
            self.assertEqual(result.state.run_log_path, result.run_log_path)
            self.assertEqual(result.state.storage_path, result.storage_path)
            self.assertEqual(result.state.selected_theme.theme, result.selected_theme.theme)
            self.assertGreaterEqual(len(result.state.rejected_themes), 2)
            state_payload = result.state.as_dict()
            self.assertEqual(
                set(state_payload.keys()),
                {
                    "paper_pool",
                    "candidate_themes",
                    "selected_theme",
                    "rejected_themes",
                    "position",
                    "post",
                    "scores",
                    "meta",
                },
            )
            self.assertIsInstance(state_payload["paper_pool"], list)
            self.assertEqual(state_payload["selected_theme"], result.selected_theme.theme)
            self.assertEqual(state_payload["post"], result.post.body)
            self.assertIn("evaluation", state_payload["scores"])
            self.assertEqual({delivery.channel for delivery in result.deliveries}, {"email", "discord"})
            self.assertIn("\n\n", result.post.body)
            self.assertTrue(result.lead_paper_summary.url.startswith("https://"))

            research_note = Path(result.storage_path).read_text()
            self.assertIn("## Lead Paper Summary", research_note)
            self.assertIn("## Reference Links", research_note)
            self.assertIn("](", research_note)

            email_delivery = next(delivery for delivery in result.deliveries if delivery.channel == "email")
            discord_delivery = next(delivery for delivery in result.deliveries if delivery.channel == "discord")
            self.assertEqual(email_delivery.target, "emsyd888@gmail.com")
            self.assertEqual(discord_delivery.target, "Weekflow")
            self.assertFalse(email_delivery.sent)
            self.assertFalse(discord_delivery.sent)
            self.assertEqual(email_delivery.status, "draft only")
            self.assertEqual(discord_delivery.status, "draft only")
            self.assertIn("To: emsyd888@gmail.com", Path(email_delivery.path).read_text())
            self.assertIn("Channel: Weekflow", Path(discord_delivery.path).read_text())
            reasoning_memory_path = Path(tmpdir) / "memory" / "reasoning_memory.json"
            self.assertTrue(reasoning_memory_path.exists())
            self.assertIn('"candidate_themes"', reasoning_memory_path.read_text())

    def test_pipeline_rejects_when_all_papers_are_already_seen(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = PipelineRunner(
                root_dir=Path(tmpdir),
                source_catalog=sample_source_catalog(),
                synthesis_engine=DeterministicSynthesisEngine(),
                research_dir=Path(tmpdir) / "research",
            )
            initial_pool = runner.source_catalog.fetch_all()
            runner.paper_memory.remember(initial_pool)
            with self.assertRaisesRegex(ValueError, "No new papers available"):
                runner.run(used_on=date(2026, 4, 27))

    def test_pipeline_works_with_custom_source_catalog(self) -> None:
        custom_catalog = SourceCatalog(
            [
                StaticPaperSource(
                    name="Custom Research",
                    tier=1,
                    papers=[
                        Paper(
                            title="Agent tool reliability needs approvals",
                            authors=["A. Test"],
                            abstract="Agent tools, reliability, approval, and workflow boundaries.",
                            source="Custom Research",
                            url="https://example.org/custom-1",
                            published_on=date(2026, 4, 22),
                            tier=1,
                        ),
                        Paper(
                            title="Workflow contracts matter more than agent autonomy",
                            authors=["B. Test"],
                            abstract="Workflow contracts and agent control points define outcomes.",
                            source="Custom Research",
                            url="https://example.org/custom-2",
                            published_on=date(2026, 4, 23),
                            tier=1,
                        ),
                        Paper(
                            title="Multi-agent coordination without ownership fails",
                            authors=["C. Test"],
                            abstract="Multi-agent coordination and ownership gaps create failure.",
                            source="Custom Research",
                            url="https://example.org/custom-3",
                            published_on=date(2026, 4, 24),
                            tier=1,
                        ),
                        Paper(
                            title="Retrieval systems fail when decision framing is vague",
                            authors=["D. Test"],
                            abstract="RAG, retrieval, evidence thresholds, and decision framing are more important than context volume.",
                            source="Custom Research",
                            url="https://example.org/custom-4",
                            published_on=date(2026, 4, 24),
                            tier=1,
                        ),
                        Paper(
                            title="Evaluation gates should precede scaling",
                            authors=["E. Test"],
                            abstract="Evaluation, benchmarks, rollout criteria, and quality gates need to exist before scale.",
                            source="Custom Research",
                            url="https://example.org/custom-5",
                            published_on=date(2026, 4, 24),
                            tier=1,
                        ),
                    ],
                )
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = PipelineRunner(
                root_dir=Path(tmpdir),
                source_catalog=custom_catalog,
                synthesis_engine=DeterministicSynthesisEngine(),
                research_dir=Path(tmpdir) / "research",
            )
            result = runner.run(used_on=date(2026, 4, 27))
            self.assertIn("agent", result.selected_theme.theme.lower())


if __name__ == "__main__":
    unittest.main()
