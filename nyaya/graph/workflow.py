"""The requirements-engineering workflow.

A state graph, not a swarm. Execution order is explicit, every transition is
checkpointed, and the human-approval gates are `interrupt` points that suspend
the run durably rather than prompting inline.

That choice is the whole reason LangGraph was selected over an autonomous
multi-agent framework: in a regulated workflow, agent-to-agent negotiation is a
liability. What is wanted is a machine whose next step can be predicted, whose
history can be replayed, and which cannot proceed past a checkpoint that a named
human has not cleared.

    ingest -> extract -> [gate: requirement_baseline]
           -> map_compliance -> [gate: regulatory_interpretation]
           -> assess_coverage -> [gate: compliance_gap]
           -> recommend_sdlc -> [gate: sdlc_selection] -> persist
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from nyaya.agents.compliance import map_requirement
from nyaya.agents.extraction import extract
from nyaya.agents.schemas import ExtractionContext
from nyaya.core.enums import RiskLevel
from nyaya.db import session_scope
from nyaya.graph.gates import payload
from nyaya.graph.state import WorkflowState
from nyaya.mcda.sdlc import default_factors, recommend
from nyaya.rules.engine import evaluate, requirement_facts

# Risk levels at which a requirement additionally needs security sign-off.
_ELEVATED = {RiskLevel.HIGH, RiskLevel.CRITICAL}


async def node_extract(state: WorkflowState) -> dict[str, Any]:
    """Turn source text into structured, quality-checked requirements."""
    result = await extract(
        state["source_text"],
        context=ExtractionContext(
            domain=state.get("domain", "ekyc_onboarding"),
            jurisdictions=state.get("jurisdictions", ["IN"]),
        ),
    )
    return {"requirements": result.requirements, "unclear": result.unclear}


def node_baseline_gate(state: WorkflowState) -> dict[str, Any]:
    """Suspend until a human approves the requirement baseline.

    Everything downstream derives from this set, so an error admitted here
    propagates silently through compliance mapping and traceability.
    """
    requirements = state.get("requirements", [])
    untestable = [r for r in requirements if not r.is_testable]
    elevated = [r for r in requirements if r.requirement.risk_level in _ELEVATED]

    decision = interrupt(
        payload(
            "requirement_baseline",
            {
                "requirement_count": len(requirements),
                "untestable_count": len(untestable),
                "elevated_risk_count": len(elevated),
                "open_questions": state.get("unclear", []),
                "statements": [r.requirement.statement for r in requirements],
                "defects": [
                    {"statement": r.requirement.statement, "detail": d.detail}
                    for r in untestable
                    for d in r.defects
                ],
            },
        )
    )
    return _record(decision, "requirement_baseline")


async def node_map_compliance(state: WorkflowState) -> dict[str, Any]:
    """Map each approved requirement to the controls it satisfies."""
    if state.get("halted"):
        return {}

    results = []
    async with session_scope() as session:
        for item in state.get("requirements", []):
            results.append(
                await map_requirement(
                    session,
                    item.requirement,
                    domain=state.get("domain", "ekyc_onboarding"),
                    jurisdictions=state.get("jurisdictions", ["IN"]),
                )
            )
    return {"compliance": results}


def node_interpretation_gate(state: WorkflowState) -> dict[str, Any]:
    """Suspend for compliance sign-off on the mappings and their citations.

    Only mappings the validator could not auto-confirm are surfaced for
    decision; the confirmed ones are listed for completeness. That distinction
    is the point of the tiered validator - it decides where human attention
    goes, not whether it is needed.
    """
    results = state.get("compliance", [])
    for_review = [
        {
            "requirement": r.requirement_statement,
            "control": m.control_id,
            "citation": m.citation_key,
            "tier": m.tier.value,
            "why": m.review_reasons,
            "note": m.review_note,
        }
        for r in results
        for m in r.needs_review
    ]
    conflicts = [c for r in results for c in r.conflicts]

    decision = interrupt(
        payload(
            "regulatory_interpretation",
            {
                "auto_confirmed": sum(len(r.confirmed) for r in results),
                "needs_review": for_review,
                "rejected": [
                    {"citation": m.citation_key, "why": m.rejections}
                    for r in results
                    for m in r.rejected
                ],
                "conflicts": conflicts,
            },
        )
    )
    return _record(decision, "regulatory_interpretation")


def node_assess_coverage(state: WorkflowState) -> dict[str, Any]:
    """Determine which mandatory controls no requirement covers."""
    if state.get("halted"):
        return {}

    facts = [
        (
            item.requirement.statement[:64],
            requirement_facts(
                statement=item.requirement.statement,
                categories=[c.value for c in item.requirement.categories],
                risk_level=item.requirement.risk_level.value,
                jurisdictions=state.get("jurisdictions", ["IN"]),
                domain=state.get("domain", "ekyc_onboarding"),
            ),
        )
        for item in state.get("requirements", [])
    ]
    reports = evaluate(
        facts,
        domain=state.get("domain", "ekyc_onboarding"),
        jurisdictions=state.get("jurisdictions", ["IN"]),
    )
    return {"coverage": reports}


def node_gap_gate(state: WorkflowState) -> dict[str, Any]:
    """Suspend on uncovered mandatory controls."""
    reports = state.get("coverage", [])
    decision = interrupt(
        payload(
            "compliance_gap",
            {
                "coverage": [
                    {
                        "pack": r.pack,
                        "ratio": round(r.coverage_ratio, 3),
                        "gaps": r.explain_gaps(),
                        "blocking_gaps": [g.control_id for g in r.blocking_gaps],
                    }
                    for r in reports
                ],
            },
        )
    )
    return _record(decision, "compliance_gap")


def node_recommend_sdlc(state: WorkflowState) -> dict[str, Any]:
    """Rank lifecycle models against the project's derived characteristics."""
    if state.get("halted"):
        return {}
    return {"sdlc": recommend(_derive_factors(state))}


