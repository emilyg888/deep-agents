from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from typing import Protocol

from langchain_openai import ChatOpenAI

from .heuristics import (
    assess_position_strength,
    build_position,
    build_post,
    build_theme_candidates,
    post_has_clear_wrong_statement,
    select_theme,
    theme_debate_filter_reasons,
    theme_would_make_senior_architect_uncomfortable,
)
from .models import (
    Paper,
    Position,
    PositionStrengthResult,
    PostDraft,
    SynthesisProvenance,
    ThemeCandidate,
)


@dataclass(frozen=True)
class SynthesisResult:
    selected_theme: ThemeCandidate
    alternative_themes: list[ThemeCandidate]
    rejected_themes: list[ThemeCandidate]
    position: Position
    position_strength: PositionStrengthResult
    post: PostDraft
    provenance: SynthesisProvenance


class SynthesisEngine(Protocol):
    def synthesize(self, papers: list[Paper], recent_themes: list[str]) -> SynthesisResult:
        ...


class DeterministicSynthesisEngine:
    def synthesize(self, papers: list[Paper], recent_themes: list[str]) -> SynthesisResult:
        candidates = build_theme_candidates(papers, recent_themes)
        if not candidates:
            raise ValueError("Could not extract any viable themes from the paper pool.")

        selected, alternatives, rejected = select_theme(candidates)
        position = build_position(selected)
        position_strength = assess_position_strength(selected)
        post = build_post(selected, position)
        return SynthesisResult(
            selected_theme=selected,
            alternative_themes=alternatives,
            rejected_themes=rejected,
            position=position,
            position_strength=position_strength,
            post=post,
            provenance=SynthesisProvenance(engine_used="deterministic"),
        )


def _parse_json_object(text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1]
        candidate = candidate.rsplit("```", 1)[0]
    return json.loads(candidate)


