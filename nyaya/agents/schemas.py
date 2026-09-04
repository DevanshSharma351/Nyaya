"""Typed contracts for agent input and output.

Every agent returns a validated object, never free text. Two consequences that
matter: the closed vocabularies are enforced by the decoder rather than parsed
out afterwards, and a schema change breaks loudly at the boundary instead of
silently downstream.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from nyaya.core.enums import (
    Priority,
    RequirementCategory,
    RiskLevel,
    StakeholderRole,
)


class ExtractedRequirement(BaseModel):
    """One requirement recovered from a stakeholder statement or document.

    Field descriptions are instructions to the model, not documentation for a
    reader - they are the only guidance the decoder sees for each field.
    """

    statement: str = Field(
        description=(
            "ONE testable requirement in EARS form. Use exactly one 'shall'. "
            "Choose the form that fits: "
            "'The <actor> shall <response>' for an always-active duty; "
            "'When <trigger>, the <actor> shall <response>' for an event; "
            "'While <state>, the <actor> shall <response>' for a state; "
            "'If <condition>, then the <actor> shall <response>' for an error or "
            "abuse path. Name the actor explicitly. Never write 'should', "
            "'may', 'appropriate', 'adequate', 'quickly' or 'as needed'; state "
            "a number, a standard or a named condition instead."
        )
    )
    rationale: str = Field(
        description="Why this is required, in one sentence, grounded in what the stakeholder said."
    )
    categories: list[RequirementCategory] = Field(
        description=(
            "Every category that applies. Multi-label: an audit-logging duty is "
            "both 'security' and 'audit_reporting'."
        )
    )
    priority: Priority = Field(
        description="'must' only where a regulation or a hard business rule compels it."
    )
    risk_level: RiskLevel = Field(description="Consequence if this requirement is not met.")
    acceptance_criteria: list[str] = Field(
        description=(
            "1-3 checks that would demonstrate the requirement is met. Each must "
            "be observable: name the input, the action and the expected outcome."
        )
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Anything assumed that the stakeholder did not state. Empty if none.",
    )
    quoted_source: str = Field(
        description=(
            "The exact span of the stakeholder's own words this requirement came "
            "from. Copy verbatim; do not paraphrase. This is the provenance link."
        )
    )


class ExtractionOutput(BaseModel):
    """The full result of extracting from one input."""

    requirements: list[ExtractedRequirement] = Field(
        description=(
            "One entry per distinct obligation. Split compound statements: "
            "'verify identity and screen against sanctions' is TWO requirements, "
            "because each can be accepted, tested and traced separately."
        )
    )
    unclear: list[str] = Field(
        default_factory=list,
        description=(
            "Questions that must be answered before a requirement can be written. "
            "Prefer listing something here over inventing a detail the "
            "stakeholder did not supply."
        ),
    )


class ClarificationQuestion(BaseModel):
    """A follow-up question for a stakeholder."""

    question: str = Field(description="A single, specific, answerable question.")
    topic: str = Field(description="The interview topic this probes.")
    why: str = Field(description="What is missing or ambiguous without the answer.")


class ExtractionContext(BaseModel):
    """Non-model context passed alongside the input text."""

    domain: str = "ekyc_onboarding"
    stakeholder_role: StakeholderRole | None = None
    jurisdictions: list[str] = Field(default_factory=lambda: ["IN"])


__all__ = [
    "ClarificationQuestion",
    "ExtractedRequirement",
    "ExtractionContext",
    "ExtractionOutput",
]
