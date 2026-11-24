"""The state carried through the requirements-engineering workflow.

Everything an agent produces lands here, and everything a later agent needs it
reads from here. Two consequences that matter for auditability:

- **The state is the record.** A checkpoint of this object at any node is a
  complete account of what the system knew and had decided at that point, which
  is what makes a run reconstructible after the fact.
- **Nothing is overwritten.** Agents append; approvals and rejections are
  recorded alongside what they acted on, never in place of it. A workflow whose
  state is mutated cannot answer "what did the reviewer actually see".
"""

from __future__ import annotations

import uuid
from typing import TypedDict

from nyaya.agents.compliance import ComplianceResult
from nyaya.agents.extraction import AnalysedRequirement
from nyaya.mcda.sdlc import SDLCRecommendation
from nyaya.rules.engine import CoverageReport


class GateDecision(TypedDict):
    """A human decision at an approval gate."""

    gate: str
    decision: str  # "approve" | "reject" | "revise"
    actor: str
    comment: str
    at: str


class WorkflowState(TypedDict, total=False):
    """Snapshot of a single workflow run threaded through the graph."""

    # --- inputs ---
    project_id: str
    run_id: str
    domain: str
    jurisdictions: list[str]
    source_text: str
    stakeholder_role: str | None

    # --- accumulated outputs ---
    requirements: list[AnalysedRequirement]
    unclear: list[str]
    compliance: list[ComplianceResult]
    coverage: list[CoverageReport]
    sdlc: SDLCRecommendation | None

    # --- human decisions, appended never replaced ---
    decisions: list[GateDecision]

    # --- control ---
    halted: bool
    halt_reason: str


def initial_state(
    *,
    project_id: str,
    source_text: str,
    domain: str = "ekyc_onboarding",
    jurisdictions: list[str] | None = None,
    stakeholder_role: str | None = None,
) -> WorkflowState:
    return WorkflowState(
        project_id=project_id,
        run_id=str(uuid.uuid4()),
        domain=domain,
        jurisdictions=jurisdictions or ["IN"],
        source_text=source_text,
        stakeholder_role=stakeholder_role,
        requirements=[],
        unclear=[],
        compliance=[],
        coverage=[],
        sdlc=None,
        decisions=[],
        halted=False,
        halt_reason="",
    )


__all__ = ["GateDecision", "WorkflowState", "initial_state"]
