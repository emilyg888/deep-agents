from __future__ import annotations

import json
import os
from typing import Protocol

from langchain_openai import ChatOpenAI

from .heuristics import (
    is_incremental,
    post_has_clear_wrong_statement,
    position_introduces_different_mental_model,
    position_is_incremental,
    position_reframes_problem,
    theme_aligns_with_current_enterprise_trends,
    theme_has_debate_potential,
    theme_has_paradigm_signal,
    theme_debate_filter_reasons,
    theme_is_generic_importance_claim,
)
from .models import EvaluationResult, Position, PositionStrengthResult, PostDraft, ThemeCandidate


def _parse_json_object(text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1]
        candidate = candidate.rsplit("```", 1)[0]
    return json.loads(candidate)


def _position_strength_score(position_strength: PositionStrengthResult) -> int:
    return min(
        5,
        round(
            (
                position_strength.contrarian
                + position_strength.decisiveness
                + position_strength.tension
                + position_strength.specificity
            )
            / 4
        ),
    )


def _parse_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes"}:
            return True
        if normalized in {"false", "no"}:
            return False
    return default


class EvaluationEngine(Protocol):
    def evaluate(
        self,
        *,
        theme: ThemeCandidate,
        position: Position,
        position_strength: PositionStrengthResult,
        post: PostDraft,
    ) -> EvaluationResult:
        ...


class DeterministicEvaluationEngine:
    def evaluate(
        self,
        *,
        theme: ThemeCandidate,
        position: Position,
        position_strength: PositionStrengthResult,
        post: PostDraft,
    ) -> EvaluationResult:
        position_text = " ".join(
            [
                position.common_belief,
                position.why_wrong,
                position.contrarian_view,
                position.enterprise_implication,
            ]
        )
        position_strength_score = _position_strength_score(position_strength)
        clarity = 5 if 90 <= post.word_count <= 140 else 4 if post.word_count < 90 else 2
        insight = min(5, max(3, position_strength_score))
        reasons: list[str] = []
        if is_incremental(position_text) or position_is_incremental(theme):
            position_strength_score = min(position_strength_score, 3)
            insight = min(insight, 3)
            reasons.append("Position is incremental.")
        if theme_aligns_with_current_enterprise_trends(theme):
            position_strength_score = min(position_strength_score, 3)
            insight = min(insight, 3)
            reasons.append("Theme aligns with current enterprise trends.")
        if theme_is_generic_importance_claim(theme):
            position_strength_score = min(position_strength_score, 2)
            insight = min(insight, 2)
            reasons.append('Theme reduces to "X is important and should be done more."')
        if not theme_has_debate_potential(theme):
            position_strength_score = min(position_strength_score, 2)
            reasons.append("Theme does not have enough debate potential.")
        if not theme_has_paradigm_signal(theme):
            position_strength_score = min(position_strength_score, 3)
            insight = min(insight, 3)
        if not position_reframes_problem(theme):
            position_strength_score = min(position_strength_score, 3)
            insight = min(insight, 3)
            reasons.append("Position does not reframe the problem.")
        if position_reframes_problem(theme):
            position_strength_score = max(position_strength_score, 4)
            insight = max(insight, 4)
        if not position_introduces_different_mental_model(theme):
            position_strength_score = min(position_strength_score, 3)
        debate_filter_reasons = theme_debate_filter_reasons(theme)
        if debate_filter_reasons:
            reasons.extend(debate_filter_reasons)
        if theme.novelty_score < 3:
            reasons.append("Novelty below threshold.")
        if position_strength_score < 3:
            reasons.append("Position strength below threshold.")
        if post.word_count > 140:
            reasons.append("Draft exceeds target post length.")
        if not post_has_clear_wrong_statement(post.body):
            reasons.append("Draft does not clearly state what is wrong.")

        return EvaluationResult(
            novelty=theme.novelty_score,
            relevance=theme.relevance_score,
            insight=insight,
            position_strength=position_strength_score,
            clarity=clarity,
            passed=not reasons,
            reasons=reasons,
        )


