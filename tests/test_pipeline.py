from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from deep_agents.memory import PaperMemoryStore, ThemeMemoryStore
from deep_agents.models import Paper
from deep_agents.pipeline import PipelineRunner
from deep_agents.samples import sample_source_catalog
from deep_agents.sources import SourceCatalog, StaticPaperSource


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
            store.remember("Theme A", date(2026, 4, 24))
            store.remember("Theme B", date(2026, 4, 25))
            store.remember("Theme C", date(2026, 4, 26))
            self.assertTrue(store.was_used_recently("theme b"))
            self.assertFalse(store.was_used_recently("Theme D"))


class SourceCatalogTests(unittest.TestCase):
    def test_default_source_catalog_covers_all_design_tiers(self) -> None:
        catalog = sample_source_catalog()
        fetched = catalog.fetch_all()
        self.assertGreaterEqual(len(catalog.sources), 8)
        self.assertTrue(any(paper.tier == 1 for paper in fetched))
        self.assertTrue(any(paper.tier == 2 for paper in fetched))
        self.assertTrue(any(paper.tier == 3 for paper in fetched))


class PipelineRunnerTests(unittest.TestCase):
    def test_pipeline_generates_research_and_delivery_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = PipelineRunner(
                root_dir=Path(tmpdir),
                research_dir=Path(tmpdir) / "research",
            )
            result = runner.run(used_on=date(2026, 4, 27))

            self.assertTrue(result.position_strength.passed)
            self.assertTrue(result.evaluation.passed)
            self.assertGreaterEqual(len(result.rejected_themes), 2)
            self.assertTrue(Path(result.storage_path).exists())
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

    def test_pipeline_rejects_when_all_papers_are_already_seen(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = PipelineRunner(
                root_dir=Path(tmpdir),
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
                research_dir=Path(tmpdir) / "research",
            )
            result = runner.run(used_on=date(2026, 4, 27))
            self.assertIn("agent", result.selected_theme.theme.lower())


if __name__ == "__main__":
    unittest.main()
