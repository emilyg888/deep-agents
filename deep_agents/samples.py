from __future__ import annotations

import os
from datetime import date

from .models import Paper
from .sources import (
    ArxivPaperSource,
    FallbackPaperSource,
    GoogleNewsPaperSource,
    HackerNewsPaperSource,
    OpenAlexPaperSource,
    RSSPaperSource,
    SemanticScholarPaperSource,
    SourceCatalog,
    StaticPaperSource,
    TopicFilteredPaperSource,
    YouTubePaperSource,
)

GENAI_FS_QUERY = "generative AI adoption financial services banking insurance"
GENAI_FS_ARXIV_QUERY = (
    'all:"generative AI" AND (all:"financial services" OR all:banking OR all:insurance OR all:fintech)'
)
GENAI_FS_HN_KEYWORDS = (
    "generative ai",
    "genai",
    "financial services",
    "banking",
    "insurance",
    "fintech",
)
GENAI_FS_TOPIC_KEYWORD_GROUPS = (
    (
        "generative ai",
        "genai",
        "artificial intelligence",
        " ai ",
        "ai adoption",
        "ai agent",
        "ai agents",
    ),
    (
        "financial services",
        "bank",
        "banks",
        "banking",
        "insurance",
        "insurer",
        "insurers",
        "fintech",
        "wealth",
        "payments",
        "lending",
        "credit",
        "claims",
        "underwriting",
    ),
    (
        "adoption",
        "adopt",
        "pilot",
        "pilots",
        "rollout",
        "deploy",
        "implementation",
        "use case",
        "use cases",
        "workflow",
        "operating",
        "controls",
        "governance",
        "model risk",
        "automation",
        "transformation",
        "productivity",
        "customer",
        "fraud",
        "process",
    ),
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
                    title="Benchmarking GenAI Adoption Controls in Banking Operations",
                    authors=["M. Chen", "A. Singh"],
                    abstract="We study generative AI adoption in banking operations, focusing on approval design, model risk controls, and workflow reliability.",
                    source="arXiv",
                    url="https://example.org/papers/banking-genai-controls",
                    published_on=date(2026, 4, 12),
                    tier=1,
                ),
                Paper(
                    title="Generative AI Adoption in Insurance Claims Needs Human Escalation Gates",
                    authors=["P. Rocha"],
                    abstract="Insurance claims teams adopt GenAI successfully only when escalation, auditability, and recovery checkpoints are designed in.",
                    source="arXiv",
                    url="https://example.org/papers/insurance-genai-escalation",
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
                    title="Financial Services GenAI Pilots Stall When Workflow Ownership Is Ambiguous",
                    authors=["L. Patel"],
                    abstract="Bank and insurer GenAI programs stall when pilots do not define ownership, deterministic handoffs, and operating accountability.",
                    source="Semantic Scholar",
                    url="https://example.org/papers/fs-genai-workflow-ownership",
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
                    title="Evaluation Gates for Production GenAI in Financial Services",
                    authors=["S. Osei"],
                    abstract="Banks and insurers need metrics, pass fail gates, benchmark design, and rollback criteria before scaling generative AI adoption.",
                    source="OpenAlex",
                    url="https://example.org/papers/fs-genai-evaluation-gates",
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
                    title="Banks Are Moving GenAI from Pilots to Decision Workflows",
                    authors=["R. Gomez", "T. Li"],
                    abstract="Banking GenAI adoption is shifting from chat assistants toward decision workflows where answer constraints and evidence thresholds dominate quality.",
                    source="MIT Sloan Management Review",
                    url="https://example.org/papers/banking-genai-decision-workflows",
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
                    title="Financial Services GenAI Adoption Is a Governance Test, Not a Productivity Contest",
                    authors=["N. Ibrahim"],
                    abstract="Financial institutions adopting GenAI face retention risk, audit burden, model risk management, and stale assumptions before productivity gains scale.",
                    source="Harvard Business Review",
                    url="https://example.org/papers/fs-genai-governance-test",
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
                    title="Insurance GenAI Rollouts Need Workflow Contracts Before More Automation",
                    authors=["A. Moore"],
                    abstract="Insurance GenAI systems underperform when workflow contracts are vague and handoffs between underwriters, claims handlers, and tools are underspecified.",
                    source="DeepLearning.AI",
                    url="https://example.org/papers/insurance-genai-workflow-contracts",
                    published_on=date(2026, 4, 21),
                    tier=2,
                )
            ],
        ),
        StaticPaperSource(
            name="Google News",
            tier=2,
            papers=[
                Paper(
                    title="Banks Accelerate GenAI Adoption but Keep Risk Teams in the Loop",
                    authors=["Google News"],
                    abstract="Recent news coverage shows financial services firms expanding generative AI adoption while retaining approval gates for regulated decisions.",
                    source="Google News",
                    url="https://example.org/news/banking-genai-adoption-risk",
                    published_on=date(2026, 4, 22),
                    tier=2,
                )
            ],
        ),
        StaticPaperSource(
            name="Finextra",
            tier=2,
            papers=[
                Paper(
                    title="Financial Services Firms Shift GenAI Adoption Toward Operating Controls",
                    authors=["Finextra"],
                    abstract="Banking and payments leaders are moving GenAI adoption from experiments toward operating controls, audit trails, and regulated workflows.",
                    source="Finextra",
                    url="https://example.org/news/finextra-genai-operating-controls",
                    published_on=date(2026, 4, 23),
                    tier=2,
                )
            ],
        ),
        StaticPaperSource(
            name="The Financial Brand",
            tier=2,
            papers=[
                Paper(
                    title="Banking GenAI Adoption Is Being Reframed Around Customer Trust",
                    authors=["The Financial Brand"],
                    abstract="Retail banks adopting generative AI are learning that customer trust, disclosure, and service recovery matter more than raw automation volume.",
                    source="The Financial Brand",
                    url="https://example.org/news/financial-brand-genai-trust",
                    published_on=date(2026, 4, 24),
                    tier=2,
                )
            ],
        ),
        StaticPaperSource(
            name="Insurance Journal",
            tier=2,
            papers=[
                Paper(
                    title="Insurers Expand GenAI Adoption in Claims but Tighten Review Gates",
                    authors=["Insurance Journal"],
                    abstract="Insurance carriers are broadening GenAI adoption in claims and underwriting while tightening human review gates and audit expectations.",
                    source="Insurance Journal",
                    url="https://example.org/news/insurance-genai-review-gates",
                    published_on=date(2026, 4, 25),
                    tier=2,
                )
            ],
        ),
        StaticPaperSource(
            name="Hacker News",
            tier=3,
            papers=[
                Paper(
                    title="Discussion: Why Bank GenAI Pilots Rarely Survive Model Risk Review",
                    authors=["HN Discussion"],
                    abstract="Practitioners describe financial services GenAI adoption barriers including weak approvals, poor observability, and model risk review gaps.",
                    source="Hacker News",
                    url="https://example.org/papers/hn-bank-genai-risk-review",
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
                    title="Banking CIOs Are Reframing GenAI Adoption as Governed Workflow Change",
                    authors=["YouTube Creator"],
                    abstract="A practitioner talk argues financial services GenAI adoption should be audited, bounded, and tied to workflow redesign rather than treated as generic productivity tooling.",
                    source="YouTube",
                    url="https://example.org/papers/youtube-fs-genai-governed-workflow",
                    published_on=date(2026, 4, 20),
                    tier=3,
                )
            ],
        ),
    ]


