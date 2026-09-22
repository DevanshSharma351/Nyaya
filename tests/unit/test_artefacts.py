"""The artefact set the brief lists as expected outputs.

These fix the properties that make the artefacts worth having: that they are
derived from approved content rather than written, and that an incomplete
traceability chain is reported rather than tidied away.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nyaya.artefacts import build
from nyaya.core.enums import Priority, RequirementCategory, RiskLevel


@dataclass
class _Requirement:
    statement: str
    rationale: str = "the obligation requires it"
    categories: list[RequirementCategory] = field(default_factory=list)
    priority: Priority = Priority.MUST
    risk_level: RiskLevel = RiskLevel.MEDIUM
    acceptance_criteria: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    quoted_source: str = "we have to check them before the account goes live"


@dataclass
class _Item:
    requirement: _Requirement
    defects: list = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    confidence: float | None = None


EVENT_DRIVEN = (
    "When a customer is onboarded remotely, the system shall screen the customer "
    "against the designated-persons list before activation."
)


def test_a_user_story_names_the_trigger_separately_from_the_behaviour():
    """EARS puts the condition first; a story that keeps it inline is unreadable."""
    story = build([_Item(_Requirement(EVENT_DRIVEN))]).user_stories[0]

    assert story.trigger == "a customer is onboarded remotely"
    assert "screen the customer" in story.capability
    # The trigger must not also be left inside the capability.
    assert "When a customer is onboarded" not in story.capability


def test_the_beneficiary_comes_from_the_category_not_from_guesswork():
    """A regulatory requirement is written for whoever will sign it off."""
    regulatory = build(
        [_Item(_Requirement(EVENT_DRIVEN, categories=[RequirementCategory.REGULATORY]))]
    ).user_stories[0]
    security = build(
        [_Item(_Requirement(EVENT_DRIVEN, categories=[RequirementCategory.SECURITY]))]
    ).user_stories[0]

    assert "compliance officer" in regulatory.role
    assert "security team" in security.role


def test_regulatory_wins_over_functional_when_a_requirement_is_both():
    """Multi-label is normal; the story is written for the approver."""
    story = build(
        [
            _Item(
                _Requirement(
                    EVENT_DRIVEN,
                    categories=[
                        RequirementCategory.FUNCTIONAL,
                        RequirementCategory.REGULATORY,
                    ],
                )
            )
        ]
    ).user_stories[0]
    assert "compliance officer" in story.role


def test_an_incomplete_trace_reports_its_gaps():
    """A traceability matrix exists to surface missing links, not hide them."""
    artefacts = build([_Item(_Requirement(EVENT_DRIVEN))])
    row = artefacts.traceability[0]

    assert "no citation" in row.gaps
    assert "no control mapping" in row.gaps
    assert "no acceptance criteria" in row.gaps
    assert artefacts.traceability_coverage == 0.0


def test_a_complete_chain_counts_towards_coverage():
    artefacts = build(
        [
            _Item(
                _Requirement(EVENT_DRIVEN, acceptance_criteria=["screening completes first"]),
                citations=["RBI-MD-KYC:22(a)"],
            )
        ],
        control_mappings={"FR-001": ["KYC.SCREEN.SANCTIONS"]},
    )
    assert artefacts.traceability[0].gaps == []
    assert artefacts.traceability_coverage == 1.0


def test_defects_become_the_use_case_exception_paths():
    """A known way a requirement fails is an exception flow, not a dropped note."""

    @dataclass
    class _Defect:
        detail: str

    use_case = build(
        [_Item(_Requirement(EVENT_DRIVEN), defects=[_Defect("threshold is unstated")])]
    ).use_cases[0]
    assert "threshold is unstated" in use_case.exceptions


def test_the_risk_register_is_ordered_by_severity():
    artefacts = build(
        [
            _Item(_Requirement("The system shall log access.", risk_level=RiskLevel.LOW)),
            _Item(_Requirement(EVENT_DRIVEN, risk_level=RiskLevel.CRITICAL)),
        ]
    )
    assert [r.level for r in artefacts.risks] == ["critical", "low"]


def test_a_statement_that_is_not_in_ears_form_is_not_mangled():
    """Better a stiff story than one built from a mis-parse."""
    story = build([_Item(_Requirement("Screening happens before activation."))]).user_stories[0]
    assert story.trigger is None
    assert "Screening happens before activation" in story.capability
