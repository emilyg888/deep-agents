from __future__ import annotations

import os
from datetime import date

from .models import Paper
from .sources import (
    ArxivPaperSource,
    FallbackPaperSource,
    HackerNewsPaperSource,
    OpenAlexPaperSource,
    RSSPaperSource,
    SemanticScholarPaperSource,
    SourceCatalog,
    StaticPaperSource,
    YouTubePaperSource,
)


def sample_papers() -> list[Paper]:
    return sample_source_catalog().fetch_all()


def sample_static_sources() -> list[StaticPaperSource]:
    return [
        StaticPaperSource(
            name="arXiv",
            tier=1,
            papers=[
                Paper(
                    title="Benchmarking Agent Reliability in Tool-Using Systems",
                    authors=["M. Chen", "A. Singh"],
                    abstract="We study agent reliability, tool orchestration, human approval, and recovery design for enterprise workflows.",
                    source="arXiv",
                    url="https://example.org/papers/agent-reliability",
                    published_on=date(2026, 4, 12),
                    tier=1,
                ),
                Paper(
                    title="Tool-Augmented Agents Need Explicit Failure Recovery",
                    authors=["P. Rocha"],
                    abstract="Tool-using agents improve task completion only when explicit fallback, retries, and approval checkpoints are designed in.",
                    source="arXiv",
                    url="https://example.org/papers/agent-failure-recovery",
                    published_on=date(2026, 4, 14),
                    tier=1,
                ),
            ],
        ),
        StaticPaperSource(
            name="Semantic Scholar",
            tier=1,
            papers=[
                Paper(
                    title="Why Multi-Agent Coordination Fails Under Ambiguous Workflow Ownership",
                    authors=["L. Patel"],
                    abstract="Coordination overhead rises when planner and worker agents do not have deterministic boundaries or clear handoffs.",
                    source="Semantic Scholar",
                    url="https://example.org/papers/multi-agent-workflow",
                    published_on=date(2026, 4, 15),
                    tier=1,
                )
            ],
        ),
        StaticPaperSource(
            name="OpenAlex",
            tier=1,
            papers=[
                Paper(
                    title="Evaluation Gates for Production GenAI Programs",
                    authors=["S. Osei"],
                    abstract="Teams need metrics, pass fail gates, benchmark design, and rollback criteria before scaling model traffic.",
                    source="OpenAlex",
                    url="https://example.org/papers/evaluation-gates",
                    published_on=date(2026, 4, 18),
                    tier=1,
                )
            ],
        ),
        StaticPaperSource(
            name="MIT Sloan Management Review",
            tier=2,
            papers=[
                Paper(
                    title="Enterprise RAG Systems Overfit Retrieval and Underdesign Decisions",
                    authors=["R. Gomez", "T. Li"],
                    abstract="Retrieval pipelines keep expanding, but task framing, answer constraints, and evidence thresholds dominate quality.",
                    source="MIT Sloan Management Review",
                    url="https://example.org/papers/rag-decision-framing",
                    published_on=date(2026, 4, 10),
                    tier=2,
                )
            ],
        ),
        StaticPaperSource(
            name="Harvard Business Review",
            tier=2,
            papers=[
                Paper(
                    title="Persistent Memory in Enterprise Assistants: UX Win or Governance Debt",
                    authors=["N. Ibrahim"],
                    abstract="Long-lived memory improves personalization but expands retention risk, stale assumptions, and audit burden.",
                    source="Harvard Business Review",
                    url="https://example.org/papers/memory-governance",
                    published_on=date(2026, 4, 8),
                    tier=2,
                )
            ],
        ),
        StaticPaperSource(
            name="DeepLearning.AI",
            tier=2,
            papers=[
                Paper(
                    title="Enterprise Agents Need Workflow Contracts",
                    authors=["A. Moore"],
                    abstract="Agent systems underperform when the workflow contract is vague and handoffs to tools are underspecified.",
                    source="DeepLearning.AI",
                    url="https://example.org/papers/workflow-contracts",
                    published_on=date(2026, 4, 21),
                    tier=2,
                )
            ],
        ),
        StaticPaperSource(
            name="Hacker News",
            tier=3,
            papers=[
                Paper(
                    title="Teams Keep Shipping Multi-Agent Demos Without Operator Controls",
                    authors=["HN Discussion"],
                    abstract="Practitioners describe coordination sprawl, weak approvals, and poor observability in multi-agent experiments.",
                    source="Hacker News",
                    url="https://example.org/papers/hn-multi-agent-controls",
                    published_on=date(2026, 4, 19),
                    tier=3,
                )
            ],
        ),
        StaticPaperSource(
            name="YouTube",
            tier=3,
            papers=[
                Paper(
                    title="Architects Are Reframing Agent Memory as Governed State",
                    authors=["YouTube Creator"],
                    abstract="A practitioner talk argues enterprise memory should be audited, bounded, and expired rather than treated as a default personalization feature.",
                    source="YouTube",
                    url="https://example.org/papers/youtube-memory-state",
                    published_on=date(2026, 4, 20),
                    tier=3,
                )
            ],
        ),
    ]