def sample_source_catalog() -> SourceCatalog:
    return SourceCatalog(sample_static_sources())


def _topic_filtered(source) -> TopicFilteredPaperSource:
    return TopicFilteredPaperSource(
        name=source.name,
        tier=source.tier,
        primary=source,
        keyword_groups=GENAI_FS_TOPIC_KEYWORD_GROUPS,
    )


def build_default_source_catalog() -> SourceCatalog:
    mode = os.getenv("DEEP_AGENTS_SOURCE_MODE", "hybrid").strip().lower()
    static_sources = {source.name: source for source in sample_static_sources()}

    live_sources = [
        _topic_filtered(
            ArxivPaperSource(
                query=os.getenv(
                    "DEEP_AGENTS_ARXIV_QUERY",
                    GENAI_FS_ARXIV_QUERY,
                ),
                limit=int(os.getenv("DEEP_AGENTS_ARXIV_LIMIT", "5")),
            )
        ),
        _topic_filtered(
            SemanticScholarPaperSource(
                query=os.getenv(
                    "DEEP_AGENTS_SEMANTIC_SCHOLAR_QUERY",
                    GENAI_FS_QUERY,
                ),
                limit=int(os.getenv("DEEP_AGENTS_SEMANTIC_SCHOLAR_LIMIT", "5")),
            )
        ),
        _topic_filtered(
            OpenAlexPaperSource(
                tier=1,
                query=os.getenv(
                    "DEEP_AGENTS_OPENALEX_QUERY",
                    GENAI_FS_QUERY,
                ),
                limit=int(os.getenv("DEEP_AGENTS_OPENALEX_LIMIT", "5")),
                from_publication_date=os.getenv(
                    "DEEP_AGENTS_OPENALEX_FROM_PUBLICATION_DATE",
                    "",
                )
                or None,
            )
        ),
        _topic_filtered(
            RSSPaperSource(
                name="MIT Sloan Management Review",
                tier=2,
                feed_url=os.getenv("DEEP_AGENTS_MIT_SLOAN_RSS_URL", ""),
                limit=int(os.getenv("DEEP_AGENTS_MIT_SLOAN_LIMIT", "5")),
            )
        ),
        _topic_filtered(
            RSSPaperSource(
                name="Harvard Business Review",
                tier=2,
                feed_url=os.getenv("DEEP_AGENTS_HBR_RSS_URL", ""),
                limit=int(os.getenv("DEEP_AGENTS_HBR_LIMIT", "5")),
            )
        ),
        _topic_filtered(
            RSSPaperSource(
                name="DeepLearning.AI",
                tier=2,
                feed_url=os.getenv("DEEP_AGENTS_DEEPLEARNINGAI_RSS_URL", ""),
                limit=int(os.getenv("DEEP_AGENTS_DEEPLEARNINGAI_LIMIT", "5")),
            )
        ),
        _topic_filtered(
            GoogleNewsPaperSource(
                query=os.getenv("DEEP_AGENTS_GOOGLE_NEWS_QUERY", GENAI_FS_QUERY),
                limit=int(os.getenv("DEEP_AGENTS_GOOGLE_NEWS_LIMIT", "10")),
                region=os.getenv("DEEP_AGENTS_GOOGLE_NEWS_REGION", "US"),
                language=os.getenv("DEEP_AGENTS_GOOGLE_NEWS_LANGUAGE", "en"),
            )
        ),
        _topic_filtered(
            RSSPaperSource(
                name="Finextra",
                tier=2,
                feed_url=os.getenv(
                    "DEEP_AGENTS_FINEXTRA_RSS_URL",
                    "https://www.finextra.com/rss/news.aspx",
                ),
                limit=int(os.getenv("DEEP_AGENTS_FINEXTRA_LIMIT", "5")),
            )
        ),
        _topic_filtered(
            RSSPaperSource(
                name="The Financial Brand",
                tier=2,
                feed_url=os.getenv(
                    "DEEP_AGENTS_FINANCIAL_BRAND_RSS_URL",
                    "https://thefinancialbrand.com/feed/",
                ),
                limit=int(os.getenv("DEEP_AGENTS_FINANCIAL_BRAND_LIMIT", "5")),
            )
        ),
        _topic_filtered(
            RSSPaperSource(
                name="Insurance Journal",
                tier=2,
                feed_url=os.getenv(
                    "DEEP_AGENTS_INSURANCE_JOURNAL_RSS_URL",
                    "https://www.insurancejournal.com/rss/news/",
                ),
                limit=int(os.getenv("DEEP_AGENTS_INSURANCE_JOURNAL_LIMIT", "5")),
            )
        ),
        _topic_filtered(
            HackerNewsPaperSource(
                limit=int(os.getenv("DEEP_AGENTS_HN_LIMIT", "5")),
                topic_keywords=GENAI_FS_HN_KEYWORDS,
            )
        ),
        _topic_filtered(
            YouTubePaperSource(
                tier=3,
                query=os.getenv(
                    "DEEP_AGENTS_YOUTUBE_QUERY",
                    GENAI_FS_QUERY,
                ),
                limit=int(os.getenv("DEEP_AGENTS_YOUTUBE_LIMIT", "5")),
                published_after=os.getenv("DEEP_AGENTS_YOUTUBE_PUBLISHED_AFTER", "")
                or None,
            )
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
