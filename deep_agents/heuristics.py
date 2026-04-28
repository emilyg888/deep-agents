from __future__ import annotations

from dataclasses import dataclass, replace

from .models import Paper, Position, PositionStrengthResult, PostDraft, ThemeCandidate


@dataclass(frozen=True)
class ThemeBlueprint:
    theme: str
    keywords: tuple[str, ...]
    why_selected: str
    why_debatable: str
    common_belief: str
    contrarian_view: str
    why_wrong: str
    recommendation: str
    enterprise_implication: str
    debate_score: int
    contrarian_score: int
    decisiveness_score: int
    tension_score: int
    specificity_score: int


THEME_LIBRARY: tuple[ThemeBlueprint, ...] = (
    ThemeBlueprint(
        theme="Agents need deterministic boundaries, not more autonomy",
        keywords=("agent", "tool", "workflow", "control", "approval", "reliable"),
        why_selected="The paper pool clusters around orchestration, recovery, and human control, so governance is the real design constraint.",
        why_debatable="Typical teams still market autonomy as the breakthrough. Strong architects will argue that bounded autonomy is the only deployable version.",
        common_belief="If the model is smart enough, the agent should own more of the workflow.",
        contrarian_view="Enterprise agents create more value when they do less and hand more control back to deterministic systems.",
        why_wrong="Autonomy expands failure modes faster than most teams expand observability, approval design, and rollback safety.",
        recommendation="Design agents as bounded judgment layers wrapped by deterministic tools, explicit approvals, and recovery paths.",
        enterprise_implication="This reframes agentic AI as governed orchestration instead of demo-stage improvisation.",
        debate_score=5,
        contrarian_score=5,
        decisiveness_score=5,
        tension_score=5,
        specificity_score=5,
    ),
    ThemeBlueprint(
        theme="Retrieval quality matters less than decision framing",
        keywords=("retrieval", "rag", "search", "context", "document", "knowledge"),
        why_selected="The paper pool suggests teams keep optimizing retrieval surfaces while leaving the decision contract vague.",
        why_debatable="Typical architects often assume better retrieval fixes quality. Strong architects debate whether task framing dominates retrieval depth.",
        common_belief="RAG systems improve mostly by adding more sources, chunking tricks, and ranking upgrades.",
        contrarian_view="The highest-leverage RAG improvement is often tighter decision framing, not broader retrieval.",
        why_wrong="More context amplifies ambiguity when the model is still free to decide too many things on its own.",
        recommendation="Specify the decision, evidence bar, and allowed output shape before expanding retrieval breadth.",
        enterprise_implication="That lowers RAG complexity while making outputs easier to trust and govern.",
        debate_score=5,
        contrarian_score=5,
        decisiveness_score=4,
        tension_score=4,
        specificity_score=4,
    ),
    ThemeBlueprint(
        theme="Evaluation should be designed before scale",
        keywords=("evaluation", "benchmark", "metric", "judge", "score", "quality"),
        why_selected="The source set repeatedly points to quality measurement, rollout criteria, and governance maturity.",
        why_debatable="Teams still normalize scaling first and learning later. Strong architects argue that this locks in weak behavior.",
        common_belief="You can launch early and formalize evaluation once usage patterns settle.",
        contrarian_view="If evaluation is late, scale only accelerates confusion and institutionalizes weak model behavior.",
        why_wrong="Without explicit gates, teams mistake usage, latency, or demos for quality.",
        recommendation="Define pass-fail criteria, rejection reasons, and rollback thresholds before increasing traffic or scope.",
        enterprise_implication="That turns AI delivery from experimentation theater into a governable product discipline.",
        debate_score=4,
        contrarian_score=4,
        decisiveness_score=5,
        tension_score=4,
        specificity_score=5,
    ),
    ThemeBlueprint(
        theme="Multi-agent systems often hide weak workflow design",
        keywords=("multi-agent", "collaboration", "delegate", "planner", "worker", "coordination"),
        why_selected="The papers raise coordination patterns, but the stronger insight is that many of them exist to compensate for vague workflow design.",
        why_debatable="Teams often interpret more agents as more sophistication. Strong architects debate whether that is just operational camouflage.",
        common_belief="Complex tasks need multiple specialized agents to reach production quality.",
        contrarian_view="Many multi-agent designs are expensive compensation for missing workflow design.",
        why_wrong="Extra agents can mask unclear ownership, noisy artifacts, and absent human control points.",
        recommendation="Prove the workflow with a single bounded agent and deterministic handoffs before adding more agent roles.",
        enterprise_implication="This reduces operating cost and avoids false confidence in agentic complexity.",
        debate_score=5,
        contrarian_score=5,
        decisiveness_score=5,
        tension_score=5,
        specificity_score=4,
    ),
    ThemeBlueprint(
        theme="Enterprise memory is more governance problem than personalization feature",
        keywords=("memory", "profile", "history", "state", "personalization", "preference"),
        why_selected="Persistent context looks like a product feature, but the harder design issue is retention, auditability, and stale assumptions.",
        why_debatable="Typical architects see memory as a UX upgrade. Strong architects debate whether it is primarily a governance liability.",
        common_belief="Long-lived memory mainly improves user experience and task continuity.",
        contrarian_view="In enterprise systems, memory creates more governance burden than product differentiation unless it is tightly bounded.",
        why_wrong="Persistent context quietly accumulates stale assumptions, retention risk, and opaque model behavior.",
        recommendation="Treat memory as regulated state with expiry rules, auditability, and narrow scopes rather than as default convenience.",
        enterprise_implication="That makes memory survivable in compliance-heavy environments instead of becoming silent risk.",
        debate_score=5,
        contrarian_score=5,
        decisiveness_score=4,
        tension_score=4,
        specificity_score=5,
    ),
)


