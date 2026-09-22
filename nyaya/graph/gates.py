"""Human-approval gates.

The brief makes human approval mandatory for requirement baselines, regulatory
interpretations, high-risk security requirements, conflict resolutions,
architecture-critical requirements and SDLC selection. Those are not advisory
checkpoints: the workflow must be unable to proceed past them without a recorded
human decision.

LangGraph's `interrupt` provides exactly that. It suspends execution at the node,
persists the checkpoint, and returns control to the caller. The run resumes only
when a decision is supplied - and because the checkpoint is durable, "resumes"
can mean days later, in a different process, after a compliance officer has read
the evidence. That is the difference between a gate and a prompt.

Each gate declares the role competent to clear it. A product owner cannot sign
off a regulatory interpretation, and encoding that here means the constraint is
enforced by the workflow rather than by convention.
"""

from __future__ import annotations

from dataclasses import dataclass

from nyaya.core.enums import StakeholderRole


@dataclass(frozen=True, slots=True)
class Gate:
    """A mandatory approval checkpoint."""

    name: str
    description: str
    required_roles: tuple[StakeholderRole, ...]
    """Any one of these may clear the gate. Multiple roles are listed where the
    decision legitimately belongs to more than one function."""

    blocking: bool = True
    """False for gates that record a decision but need not halt the run - used
    where a project has explicitly delegated the judgement in advance."""


GATES: dict[str, Gate] = {
    "requirement_baseline": Gate(
        name="requirement_baseline",
        description=(
            "Approve the extracted requirements as a baseline. Everything "
            "downstream - compliance mapping, traceability, the SDLC "
            "recommendation - is derived from this set, so an error admitted "
            "here propagates silently."
        ),
        required_roles=(StakeholderRole.BUSINESS_ANALYST, StakeholderRole.PRODUCT_OWNER),
    ),
    "regulatory_interpretation": Gate(
        name="regulatory_interpretation",
        description=(
            "Confirm the requirement-to-control mappings and their citations. "
            "The system may propose a mapping and verify its citation, but it "
            "must not make a final legal determination - that authority rests "
            "with compliance or legal."
        ),
        required_roles=(StakeholderRole.COMPLIANCE, StakeholderRole.LEGAL),
    ),
    "compliance_gap": Gate(
        name="compliance_gap",
        description=(
            "Accept or remediate the mandatory controls no requirement covers. "
            "A blocking gap left unaddressed is a known compliance failure "
            "being carried into build."
        ),
        required_roles=(StakeholderRole.COMPLIANCE, StakeholderRole.RISK),
    ),
    "security_requirements": Gate(
        name="security_requirements",
        description="Approve requirements assessed as high or critical security risk.",
        required_roles=(StakeholderRole.SECURITY, StakeholderRole.ARCHITECT),
    ),
    "conflict_resolution": Gate(
        name="conflict_resolution",
        description=(
            "Resolve contradictions between stakeholders. The system detects "
            "and explains a conflict; deciding between two legitimate business "
            "positions is not a decision it is competent to make."
        ),
        required_roles=(StakeholderRole.PRODUCT_OWNER, StakeholderRole.ARCHITECT),
    ),
    "production_readiness": Gate(
        name="production_readiness",
        description=(
            "Approve release to production. The brief lists this among the "
            "decisions a human must make, and it is the one gate whose subject "
            "is not a document: everything upstream can be corrected in a later "
            "version, and this one puts the system in front of customers and "
            "their money."
        ),
        required_roles=(
            StakeholderRole.PRODUCT_OWNER,
            StakeholderRole.COMPLIANCE,
            StakeholderRole.SECURITY,
        ),
    ),
    "sdlc_selection": Gate(
        name="sdlc_selection",
        description=(
            "Approve the recommended lifecycle. The ranking is derived and "
            "explainable, but adopting a lifecycle commits an organisation to a "
            "way of working that the factor vector does not fully capture."
        ),
        required_roles=(
            StakeholderRole.ARCHITECT,
            StakeholderRole.PRODUCT_OWNER,
            StakeholderRole.COMPLIANCE,
        ),
    ),
}


class UnauthorisedApproverError(PermissionError):
    """The actor's role is not competent to clear this gate."""


def authorise(gate_name: str, role: StakeholderRole) -> None:
    """Check that `role` may clear `gate_name`, raising if not."""
    gate = GATES.get(gate_name)
    if gate is None:
        raise KeyError(f"Unknown gate {gate_name!r}")
    if role not in gate.required_roles:
        raise UnauthorisedApproverError(
            f"role {role.value!r} cannot clear gate {gate_name!r}; "
            f"requires one of {[r.value for r in gate.required_roles]}"
        )


def payload(gate_name: str, summary: dict) -> dict:
    """The packet surfaced to a human when the workflow suspends.

    Carries what the reviewer needs to decide *and* who is competent to decide
    it, so a queue can route the item rather than merely display it.
    """
    gate = GATES[gate_name]
    return {
        "gate": gate.name,
        "description": gate.description,
        "required_roles": [r.value for r in gate.required_roles],
        "summary": summary,
    }


__all__ = ["GATES", "Gate", "UnauthorisedApproverError", "authorise", "payload"]
