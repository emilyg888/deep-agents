from __future__ import annotations

from datetime import date
from pathlib import Path

from .models import (
    DeliveryArtifact,
    EvaluationResult,
    PaperSummary,
    PaperPool,
    Position,
    PositionStrengthResult,
    PostDraft,
    ThemeCandidate,
)


def _slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")


class ResearchStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def save(
        self,
        *,
        used_on: date,
        paper_pool: PaperPool,
        lead_paper_summary: PaperSummary,
        theme: ThemeCandidate,
        rejected_themes: list[ThemeCandidate],
        position: Position,
        position_strength: PositionStrengthResult,
        post: PostDraft,
        evaluation: EvaluationResult,
        deliveries: list[DeliveryArtifact],
    ) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{used_on.isoformat()}-{_slugify(theme.theme)}.md"
        path = self.base_dir / filename

        lead_paper_line = (
            f"[{lead_paper_summary.title}]({lead_paper_summary.url})"
            f" — {lead_paper_summary.source}"
        )
        supporting_lines = "\n".join(
            f"- [{paper.title}]({paper.url}) — {paper.source}"
            for paper in theme.supporting_papers
        )
        rejected_lines = "\n".join(
            f"- {candidate.theme}: {candidate.rejection_reason}"
            for candidate in rejected_themes
        )
        deprioritized_lines = "\n".join(
            f"- {paper.title} — {paper.source}"
            for paper in paper_pool.similarity_deprioritized
        ) or "- None"
        delivery_lines = "\n".join(
            f"- {delivery.channel}: {delivery.path}" for delivery in deliveries
        )

        content = f"""---
date: {used_on.isoformat()}
theme: "{theme.theme}"
---

# {theme.theme}

## Paper Pool
- Fetched: {len(paper_pool.fetched)}
- Deduped: {len(paper_pool.deduped)}
- Exact dropped: {len(paper_pool.exact_dropped)}
- Similarity deprioritized: {len(paper_pool.similarity_deprioritized)}

### Similarity Deprioritized Papers
{deprioritized_lines}

## Why Selected
{theme.why_selected}

## Lead Paper Summary
- Paper: {lead_paper_line}
- Authors: {", ".join(lead_paper_summary.authors)}
- Summary: {lead_paper_summary.summary}

## Why Debatable
{theme.why_debatable}

## Why Other Themes Were Rejected
{rejected_lines or "- None"}

## Position
- Common belief: {position.common_belief}
- Contrarian view: {position.contrarian_view}
- Why wrong: {position.why_wrong}
- Recommendation: {position.recommendation}
- Enterprise implication: {position.enterprise_implication}

## Position Strength
- Contrarian: {position_strength.contrarian}/5
- Tension: {position_strength.tension}/5
- Specificity: {position_strength.specificity}/5
- Passed: {position_strength.passed}

## LinkedIn Draft
{post.body}

## Reference Links
{supporting_lines}

## Evaluation
- Novelty: {evaluation.novelty}/5
- Relevance: {evaluation.relevance}/5
- Insight: {evaluation.insight}/5
- Position strength: {evaluation.position_strength}/5
- Clarity: {evaluation.clarity}/5
- Passed: {evaluation.passed}

## Delivery
{delivery_lines}
"""
        path.write_text(content, encoding="utf-8")
        return path
