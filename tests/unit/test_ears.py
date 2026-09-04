"""EARS grammar recognition."""

from __future__ import annotations

import pytest

from nyaya.agents.quality.ears import EARSPattern, analyse


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("The system shall encrypt customer records at rest.", EARSPattern.UBIQUITOUS),
        (
            "When a customer submits an application, the system shall screen the applicant.",
            EARSPattern.EVENT_DRIVEN,
        ),
        (
            "While the account is frozen, the system shall reject outward transfers.",
            EARSPattern.STATE_DRIVEN,
        ),
        (
            "If liveness detection fails, then the system shall terminate the session.",
            EARSPattern.UNWANTED,
        ),
        (
            "Where video onboarding is enabled, the system shall record the session.",
            EARSPattern.OPTIONAL,
        ),
        (
            "While a review is open, when a document is uploaded, the system shall notify the reviewer.",
            EARSPattern.COMPLEX,
        ),
    ],
)
def test_patterns_are_recognised(statement, expected):
    assert analyse(statement).pattern is expected


def test_conforming_statement_has_no_issues():
    result = analyse("The system shall retain identity records for five years.")
    assert result.conforms
    assert result.is_binding
    assert result.issues == []


def test_prose_without_a_modal_is_rejected():
    result = analyse("Security is very important to the onboarding journey.")
    assert result.pattern is EARSPattern.NONE
    assert not result.conforms
    assert any("no modal verb" in i for i in result.issues)


def test_non_binding_modal_is_flagged():
    """'should' expresses a preference, not a requirement."""
    result = analyse("The system should be secure.")
    assert not result.conforms
    assert result.modal == "should"
    assert any("non-binding modal" in i for i in result.issues)


def test_compound_requirement_is_flagged():
    """Two obligations cannot be separately approved, tested or traced."""
    result = analyse("The system shall verify the PAN and shall notify compliance.")
    assert any("compound" in i for i in result.issues)


def test_single_obligation_containing_and_is_not_flagged():
    """Guard against the compound check firing on any 'and'."""
    result = analyse("The system shall record the reviewer identity and the access timestamp.")
    assert not any("compound" in i for i in result.issues)
    assert result.conforms