BANNED_POSITION_PATTERNS: tuple[str, ...] = (
    "on the other hand",
    "critics argue",
    "proponents suggest",
    "there is a debate",
    "it depends",
)
NEUTRAL_TONE_PATTERNS: tuple[str, ...] = (
    "may be",
    "might be",
    "could be",
    "should consider",
    "balanced approach",
    "both sides",
)
WRONG_MARKERS: tuple[str, ...] = (
    "wrong",
    "fails",
    "failure",
    "flaw",
    "broken",
    "misleading",
    "incomplete",
    "mistake",
)
CONSENSUS_TREND_PATTERNS: tuple[str, ...] = (
    "trustworthy ai",
    "trust in ai",
    "user-centric",
    "explainability",
    "responsible ai",
    "compliance",
    "transparency",
    "governance",
    "safety",
    "guardrail",
)
GENERIC_IMPORTANCE_PATTERNS: tuple[str, ...] = (
    "is important",
    "are important",
    "is essential",
    "are essential",
    "should be done more",
    "should prioritize",
    "should invest in",
    "should adopt",
    "should improve",
    "should enhance",
    "should focus on",
    "must prioritize",
    "must improve",
    "must enhance",
)
INCREMENTAL_PATTERNS: tuple[str, ...] = (
    "should improve",
    "should adopt",
    "is important",
    "enhance",
    "better approach",
)
STRUCTURAL_SHIFT_PATTERNS: tuple[str, ...] = (
    "instead of",
    "rather than",
    "before",
    "bounded",
    "deterministic",
    "handoff",
    "approval",
    "rollback",
    "gate",
    "workflow",
    "state",
    "contract",
    "expiry",
    "auditability",
    "reframe",
)
TRADEOFF_PATTERNS: tuple[str, ...] = (
    "trade-off",
    "instead of",
    "rather than",
    "before scale",
    "at the cost of",
    "reduces",
    "while reducing",
    "not more",
    "less ",
)
PROBLEM_REFRAME_PATTERNS: tuple[str, ...] = (
    "wrong problem",
    "wrong framing",
    "problem framing",
    "real problem",
    "real issue",
    "not the problem",
    "we are solving",
    "instead of solving",
    "reframe",
)
MENTAL_MODEL_PATTERNS: tuple[str, ...] = (
    "treat",
    "reframe",
    "not as",
    "rather than",
    "instead of",
    "judgment layer",
    "governed orchestration",
    "product discipline",
    "regulated state",
)


def _paper_text(paper: Paper) -> str:
    return f"{paper.title} {paper.abstract}".lower()


