from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .models import (
    DeliveryArtifact,
    EvaluationResult,
    Paper,
    PaperPool,
    PaperSummary,
    Position,
    PositionStrengthResult,
    PostDraft,
    RunState,
    SynthesisProvenance,
    ThemeCandidate,
)


def _slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")


def _paper_summary_text(paper: Paper) -> str:
    abstract = " ".join(paper.abstract.split())
    first_sentence = abstract.split(". ", 1)[0].strip()
    return first_sentence if first_sentence.endswith(".") else f"{first_sentence}."


def _paper_sections(papers: list[Paper]) -> str:
    if not papers:
        return "- None"
    divider = "\n---\n"
    sections = []
    for index, paper in enumerate(papers, start=1):
        sections.append(
            "\n".join(
                [
                    f"### {index}. {paper.title}",
                    f"- Citation: [{paper.url}]({paper.url})",
                    f"- Source: {paper.source}",
                    f"- Summary: {_paper_summary_text(paper)}",
                ]
            )
        )
    return divider.join(sections)


class ResearchStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def save(
        self,
        *,
        used_on: date,
        paper_pool: PaperPool,
        top_papers: list[Paper],
        lead_paper_summary: PaperSummary,
        synthesis_provenance: SynthesisProvenance,
        theme: ThemeCandidate,
        alternative_themes: list[ThemeCandidate],
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
        top_paper_sections = _paper_sections(top_papers)
        alternative_lines = "\n".join(
            f"- {candidate.theme}" for candidate in alternative_themes
        ) or "- None"
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
        synthesis_lines = [
            f"- Engine used: {synthesis_provenance.engine_used}",
            f"- Fallback used: {synthesis_provenance.fallback_used}",
        ]
        if synthesis_provenance.primary_engine:
            synthesis_lines.append(
                f"- Primary engine: {synthesis_provenance.primary_engine}"
            )
        if synthesis_provenance.fallback_reason:
            synthesis_lines.append(
                f"- Fallback reason: {synthesis_provenance.fallback_reason}"
            )
        synthesis_summary = "\n".join(synthesis_lines)

        content = f"""---
date: {used_on.isoformat()}
theme: "{theme.theme}"
---

# {theme.theme}

## Synthesis Provenance
{synthesis_summary}

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

## Top 5 Papers
{top_paper_sections}

## Why Debatable
{theme.why_debatable}

## Other Viable Themes
{alternative_lines}

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
- Decisiveness: {position_strength.decisiveness}/5
- Tension: {position_strength.tension}/5
- Specificity: {position_strength.specificity}/5
- Passed: {position_strength.passed}

## LinkedIn Draft
{post.body}

## Reference Links
{top_paper_sections}

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


class RunLogStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def save(self, state: RunState, deliveries: list[DeliveryArtifact]) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f"run_{state.used_on.isoformat()}.json"
        payload = state.as_dict()
        payload["deliveries"] = [delivery.as_dict() for delivery in deliveries]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
