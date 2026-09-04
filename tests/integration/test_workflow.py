"""The workflow's gate behaviour.

The claim under test is the one the whole human-in-the-loop design rests on:
that the run **cannot proceed** past an approval gate without a recorded human
decision, and that a rejection stops it rather than being noted and ignored.

Agent nodes are replaced with fakes, because what is being tested is the
control flow, not the agents - those are measured in `nyaya.eval`.
"""

from __future__ import annotations

import uuid

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from nyaya.agents.extraction import AnalysedRequirement
from nyaya.agents.schemas import ExtractedRequirement
from nyaya.core.enums import Priority, RequirementCategory, RiskLevel
from nyaya.graph.gates import GATES, UnauthorisedApproverError, authorise
from nyaya.graph.state import WorkflowState, initial_state
from nyaya.graph.workflow import (
    _continue_or_halt,
    _derive_factors,
    node_baseline_gate,
    node_recommend_sdlc,
    node_sdlc_gate,
)


def _requirement(statement: str, risk: RiskLevel = RiskLevel.HIGH) -> AnalysedRequirement:
    return AnalysedRequirement(
        requirement=ExtractedRequirement(
            statement=statement,
            rationale="r",
            categories=[RequirementCategory.REGULATORY, RequirementCategory.SECURITY],
            priority=Priority.MUST,
            risk_level=risk,
            acceptance_criteria=["Given X, when Y, then Z."],
            assumptions=[],
            quoted_source="src",
        ),
        defects=[],
        ears_pattern="ubiquitous",
    )


def _mini_graph():
    """A two-gate graph exercising suspend, resume and halt."""
    graph = StateGraph(WorkflowState)
    graph.add_node("baseline_gate", node_baseline_gate)
    graph.add_node("recommend_sdlc", node_recommend_sdlc)
    graph.add_node("sdlc_gate", node_sdlc_gate)
    graph.add_edge(START, "baseline_gate")
    graph.add_conditional_edges(
        "baseline_gate",
        _continue_or_halt,
        {"continue": "recommend_sdlc", "halt": END},
    )
    graph.add_edge("recommend_sdlc", "sdlc_gate")
    graph.add_edge("sdlc_gate", END)
    return graph.compile(checkpointer=InMemorySaver())


def _config():
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


def _state():
    state = initial_state(project_id="p1", source_text="text")
    state["requirements"] = [_requirement("The system shall screen customers.")]
    return state


async def test_run_suspends_at_the_first_gate():
    """The run must stop and surface what the reviewer needs to decide."""
    app, config = _mini_graph(), _config()
    result = await app.ainvoke(_state(), config)

    assert "__interrupt__" in result
    packet = result["__interrupt__"][0].value
    assert packet["gate"] == "requirement_baseline"
    assert packet["required_roles"]
    assert packet["summary"]["requirement_count"] == 1


async def test_run_does_not_advance_without_a_decision():
    """Re-invoking without supplying a decision must not slip past the gate."""
    app, config = _mini_graph(), _config()
    await app.ainvoke(_state(), config)

    state = await app.aget_state(config)
    assert state.next  # still pending
    assert not state.values.get("sdlc")


async def test_approval_resumes_and_records_the_decision():
    app, config = _mini_graph(), _config()
    await app.ainvoke(_state(), config)

    result = await app.ainvoke(
        Command(resume={"decision": "approve", "actor": "ba@bank.example"}), config
    )

    baseline = [d for d in result["decisions"] if d["gate"] == "requirement_baseline"]
    assert baseline and baseline[0]["actor"] == "ba@bank.example"
    assert baseline[0]["at"]  # timestamped for the audit record


async def test_rejection_halts_the_run():
    """A gate whose refusal does not stop anything is not a gate."""
    app, config = _mini_graph(), _config()
    await app.ainvoke(_state(), config)

    result = await app.ainvoke(
        Command(
            resume={
                "decision": "reject",
                "actor": "ba@bank.example",
                "comment": "requirements are not yet agreed",
            }
        ),
        config,
    )

    assert result["halted"]
    assert "not yet agreed" in result["halt_reason"]
    assert result.get("sdlc") is None  # never reached the recommendation


async def test_decisions_accumulate_across_gates():
    """Approvals are appended, never replaced: the record must show every
    decision a reviewer made, not only the last."""
    app, config = _mini_graph(), _config()
    await app.ainvoke(_state(), config)
    await app.ainvoke(Command(resume={"decision": "approve", "actor": "ba"}), config)
    result = await app.ainvoke(
        Command(resume={"decision": "approve", "actor": "architect"}), config
    )

    gates = [d["gate"] for d in result["decisions"]]
    assert gates == ["requirement_baseline", "sdlc_selection"]


async def test_state_is_durable_across_a_fresh_handle():
    """A suspended run must be resumable by a different caller later - that is
    what makes a gate an approval rather than a prompt."""
    saver = InMemorySaver()

    def compile_app():
        graph = StateGraph(WorkflowState)
        graph.add_node("baseline_gate", node_baseline_gate)
        graph.add_edge(START, "baseline_gate")
        graph.add_edge("baseline_gate", END)
        return graph.compile(checkpointer=saver)

    config = _config()
    await compile_app().ainvoke(_state(), config)

    # A separate compiled handle over the same store resumes the same run.
    result = await compile_app().ainvoke(
        Command(resume={"decision": "approve", "actor": "later@bank.example"}), config
    )
    assert result["decisions"][0]["actor"] == "later@bank.example"


def test_gate_roles_are_enforced():
    from nyaya.core.enums import StakeholderRole

    authorise("regulatory_interpretation", StakeholderRole.COMPLIANCE)
    with pytest.raises(UnauthorisedApproverError):
        authorise("regulatory_interpretation", StakeholderRole.PRODUCT_OWNER)


def test_every_gate_declares_a_competent_role():
    for name, gate in GATES.items():
        assert gate.required_roles, f"{name} has no competent role"
        assert gate.description


def test_sdlc_factors_are_derived_from_the_requirements():
    """A hand-supplied factor vector is a conclusion dressed as an input."""
    state = _state()
    state["unclear"] = ["what is the latency target?"]
    factors = _derive_factors(state)

    assert set(factors) == set(__import__("nyaya.mcda.sdlc", fromlist=["FACTORS"]).FACTORS)
    assert all(0.0 <= v <= 1.0 for v in factors.values())
    # every requirement is regulatory+security and high risk in this fixture
    assert factors["regulatory_criticality"] >= 0.5
    assert factors["security_risk"] >= 0.4