def node_sdlc_gate(state: WorkflowState) -> dict[str, Any]:
    """Suspend for approval of the lifecycle recommendation."""
    recommendation = state.get("sdlc")
    decision = interrupt(
        payload(
            "sdlc_selection",
            {
                "ranked": recommendation.ranked() if recommendation else [],
                "close_call": recommendation.close_call if recommendation else False,
                "notes": recommendation.notes if recommendation else [],
                "consistency_ratio": (
                    round(recommendation.weights.consistency_ratio, 4)
                    if recommendation
                    else None
                ),
                "explanation": (
                    recommendation.ranking.explain() if recommendation else []
                ),
            },
        )
    )
    return _record(decision, "sdlc_selection")


def _derive_factors(state: WorkflowState) -> dict[str, float]:
    """Derive SDLC decision factors from what the pipeline actually found.

    Deliberately derived, not asked for. A factor vector supplied by hand is a
    conclusion dressed as an input; deriving it from the requirement set means
    the recommendation is traceable to evidence like everything else here.
    """
    requirements = state.get("requirements", [])
    total = max(len(requirements), 1)

    regulatory = sum(
        1 for r in requirements if any(c.value == "regulatory" for c in r.requirement.categories)
    ) / total
    security = sum(
        1 for r in requirements if any(c.value == "security" for c in r.requirement.categories)
    ) / total
    elevated = sum(1 for r in requirements if r.requirement.risk_level in _ELEVATED) / total
    # Open questions signal requirements that are not yet settled.
    unsettled = min(len(state.get("unclear", [])) / (total * 2), 1.0)

    return default_factors(
        regulatory_criticality=max(regulatory, 0.5),
        security_risk=max(security, 0.4),
        failure_consequence=max(elevated, 0.4),
        requirement_stability=1.0 - unsettled,
        change_frequency=unsettled,
        formal_verification_need=max(elevated, 0.3),
    )


def _record(decision: Any, gate: str) -> dict[str, Any]:
    """Normalise a resumed decision into state.

    A rejection halts the run rather than being noted and ignored: a gate whose
    refusal does not stop anything is not a gate.
    """
    if not isinstance(decision, dict):
        decision = {"decision": str(decision)}

    entry = {
        "gate": gate,
        "decision": decision.get("decision", "approve"),
        "actor": decision.get("actor", "unknown"),
        "comment": decision.get("comment", ""),
        "at": datetime.now(UTC).isoformat(),
    }
    update: dict[str, Any] = {"decisions": [entry]}
    if entry["decision"] == "reject":
        update["halted"] = True
        update["halt_reason"] = f"{gate} rejected by {entry['actor']}: {entry['comment']}"
    return update


def build_graph(checkpointer: Any | None = None):
    """Assemble the workflow.

    A checkpointer is what makes the gates durable: without one an interrupt is
    a pause in a process, and with one it is a suspended run that survives
    restarts and can be resumed by a different person days later.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("extract", node_extract)
    graph.add_node("baseline_gate", node_baseline_gate)
    graph.add_node("map_compliance", node_map_compliance)
    graph.add_node("interpretation_gate", node_interpretation_gate)
    graph.add_node("assess_coverage", node_assess_coverage)
    graph.add_node("gap_gate", node_gap_gate)
    graph.add_node("recommend_sdlc", node_recommend_sdlc)
    graph.add_node("sdlc_gate", node_sdlc_gate)

    graph.add_edge(START, "extract")
    graph.add_edge("extract", "baseline_gate")
    graph.add_conditional_edges(
        "baseline_gate", _continue_or_halt,
        {"continue": "map_compliance", "halt": END},
    )
    graph.add_edge("map_compliance", "interpretation_gate")
    graph.add_conditional_edges(
        "interpretation_gate", _continue_or_halt,
        {"continue": "assess_coverage", "halt": END},
    )
    graph.add_edge("assess_coverage", "gap_gate")
    graph.add_conditional_edges(
        "gap_gate", _continue_or_halt,
        {"continue": "recommend_sdlc", "halt": END},
    )
    graph.add_edge("recommend_sdlc", "sdlc_gate")
    graph.add_edge("sdlc_gate", END)

    return graph.compile(checkpointer=checkpointer)


def _continue_or_halt(state: WorkflowState) -> str:
    return "halt" if state.get("halted") else "continue"


__all__ = ["build_graph", "node_extract", "node_recommend_sdlc"]