def _has_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(pattern in normalized for pattern in patterns)


def _has_clear_wrong_statement(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in WRONG_MARKERS)


def _position_prefilter_reasons(candidate: ThemeCandidate) -> list[str]:
    reasons: list[str] = []
    combined = " ".join(
        [
            candidate.common_belief,
            candidate.why_wrong,
            candidate.contrarian_view,
            candidate.recommendation,
            candidate.enterprise_implication,
        ]
    )
    if _has_pattern(combined, BANNED_POSITION_PATTERNS):
        reasons.append("Position used banned balanced-language patterns.")
    if _has_pattern(combined, NEUTRAL_TONE_PATTERNS):
        reasons.append("Position used neutral or academic tone.")
    if not _has_clear_wrong_statement(candidate.why_wrong):
        reasons.append("Position did not state clearly that current practice is wrong.")
    if position_is_incremental(candidate):
        reasons.append("Position is incremental instead of challenging the underlying approach.")
    if theme_aligns_with_current_enterprise_trends(candidate):
        reasons.append("Position aligns with current enterprise direction.")
    if not position_reframes_problem(candidate):
        reasons.append("Position did not reframe the problem.")
    if not position_introduces_different_mental_model(candidate):
        reasons.append("Position did not introduce a different mental model.")
    if not theme_would_make_senior_architect_uncomfortable(candidate):
        reasons.append("Position would not make a senior architect uncomfortable.")
    return reasons


def post_has_clear_wrong_statement(body: str) -> bool:
    return _has_clear_wrong_statement(body)