class OpenAIEvaluationEngine:
    def __init__(self, *, model: str | None = None, temperature: float = 0.0) -> None:
        self.model = ChatOpenAI(
            model=model or os.getenv("DEEP_AGENTS_EVALUATION_MODEL", os.getenv("DEEP_AGENTS_OPENAI_MODEL", "gpt-4o-mini")),
            temperature=temperature,
        )
        self.deterministic_engine = DeterministicEvaluationEngine()

    def evaluate(
        self,
        *,
        theme: ThemeCandidate,
        position: Position,
        position_strength: PositionStrengthResult,
        post: PostDraft,
    ) -> EvaluationResult:
        deterministic = self.deterministic_engine.evaluate(
            theme=theme,
            position=position,
            position_strength=position_strength,
            post=post,
        )
        prompt = f"""
You are evaluating a research-driven LinkedIn post for enterprise AI architects.

First, apply a binary pre-filter. Reject immediately if the draft:
- describes multiple perspectives without taking a side
- uses neutral or academic tone
- lacks a clear statement that current practice is wrong

Then score the draft from 1 to 5 on:
- novelty
- relevance
- insight
- position_strength
- clarity

Return strict JSON only with keys:
- novelty
- relevance
- insight
- position_strength
- clarity
- passed
- reasons

Rules:
- Keep scores between 1 and 5.
- passed should be false if the draft is weak, generic, unclear, not debatable enough, or fails the pre-filter.
- reasons should contain concise fail reasons when passed is false, otherwise it may be empty.
- Use this position-strength rubric:
  1. Contrarian strength: does it clearly challenge current practice?
  2. Decisiveness: is a clear stance taken?
  3. Tension: would a strong architect debate the implication or trade-off?
  4. Specificity: is it tied to system or architecture, not generic AI?
- Reject if:
  - the position improves an existing approach instead of challenging it
  - the position can be summarized as "X is important and should be done better"
  - the position aligns with current enterprise direction
- Accept only if:
  - it reframes the problem
  - it challenges current architecture or evaluation assumptions
  - it introduces a different mental model
- Hard rules:
  - if there is no explicit "current practice is wrong" idea, position_strength must be 1
  - if the tone is neutral, position_strength must be 2 or lower
  - if there is no debate potential, position_strength must be 2 or lower
  - if the idea aligns with current enterprise trends, position_strength must be 3 or lower and insight must be 3 or lower
  - if the theme can be summarized as "X is important and should be done more", position_strength must be 2 or lower and insight must be 2 or lower
  - if the position is incremental, position_strength must be 3 or lower
  - if the position reframes the problem, position_strength must be 4 or higher

Theme:
{json.dumps(theme.as_dict(), indent=2)}

Position:
{json.dumps(position.as_dict(), indent=2)}

Position strength prior:
{json.dumps(position_strength.as_dict(), indent=2)}

Draft:
{post.body}
""".strip()
        response = self.model.invoke(prompt)
        payload = _parse_json_object(
            response.content if isinstance(response.content, str) else str(response.content)
        )

        def parse_score(key: str) -> int:
            value = int(payload[key])
            if not 1 <= value <= 5:
                raise ValueError(f"Evaluation score {key} out of range: {value}")
            return value

        novelty = parse_score("novelty")
        relevance = parse_score("relevance")
        insight = parse_score("insight")
        llm_position_strength = parse_score("position_strength")
        clarity = parse_score("clarity")
        final_position_strength = min(llm_position_strength, deterministic.position_strength)

        reasons: list[str] = []
        llm_reasons = payload.get("reasons", [])
        if isinstance(llm_reasons, list):
            reasons.extend(str(reason).strip() for reason in llm_reasons if str(reason).strip())
        if novelty < 3:
            reasons.append("Novelty below threshold.")
        if final_position_strength < 3:
            reasons.append("Position strength below threshold.")
        if post.word_count > 140:
            reasons.append("Draft exceeds target post length.")
        if not post_has_clear_wrong_statement(post.body):
            reasons.append("Draft does not clearly state what is wrong.")

        deduped_reasons = list(dict.fromkeys(reasons))
        llm_passed = _parse_bool(
            payload.get("passed", not deduped_reasons),
            default=not deduped_reasons,
        )
        return EvaluationResult(
            novelty=novelty,
            relevance=relevance,
            insight=insight,
            position_strength=final_position_strength,
            clarity=min(clarity, deterministic.clarity),
            passed=llm_passed and not deduped_reasons,
            reasons=deduped_reasons,
        )


class FallbackEvaluationEngine:
    def __init__(self, primary: EvaluationEngine, fallback: EvaluationEngine) -> None:
        self.primary = primary
        self.fallback = fallback

    def evaluate(
        self,
        *,
        theme: ThemeCandidate,
        position: Position,
        position_strength: PositionStrengthResult,
        post: PostDraft,
    ) -> EvaluationResult:
        try:
            return self.primary.evaluate(
                theme=theme,
                position=position,
                position_strength=position_strength,
                post=post,
            )
        except Exception:
            return self.fallback.evaluate(
                theme=theme,
                position=position,
                position_strength=position_strength,
                post=post,
            )


def build_default_evaluation_engine() -> EvaluationEngine:
    mode = os.getenv("DEEP_AGENTS_EVALUATION_ENGINE", "auto").strip().lower()
    deterministic = DeterministicEvaluationEngine()
    has_openai_key = bool(os.getenv("OPENAI_API_KEY"))

    if mode == "deterministic":
        return deterministic
    if mode == "openai":
        return FallbackEvaluationEngine(OpenAIEvaluationEngine(), deterministic)
    if mode == "auto" and has_openai_key:
        return FallbackEvaluationEngine(OpenAIEvaluationEngine(), deterministic)
    return deterministic