def sample_source_catalog() -> SourceCatalog:
    return SourceCatalog(sample_static_sources())


def build_default_source_catalog() -> SourceCatalog:
    mode = os.getenv("DEEP_AGENTS_SOURCE_MODE", "hybrid").strip().lower()
    static_sources = {source.name: source for source in sample_static_sources()}

    live_sources = [
        ArxivPaperSource(
            query=os.getenv(
                "DEEP_AGENTS_ARXIV_QUERY",
                "all:agentic AI OR all:enterprise AI OR all:RAG",
            ),
            limit=int(os.getenv("DEEP_AGENTS_ARXIV_LIMIT", "5")),
        ),
        SemanticScholarPaperSource(
            query=os.getenv(
                "DEEP_AGENTS_SEMANTIC_SCHOLAR_QUERY",
                "agentic ai enterprise ai rag workflow governance",
            ),
            limit=int(os.getenv("DEEP_AGENTS_SEMANTIC_SCHOLAR_LIMIT", "5")),
        ),
        OpenAlexPaperSource(
            tier=1,
            query=os.getenv(
                "DEEP_AGENTS_OPENALEX_QUERY",
                "agentic ai enterprise ai rag workflow governance",
            ),
            limit=int(os.getenv("DEEP_AGENTS_OPENALEX_LIMIT", "5")),
            from_publication_date=os.getenv(
                "DEEP_AGENTS_OPENALEX_FROM_PUBLICATION_DATE",
                "",
            )
            or None,
        ),
        RSSPaperSource(
            name="MIT Sloan Management Review",
            tier=2,
            feed_url=os.getenv("DEEP_AGENTS_MIT_SLOAN_RSS_URL", ""),
            limit=int(os.getenv("DEEP_AGENTS_MIT_SLOAN_LIMIT", "5")),
        ),
        RSSPaperSource(
            name="Harvard Business Review",
            tier=2,
            feed_url=os.getenv("DEEP_AGENTS_HBR_RSS_URL", ""),
            limit=int(os.getenv("DEEP_AGENTS_HBR_LIMIT", "5")),
        ),
        RSSPaperSource(
            name="DeepLearning.AI",
            tier=2,
            feed_url=os.getenv("DEEP_AGENTS_DEEPLEARNINGAI_RSS_URL", ""),
            limit=int(os.getenv("DEEP_AGENTS_DEEPLEARNINGAI_LIMIT", "5")),
        ),
        HackerNewsPaperSource(
            limit=int(os.getenv("DEEP_AGENTS_HN_LIMIT", "5")),
        ),
        YouTubePaperSource(
            tier=3,
            query=os.getenv(
                "DEEP_AGENTS_YOUTUBE_QUERY",
                "enterprise AI architecture agents RAG evaluation",
            ),
            limit=int(os.getenv("DEEP_AGENTS_YOUTUBE_LIMIT", "5")),
            published_after=os.getenv("DEEP_AGENTS_YOUTUBE_PUBLISHED_AFTER", "")
            or None,
        ),
    ]

    if mode == "static":
        return sample_source_catalog()

    if mode == "live":
        return SourceCatalog(live_sources)

    hybrid_sources = [
        FallbackPaperSource(
            name=live_source.name,
            tier=live_source.tier,
            primary=live_source,
            fallback=static_sources[live_source.name],
        )
        for live_source in live_sources
        if live_source.name in static_sources
    ]
    return SourceCatalog(hybrid_sources)