def _theme_text(candidate: ThemeCandidate) -> str:
    return " ".join(
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


def theme_has_structural_shift(candidate: ThemeCandidate) -> bool:
    combined = " ".join(
        [
            candidate.contrarian_view,
            candidate.recommendation,
            candidate.enterprise_implication,
        ]
    )
    return _has_pattern(combined, STRUCTURAL_SHIFT_PATTERNS)


def theme_forces_tradeoff(candidate: ThemeCandidate) -> bool:
    combined = " ".join(
        [
            candidate.common_belief,
            candidate.contrarian_view,
            candidate.why_wrong,
            candidate.recommendation,
        ]
    )
    return _has_pattern(combined, TRADEOFF_PATTERNS) or (
        theme_has_structural_shift(candidate) and _has_clear_wrong_statement(candidate.why_wrong)
    )


def theme_is_generic_importance_claim(candidate: ThemeCandidate) -> bool:
    combined = " ".join(
        [
            candidate.contrarian_view,
            candidate.recommendation,
            candidate.enterprise_implication,
        ]
    )
    return _has_pattern(combined, GENERIC_IMPORTANCE_PATTERNS) and not theme_forces_tradeoff(candidate)


def is_incremental(text: str) -> bool:
    return _has_pattern(text, INCREMENTAL_PATTERNS)


def theme_aligns_with_current_enterprise_trends(candidate: ThemeCandidate) -> bool:
    combined = _theme_text(candidate)
    return (
        _has_pattern(combined, CONSENSUS_TREND_PATTERNS)
        and not theme_has_structural_shift(candidate)
        and not theme_forces_tradeoff(candidate)
    )


def theme_would_make_senior_architect_uncomfortable(candidate: ThemeCandidate) -> bool:
    return (
        candidate.tension_score >= 4
        and candidate.contrarian_score >= 4
        and not candidate.typical_architect_agrees
    )


def theme_debate_filter_reasons(candidate: ThemeCandidate) -> list[str]:
    reasons: list[str] = []
    if candidate.debate_score < 3:
        reasons.append("Debate score below threshold.")
    if candidate.typical_architect_agrees:
        reasons.append("Theme aligns with current enterprise practice.")
    if theme_aligns_with_current_enterprise_trends(candidate):
        reasons.append("Theme aligns with current industry direction.")
    if theme_is_generic_importance_claim(candidate):
        reasons.append('Theme reduces to "X is important and should be done more."')
    if not theme_has_structural_shift(candidate):
        reasons.append("Theme does not introduce a structural shift.")
    if not theme_forces_tradeoff(candidate):
        reasons.append("Theme does not force a trade-off or rethinking.")
    if not theme_would_make_senior_architect_uncomfortable(candidate):
        reasons.append("Theme would not make a senior architect uncomfortable.")
    return list(dict.fromkeys(reasons))


def position_reframes_problem(candidate: ThemeCandidate) -> bool:
    combined = " ".join(
        [
            candidate.why_wrong,
            candidate.contrarian_view,
            candidate.recommendation,
        ]
    )
    return _has_pattern(combined, PROBLEM_REFRAME_PATTERNS) or (
        theme_has_structural_shift(candidate) and _has_clear_wrong_statement(candidate.why_wrong)
    )


def position_introduces_different_mental_model(candidate: ThemeCandidate) -> bool:
    combined = " ".join(
        [
            candidate.contrarian_view,
            candidate.recommendation,
            candidate.enterprise_implication,
        ]
    )
    return _has_pattern(combined, MENTAL_MODEL_PATTERNS) or theme_has_structural_shift(candidate)


def position_is_incremental(candidate: ThemeCandidate) -> bool:
    combined = " ".join(
        [
            candidate.contrarian_view,
            candidate.recommendation,
            candidate.enterprise_implication,
        ]
    )
    return is_incremental(combined) or theme_is_generic_importance_claim(candidate)


def build_theme_candidates(
    papers: list[Paper],
    recent_themes: list[str],
    *,
    max_candidates: int = 5,
) -> list[ThemeCandidate]:
    recent_normalized = set(recent_themes)
    ranked_candidates: list[tuple[int, ThemeCandidate]] = []

    for blueprint in THEME_LIBRARY:
        matched_papers: list[Paper] = []
        weighted_score = 0
        covered_sources: set[str] = set()
        for paper in papers:
            text = _paper_text(paper)
            matches = sum(1 for keyword in blueprint.keywords if keyword in text)
            if matches <= 0:
                continue
            matched_papers.append(paper)
            covered_sources.add(paper.source)
            weighted_score += matches + max(1, 4 - paper.tier)

        if not matched_papers:
            continue

        weighted_score += len(covered_sources)
        novelty_score = 5 if blueprint.theme.lower() not in recent_normalized else 1
        relevance_score = min(5, max(2, len(matched_papers) + len(covered_sources) - 1))
        typical_architect_agrees = blueprint.debate_score <= 2
        strong_architect_debates = blueprint.debate_score >= 4

        rejection_reason = None
        if blueprint.theme.lower() in recent_normalized:
            rejection_reason = "Theme used in the last 6 months."

        candidate = ThemeCandidate(
            theme=blueprint.theme,
            why_selected=blueprint.why_selected,
            why_debatable=blueprint.why_debatable,
            supporting_papers=matched_papers[:3],
            common_belief=blueprint.common_belief,
            contrarian_view=blueprint.contrarian_view,
            why_wrong=blueprint.why_wrong,
            recommendation=blueprint.recommendation,
            enterprise_implication=blueprint.enterprise_implication,
            novelty_score=novelty_score,
            relevance_score=relevance_score,
            debate_score=blueprint.debate_score,
            contrarian_score=blueprint.contrarian_score,
            decisiveness_score=blueprint.decisiveness_score,
            tension_score=blueprint.tension_score,
            specificity_score=blueprint.specificity_score,
            typical_architect_agrees=typical_architect_agrees,
            strong_architect_debates=strong_architect_debates,
            rejection_reason=rejection_reason,
        )
        if candidate.rejection_reason is None:
            debate_filter_reasons = theme_debate_filter_reasons(candidate)
            if debate_filter_reasons:
                candidate = replace(candidate, rejection_reason=debate_filter_reasons[0])
        ranked_candidates.append((weighted_score, candidate))

    ranked_candidates.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in ranked_candidates[:max_candidates]]


