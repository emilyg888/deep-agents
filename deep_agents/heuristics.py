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
        tension_score=4,
        specificity_score=5,
    ),
)


def _paper_text(paper: Paper) -> str:
    return f"{paper.title} {paper.abstract}".lower()


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
            rejection_reason = "Theme used in the last 3 posts."
        elif typical_architect_agrees:
            rejection_reason = "Typical architect would agree, so the debate filter rejected it."
        elif not strong_architect_debates:
            rejection_reason = "Theme lacks enough professional tension."

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
            tension_score=blueprint.tension_score,
            specificity_score=blueprint.specificity_score,
            typical_architect_agrees=typical_architect_agrees,
            strong_architect_debates=strong_architect_debates,
            rejection_reason=rejection_reason,
        )
        ranked_candidates.append((weighted_score, candidate))

    ranked_candidates.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in ranked_candidates[:max_candidates]]


def select_theme(candidates: list[ThemeCandidate]) -> tuple[ThemeCandidate, list[ThemeCandidate]]:
    accepted = [candidate for candidate in candidates if candidate.rejection_reason is None]
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
            rejected.append(
                replace(
                    candidate,
                    rejection_reason="Another theme had stronger debate and novelty scores.",
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
    reasons: list[str] = []
    if candidate.contrarian_score < 3:
        reasons.append("Contrarian score below threshold.")
    if candidate.tension_score < 3:
        reasons.append("Tension score below threshold.")
    if candidate.specificity_score < 3:
        reasons.append("Specificity score below threshold.")
    return PositionStrengthResult(
        contrarian=candidate.contrarian_score,
        tension=candidate.tension_score,
        specificity=candidate.specificity_score,
        passed=not reasons,
        reasons=reasons,
    )


def build_post(candidate: ThemeCandidate, position: Position) -> PostDraft:
    paragraphs = [
        [
            candidate.theme,
            position.common_belief,
        ],
        [
            position.contrarian_view,
            position.why_wrong,
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
    if len(words) > 180:
        body = " ".join(words[:180]).rstrip(".") + "."
        words = body.split()
    return PostDraft(hook=candidate.theme, body=body, word_count=len(words))