def _parse_bool(value: object, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    raise ValueError(f"Candidate field {field_name} must be a boolean.")


def _parse_score(value: object, *, field_name: str) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Candidate score {field_name} must be numeric.") from exc
    # Clamp to the repo's 1..5 scale so minor schema drift does not force
    # a full fallback to deterministic blueprint output.
    return max(1, min(5, round(numeric)))


def _selection_sort_key(candidate: ThemeCandidate) -> tuple[int, int, int, int, int, int, int]:
    return (
        candidate.debate_score,
        candidate.relevance_score,
        candidate.novelty_score,
        candidate.specificity_score,
        candidate.contrarian_score,
        candidate.decisiveness_score,
        candidate.tension_score,
    )


class ThemeGenerationRejected(ValueError):
    """Raised when the LLM returns themes, but none pass deterministic gates."""


def _candidate_rejection_report(candidates: list[ThemeCandidate]) -> str:
    if not candidates:
        return "No candidate themes returned."
    lines: list[str] = []
    for candidate in candidates:
        reasons = theme_debate_filter_reasons(candidate)
        if candidate.rejection_reason:
            reasons.insert(0, candidate.rejection_reason)
        reason_text = "; ".join(dict.fromkeys(reasons)) or "accepted"
        lines.append(f"- {candidate.theme}: {reason_text}")
    return "\n".join(lines)


def _theme_selection_score(candidate: ThemeCandidate) -> int:
    return (
        4 * candidate.debate_score
        + 3 * candidate.relevance_score
        + 2 * candidate.novelty_score
        + candidate.specificity_score
        + (2 if theme_would_make_senior_architect_uncomfortable(candidate) else 0)
    )


def _engine_name(engine: object) -> str:
    if isinstance(engine, OpenAISynthesisEngine):
        return "openai"
    if isinstance(engine, DeterministicSynthesisEngine):
        return "deterministic"
    return engine.__class__.__name__


THEME_ELEVATION_GUIDANCE = """
Abstraction guidance:
- Focus on shifts in thinking, not paper topics.
- Prefer themes in the form: "Shift from X to Y" or "We are solving X, but the real issue is Y".

Bad theme examples:
- "Clinical AI evaluation methods"
- "Explainable AI and user trust"
- "RAG retrieval quality"

Good theme examples:
- "Shift from model-centric evaluation to system-behavior evaluation"
- "Explainability is solving the wrong problem; control matters more than explanation"
- "Retrieval is compensating for missing system structure"
""".strip()


class OpenAISynthesisEngine:
    def __init__(self, *, model: str | None = None, temperature: float = 0.1) -> None:
        self.model = ChatOpenAI(
            model=model or os.getenv("DEEP_AGENTS_OPENAI_MODEL", "gpt-4o-mini"),
            temperature=temperature,
        )
        self.max_position_attempts = max(
            1,
            int(os.getenv("DEEP_AGENTS_POSITION_ATTEMPTS", "3")),
        )
        self.max_post_attempts = max(
            1,
            int(os.getenv("DEEP_AGENTS_POST_ATTEMPTS", "3")),
        )
        self.max_theme_attempts = max(
            1,
            int(os.getenv("DEEP_AGENTS_THEME_ATTEMPTS", "3")),
        )

    def synthesize(self, papers: list[Paper], recent_themes: list[str]) -> SynthesisResult:
        paper_context = [
            {
                "title": paper.title,
                "source": paper.source,
                "abstract": paper.abstract,
                "url": paper.url,
                "published_on": paper.published_on.isoformat(),
                "tier": paper.tier,
            }
            for paper in papers[:8]
        ]
        parsed_candidates = self._generate_theme_candidates_with_retries(
            papers,
            paper_context,
            recent_themes,
        )
        selected, alternatives, rejected = self._resolve_theme_selection(
            parsed_candidates,
            paper_context,
        )
        selected, position_strength = self._build_position_with_retries(
            selected,
            paper_context,
        )
        position = build_position(selected)
        post = self._build_post_with_retries(selected, paper_context)
        return SynthesisResult(
            selected_theme=selected,
            alternative_themes=alternatives,
            rejected_themes=rejected,
            position=position,
            position_strength=position_strength,
            post=post,
            provenance=SynthesisProvenance(engine_used="openai"),
        )

    def _generate_theme_candidates_with_retries(
        self,
        papers: list[Paper],
        paper_context: list[dict[str, object]],
        recent_themes: list[str],
    ) -> list[ThemeCandidate]:
        feedback: list[str] = []
        last_error: ValueError | None = None
        for attempt in range(1, self.max_theme_attempts + 1):
            try:
                candidates = self._generate_theme_candidates(
                    papers,
                    paper_context,
                    recent_themes,
                    feedback=feedback,
                    attempt=attempt,
                )
            except ValueError as exc:
                feedback = [
                    str(exc),
                    "If the topic is narrow, return fewer themes instead of weak filler themes.",
                    "Elevate the themes to paradigm-level insights. Focus on shifts in thinking, not topics. Use the form: 'Shift from X to Y'.",
                ]
                last_error = exc
                continue
            if not candidates:
                feedback = [
                    "No usable themes were returned.",
                    "Extract broader patterns across the papers, but do not invent filler themes.",
                    "Elevate the themes to paradigm-level insights. Focus on shifts in thinking, not topics. Use the form: 'Shift from X to Y'.",
                ]
                last_error = ValueError("No usable themes.")
                continue
            if candidates:
                return candidates
            rejection_report = _candidate_rejection_report(candidates)
            if len(candidates) < 2:
                feedback = [
                    "No paradigm-level themes survived and too few themes were returned.",
                    "Extract broader patterns across the papers, but keep the themes paradigm-level.",
                    "Elevate the themes to paradigm-level insights. Focus on shifts in thinking, not topics. Use the form: 'Shift from X to Y'.",
                ]
            else:
                feedback = [
                    "No themes survived the deterministic filter.",
                    "At least one theme must challenge current practice enough to create debate, introduce a structural shift, problem reframe, or different mental model, and avoid generic importance claims.",
                    "Elevate the themes to paradigm-level insights. Focus on shifts in thinking, not topics. Use the form: 'Shift from X to Y'.",
                ]
            last_error = ThemeGenerationRejected(
                "No paradigm-level themes survived deterministic filtering.\n"
                f"{rejection_report}"
            )
        if last_error is not None:
            raise last_error
        raise ValueError("Theme generation rejected.")

    def _generate_theme_candidates(
        self,
        papers: list[Paper],
        paper_context: list[dict[str, object]],
        recent_themes: list[str],
        *,
        feedback: list[str],
        attempt: int,
    ) -> list[ThemeCandidate]:
        revision_feedback = ""
        if feedback:
            revision_feedback = f"""
Previous attempt failed for these reasons:
{json.dumps(feedback, indent=2)}

Revise the theme list to fix every listed failure. Output only corrected JSON.
""".strip()
        prompt = f"""
You are a senior enterprise AI architect.

Given these papers:
- identify UP TO 5 themes
- classify each theme as either:
  A) Incremental improvement
     - improves current practice
     - makes systems better
     - aligns with industry direction
  B) Paradigm challenge
     - questions the underlying approach
     - reframes the problem
     - creates real architectural debate

Reject all Incremental themes.
Do NOT select a winner in code terms. Code will do the final selection.

Return strict JSON only with keys:
- themes

Each themes item must contain:
- theme
- why_selected
- why_debatable
- common_belief
- contrarian_view
- why_wrong
- recommendation
- enterprise_implication
- novelty_score
- enterprise_relevance_score
- debate_score
- contrarian_score
- decisiveness_score
- tension_score
- specificity_score
- typical_architect_agrees
- strong_architect_debates
- rejection_reason
- supporting_paper_urls

Rules:
- Produce between 1 and 5 themes when meaningful.
- It is acceptable to return fewer themes if only a small number are meaningful.
- Do NOT invent weak or filler themes to meet a quota.
- rejection_reason is optional metadata. Code will not use it for final selection.
- It is acceptable if your theme list is not fully self-consistent; code will enforce invariants downstream.
- All score fields must be integers on a 1 to 5 scale.
- Boolean fields must be JSON booleans when possible.
- supporting_paper_urls must reference the supplied papers exactly by URL.
- Return JSON only. No markdown.
- Reject the theme if it is only a generic importance claim, for example: "X is important and should be improved."
- Reject the theme if it is regulator-consistent but has no architectural consequence.
- Select themes that challenge current practice enough to create debate, introduce a structural shift, problem reframe, or different mental model.
- Architectural discomfort is useful but not mandatory. If a strong architect may agree but would still debate the implementation trade-off, keep the theme and set strong_architect_debates=true.
- Reject any theme that can be summarized as: "X is important and should be done more."
- For paradigm themes, why_debatable must explain why the theme is a paradigm challenge.
- For rejected themes, rejection_reason must explicitly label the theme as incremental or weak.
- If the topic is narrow, it is better to return 1 or 2 strong paradigm themes than weak filler themes.

{THEME_ELEVATION_GUIDANCE}

Recent themes:
{json.dumps(recent_themes, indent=2)}

Paper pool:
{json.dumps(paper_context, indent=2)}

Attempt: {attempt} of {self.max_theme_attempts}
{revision_feedback}
""".strip()
        response = self.model.invoke(prompt)
        payload = _parse_json_object(
            response.content if isinstance(response.content, str) else str(response.content)
        )

        raw_candidates = payload.get("themes", payload.get("candidate_themes", []))
        if not isinstance(raw_candidates, list):
            raise ValueError("LLM did not return a theme list.")
        if len(raw_candidates) == 0:
            raise ValueError("No usable themes.")
        if len(raw_candidates) > 5:
            raise ValueError("LLM returned too many themes.")

        paper_lookup = {paper.url: paper for paper in papers}
        parsed_candidates: list[ThemeCandidate] = []
        for raw_candidate in raw_candidates:
            if not isinstance(raw_candidate, dict):
                raise ValueError("LLM candidate theme payload was not an object.")
            supporting_urls = raw_candidate.get("supporting_paper_urls", [])
            if not isinstance(supporting_urls, list) or not supporting_urls:
                raise ValueError("Each candidate theme must include supporting_paper_urls.")
            supporting_papers = [
                paper_lookup[url]
                for url in supporting_urls
                if isinstance(url, str) and url in paper_lookup
            ]
            if not supporting_papers:
                raise ValueError("Candidate theme referenced unknown supporting papers.")
            parsed_candidates.append(
                ThemeCandidate(
                    theme=str(raw_candidate["theme"]).strip(),
                    why_selected=str(raw_candidate["why_selected"]).strip(),
                    why_debatable=str(raw_candidate["why_debatable"]).strip(),
                    supporting_papers=supporting_papers[:3],
                    common_belief=str(raw_candidate["common_belief"]).strip(),
                    contrarian_view=str(raw_candidate["contrarian_view"]).strip(),
                    why_wrong=str(raw_candidate["why_wrong"]).strip(),
                    recommendation=str(raw_candidate["recommendation"]).strip(),
                    enterprise_implication=str(raw_candidate["enterprise_implication"]).strip(),
                    novelty_score=_parse_score(
                        raw_candidate.get("novelty_score"),
                        field_name="novelty_score",
                    ),
                    relevance_score=_parse_score(
                        raw_candidate.get(
                            "enterprise_relevance_score",
                            raw_candidate.get("relevance_score"),
                        ),
                        field_name="enterprise_relevance_score",
                    ),
                    debate_score=_parse_score(
                        raw_candidate.get("debate_score"),
                        field_name="debate_score",
                    ),
                    contrarian_score=_parse_score(
                        raw_candidate.get("contrarian_score"),
                        field_name="contrarian_score",
                    ),
                    decisiveness_score=_parse_score(
                        raw_candidate.get("decisiveness_score"),
                        field_name="decisiveness_score",
                    ),
                    tension_score=_parse_score(
                        raw_candidate.get("tension_score"),
                        field_name="tension_score",
                    ),
                    specificity_score=_parse_score(
                        raw_candidate.get("specificity_score"),
                        field_name="specificity_score",
                    ),
                    typical_architect_agrees=_parse_bool(
                        raw_candidate["typical_architect_agrees"],
                        field_name="typical_architect_agrees",
                    ),
                    strong_architect_debates=_parse_bool(
                        raw_candidate["strong_architect_debates"],
                        field_name="strong_architect_debates",
                    ),
                    rejection_reason=(
                        str(raw_candidate["rejection_reason"]).strip()
                        if raw_candidate.get("rejection_reason") is not None
                        else None
                    ),
                )
            )
        return parsed_candidates

    def _resolve_theme_selection(
        self,
        candidates: list[ThemeCandidate],
        paper_context: list[dict[str, object]],
    ) -> tuple[ThemeCandidate, list[ThemeCandidate], list[ThemeCandidate]]:
        del paper_context
        eligible = [
            replace(candidate, rejection_reason=None)
            for candidate in candidates
            if candidate.relevance_score >= 3
        ]
        if not eligible:
            raise ValueError("No enterprise-relevant theme was available for ranking.")

        ranked = [
            replace(candidate, rejection_reason=None)
            for candidate in eligible
        ]
        selected = sorted(
            ranked,
            key=lambda candidate: (_theme_selection_score(candidate), _selection_sort_key(candidate)),
            reverse=True,
        )[0]
        selected = replace(selected, rejection_reason=None)
        alternatives = [
            replace(candidate, rejection_reason=None)
            for candidate in ranked
            if candidate.theme != selected.theme
        ]
        rejected = [
            replace(candidate, rejection_reason="Enterprise relevance below threshold.")
            for candidate in candidates
            if candidate.relevance_score < 3
        ]
        return selected, alternatives, rejected

    def _build_position_with_retries(
        self,
        candidate: ThemeCandidate,
        paper_context: list[dict[str, object]],
    ) -> tuple[ThemeCandidate, PositionStrengthResult]:
        feedback: list[str] = []
        last_error: ValueError | None = None
        current = candidate
        last_strength = assess_position_strength(current)
        for attempt in range(1, self.max_position_attempts + 1):
            try:
                current = self._build_position(
                    current,
                    paper_context,
                    feedback=feedback,
                    attempt=attempt,
                )
            except Exception as exc:
                feedback = [str(exc)]
                last_error = ValueError(str(exc))
                continue
            position_strength = assess_position_strength(current)
            last_strength = position_strength
            if position_strength.passed:
                return current, position_strength
            feedback = position_strength.reasons
            last_error = ValueError("; ".join(position_strength.reasons))
        return current, last_strength

    def _build_position(
        self,
        candidate: ThemeCandidate,
        paper_context: list[dict[str, object]],
        *,
        feedback: list[str],
        attempt: int,
    ) -> ThemeCandidate:
        revision_feedback = ""
        if feedback:
            revision_feedback = f"""
Previous attempt failed for these reasons:
{json.dumps(feedback, indent=2)}

Revise the position to fix every listed failure. Do not explain the revisions. Output only the corrected position JSON.
""".strip()
        prompt = f"""
You are a senior enterprise AI architect.

Given this theme:
{json.dumps(candidate.as_dict(), indent=2)}

Supporting paper pool:
{json.dumps(paper_context, indent=2)}

Step 1:
State what most enterprises believe.

Step 2:
Explain why this is the WRONG problem framing.

Step 3:
Reframe the problem:
- What is the real issue?

Step 4:
State the correct architectural approach.

Hard rules:
- You MUST pick a side.
- You MUST state what is wrong with current practice.
- You MUST say what problem is being solved incorrectly.
- You MUST reframe the problem, not just improve the solution.
- Do NOT propose incremental fixes.
- Do NOT present both sides.
- Do NOT use balanced language.
- Do NOT say "it depends".
- The why_wrong field must explicitly say current practice is wrong, incomplete, misleading, broken, or a mistake.

Banned patterns:
- on the other hand
- critics argue
- proponents suggest
- there is a debate

Attempt: {attempt} of {self.max_position_attempts}
{revision_feedback}

Return strict JSON only with keys:
- common_belief
- why_wrong
- contrarian_view
- recommendation
- enterprise_implication
- contrarian_score
- decisiveness_score
- tension_score
- specificity_score

Interpretation:
- contrarian_view = the reframed problem / real issue
- recommendation = the correct architectural approach
""".strip()
        response = self.model.invoke(prompt)
        payload = _parse_json_object(
            response.content if isinstance(response.content, str) else str(response.content)
        )
        return replace(
            candidate,
            common_belief=str(payload["common_belief"]).strip(),
            why_wrong=str(payload["why_wrong"]).strip(),
            contrarian_view=str(payload["contrarian_view"]).strip(),
            recommendation=str(payload["recommendation"]).strip(),
            enterprise_implication=str(payload["enterprise_implication"]).strip(),
            contrarian_score=_parse_score(payload.get("contrarian_score"), field_name="contrarian_score"),
            decisiveness_score=_parse_score(payload.get("decisiveness_score"), field_name="decisiveness_score"),
            tension_score=_parse_score(payload.get("tension_score"), field_name="tension_score"),
            specificity_score=_parse_score(payload.get("specificity_score"), field_name="specificity_score"),
        )

    def _build_post_with_retries(
        self,
        candidate: ThemeCandidate,
        paper_context: list[dict[str, object]],
    ) -> PostDraft:
        feedback: list[str] = []
        last_error: ValueError | None = None
        for attempt in range(1, self.max_post_attempts + 1):
            try:
                return self._build_post(
                    candidate,
                    paper_context,
                    feedback=feedback,
                    attempt=attempt,
                )
            except Exception as exc:
                feedback = [str(exc)]
                last_error = ValueError(str(exc))
        return build_post(candidate, build_position(candidate))

    def _build_post(
        self,
        candidate: ThemeCandidate,
        paper_context: list[dict[str, object]],
        *,
        feedback: list[str],
        attempt: int,
    ) -> PostDraft:
        revision_feedback = ""
        if feedback:
            revision_feedback = f"""
Previous attempt failed for these reasons:
{json.dumps(feedback, indent=2)}

Revise the post to fix every listed failure. Do not explain the revisions. Output only the corrected post JSON.
""".strip()
        prompt = f"""
Write a LinkedIn post (max 140 words).

Theme:
{candidate.theme}

Position:
{json.dumps(build_position(candidate).as_dict(), indent=2)}

Supporting paper pool:
{json.dumps(paper_context, indent=2)}

Requirements:
- Start with a strong claim
- Clearly state what enterprises are doing wrong
- Present one contrarian insight
- Tie to system or architecture impact

Hard rules:
- No explanation tone
- No academic language
- No balanced arguments
- No "should consider"
- The post must contain a clear statement that something is wrong
- Use the word "wrong", "broken", "failure", "flaw", "misleading", or "mistake" at least once

Tone:
- Direct
- Opinionated
- Architect-level

Attempt: {attempt} of {self.max_post_attempts}
{revision_feedback}

Return strict JSON only with keys:
- post_paragraphs
""".strip()
        response = self.model.invoke(prompt)
        payload = _parse_json_object(
            response.content if isinstance(response.content, str) else str(response.content)
        )
        paragraphs = payload.get("post_paragraphs", [])
        if not isinstance(paragraphs, list) or not paragraphs:
            raise ValueError("LLM did not return post_paragraphs.")
        post_body = "\n\n".join(str(paragraph).strip() for paragraph in paragraphs if str(paragraph).strip())
        word_count = len(post_body.split())
        if word_count > 140:
            raise ValueError("LLM post exceeded 140 words.")
        if not post_has_clear_wrong_statement(post_body):
            raise ValueError("LLM post did not contain a clear statement that something is wrong.")
        return PostDraft(
            hook=candidate.theme,
            body=post_body,
            word_count=word_count,
        )


class FallbackSynthesisEngine:
    def __init__(self, primary: SynthesisEngine, fallback: SynthesisEngine) -> None:
        self.primary = primary
        self.fallback = fallback

    def synthesize(self, papers: list[Paper], recent_themes: list[str]) -> SynthesisResult:
        try:
            return self.primary.synthesize(papers, recent_themes)
        except ThemeGenerationRejected as exc:
            fallback_result = self.fallback.synthesize(papers, recent_themes)
            return replace(
                fallback_result,
                provenance=SynthesisProvenance(
                    engine_used=_engine_name(self.fallback),
                    fallback_used=True,
                    primary_engine=_engine_name(self.primary),
                    fallback_reason=str(exc),
                ),
            )
        except ValueError:
            raise
        except Exception as exc:
            fallback_result = self.fallback.synthesize(papers, recent_themes)
            return replace(
                fallback_result,
                provenance=SynthesisProvenance(
                    engine_used=_engine_name(self.fallback),
                    fallback_used=True,
                    primary_engine=_engine_name(self.primary),
                    fallback_reason=f"{type(exc).__name__}: {exc}",
                ),
            )


def build_default_synthesis_engine() -> SynthesisEngine:
    mode = os.getenv("DEEP_AGENTS_SYNTHESIS_ENGINE", "auto").strip().lower()
    deterministic = DeterministicSynthesisEngine()
    has_openai_key = bool(os.getenv("OPENAI_API_KEY"))

    if mode == "deterministic":
        return deterministic
    if mode == "openai":
        return FallbackSynthesisEngine(OpenAISynthesisEngine(), deterministic)
    if mode == "auto" and has_openai_key:
        return FallbackSynthesisEngine(OpenAISynthesisEngine(), deterministic)
    return deterministic