def select_theme(candidates: list[ThemeCandidate]) -> tuple[ThemeCandidate, list[ThemeCandidate]]:
    accepted = [
        candidate
        for candidate in candidates
        if candidate.rejection_reason is None and not theme_debate_filter_reasons(candidate)
    ]
    if not accepted:
        raise ValueError("No debatable theme survived novelty and debate filtering.")

    accepted.sort(
        key=lambda candidate: (
            candidate.debate_score,
            candidate.novelty_score,
            candidate.relevance_score,
            candidate.specificity_score,
        ),
        reverse=True,
    )
    selected = accepted[0]
    rejected: list[ThemeCandidate] = []
    for candidate in candidates:
        if candidate.theme == selected.theme:
            continue
        if candidate.rejection_reason is not None:
            rejected.append(candidate)
        else:
            reasons = theme_debate_filter_reasons(candidate)
            rejected.append(
                replace(
                    candidate,
                    rejection_reason=(
                        reasons[0] if reasons else "Another theme had stronger debate and novelty scores."
                    ),
                )
            )
    return selected, rejected


def build_position(candidate: ThemeCandidate) -> Position:
    return Position(
        common_belief=candidate.common_belief,
        contrarian_view=candidate.contrarian_view,
        why_wrong=candidate.why_wrong,
        recommendation=candidate.recommendation,
        enterprise_implication=candidate.enterprise_implication,
    )


def assess_position_strength(candidate: ThemeCandidate) -> PositionStrengthResult:
    reasons = _position_prefilter_reasons(candidate)
    contrarian = candidate.contrarian_score
    decisiveness = candidate.decisiveness_score
    tension = candidate.tension_score
    specificity = candidate.specificity_score

    if not _has_clear_wrong_statement(candidate.why_wrong):
        contrarian = min(contrarian, 1)
        decisiveness = min(decisiveness, 1)
    if position_is_incremental(candidate):
        contrarian = min(contrarian, 3)
        tension = min(tension, 3)
        specificity = min(specificity, 3)
    if theme_aligns_with_current_enterprise_trends(candidate):
        contrarian = min(contrarian, 3)
        tension = min(tension, 2)
    if _has_pattern(
        " ".join([candidate.why_wrong, candidate.contrarian_view, candidate.recommendation]),
        NEUTRAL_TONE_PATTERNS,
    ):
        decisiveness = min(decisiveness, 2)
        tension = min(tension, 2)
    if _has_pattern(
        " ".join([candidate.why_debatable, candidate.contrarian_view]),
        BANNED_POSITION_PATTERNS,
    ):
        decisiveness = min(decisiveness, 1)
        tension = min(tension, 2)
    if position_reframes_problem(candidate):
        contrarian = max(contrarian, 4)
        decisiveness = max(decisiveness, 4)
        tension = max(tension, 4)
    if not position_reframes_problem(candidate):
        contrarian = min(contrarian, 3)
        tension = min(tension, 3)
    if not position_introduces_different_mental_model(candidate):
        tension = min(tension, 3)
        specificity = min(specificity, 3)

    if contrarian < 3:
        reasons.append("Contrarian score below threshold.")
    if decisiveness < 3:
        reasons.append("Decisiveness score below threshold.")
    if tension < 3:
        reasons.append("Tension score below threshold.")
    if specificity < 3:
        reasons.append("Specificity score below threshold.")
    return PositionStrengthResult(
        contrarian=contrarian,
        decisiveness=decisiveness,
        tension=tension,
        specificity=specificity,
        passed=not reasons and contrarian >= 3 and decisiveness >= 3 and tension >= 3 and specificity >= 3,
        reasons=reasons,
    )


def build_post(candidate: ThemeCandidate, position: Position) -> PostDraft:
    paragraphs = [
        [
            candidate.theme,
            f"Most enterprises still operate as if {position.common_belief.rstrip('.').lower()}.",
        ],
        [
            f"That is wrong because {position.why_wrong.rstrip('.').lower()}.",
            position.contrarian_view,
        ],
        [
            position.recommendation,
            position.enterprise_implication,
        ],
    ]
    body = "\n\n".join(
        " ".join(
            sentence.strip().rstrip(".") + "."
            for sentence in paragraph
            if sentence.strip()
        )
        for paragraph in paragraphs
    )
    words = body.split()
    if len(words) > 140:
        body = " ".join(words[:140]).rstrip(".") + "."
        words = body.split()
    return PostDraft(hook=candidate.theme, body=body, word_count=len(words))
