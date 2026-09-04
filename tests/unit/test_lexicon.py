"""Ambiguity lexicon: it must catch vagueness without punishing good writing."""

from __future__ import annotations

import pytest

from nyaya.agents.quality.lexicon import AmbiguityKind, blocking, scan

WELL_FORMED = [
    "When a customer submits an onboarding application, the system shall screen "
    "the applicant against the designated-persons list before activating the account.",
    "The system shall retain customer identification records for five years from "
    "the date the relationship ends.",
    "If liveness detection fails, then the system shall terminate the video session "
    "and record the failure reason.",
    "While a customer is categorised as high risk, the system shall require "
    "senior-management approval before activating the account.",
    "The system shall encrypt customer identification documents at rest using AES-256.",
]


@pytest.mark.parametrize("statement", WELL_FORMED)
def test_well_formed_requirements_have_no_blocking_findings(statement):
    """A linter that fires on good input is one reviewers learn to ignore."""
    assert blocking(scan(statement)) == []


def test_vague_qualifiers_are_caught():
    findings = scan("The system shall provide appropriate and adequate security.")
    kinds = {f.kind for f in findings}
    assert AmbiguityKind.VAGUE_QUALIFIER in kinds


def test_unquantified_terms_are_caught():
    findings = scan("The system shall respond quickly to verification requests.")
    assert any(f.kind is AmbiguityKind.UNQUANTIFIED for f in findings)


def test_optionality_is_caught():
    findings = scan("The system shall log access as needed.")
    assert any(f.kind is AmbiguityKind.OPTIONALITY for f in findings)


def test_open_ended_lists_are_caught():
    findings = scan("The system shall store documents, identity proofs, etc.")
    assert any(f.kind is AmbiguityKind.OPEN_ENDED for f in findings)


def test_defined_regulatory_terms_are_not_flagged():
    """'high risk' is a defined category; the regulation supplies its meaning."""
    findings = scan("The system shall apply enhanced due diligence to a high risk customer.")
    assert not any(f.term.lower() == "high" for f in findings)


def test_passive_voice_in_a_condition_clause_is_allowed():
    """Passive in a trigger describes a state; it hides no responsible actor."""
    findings = scan(
        "While a customer is categorised as high risk, the system shall block transfers."
    )
    assert not any(f.kind is AmbiguityKind.PASSIVE_ACTOR for f in findings)


def test_passive_voice_in_the_obligation_is_flagged():
    findings = scan("Customer records shall be retained for five years.")
    assert any(f.kind is AmbiguityKind.PASSIVE_ACTOR for f in findings)


def test_severity_separates_blocking_from_informational():
    findings = scan("The system shall notify all users quickly.")
    assert any(f.kind is AmbiguityKind.UNQUANTIFIED and f.blocking for f in findings)
    assert any(f.kind is AmbiguityKind.SUPERLATIVE and not f.blocking for f in findings)


def test_longest_match_wins():
    """'as soon as possible' must not be reported merely as 'soon'."""
    findings = scan("The system shall respond as soon as possible.")
    assert any("as soon as possible" in f.term.lower() for f in findings)
