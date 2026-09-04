"""The extraction agent's deterministic half.

`inspect` and `verify_provenance` decide whether a model's output is a usable
requirement. They run without a model, so they are tested without one.
"""

from __future__ import annotations

from nyaya.agents.extraction import inspect, verify_provenance
from nyaya.agents.schemas import ExtractedRequirement
from nyaya.core.enums import DefectType, Priority, RequirementCategory, RiskLevel, Severity


def _req(statement: str, **overrides) -> ExtractedRequirement:
    payload = dict(
        statement=statement,
        rationale="because the stakeholder said so",
        categories=[RequirementCategory.REGULATORY],
        priority=Priority.MUST,
        risk_level=RiskLevel.HIGH,
        acceptance_criteria=["Given X, when Y, then Z."],
        assumptions=[],
        quoted_source="we have to check them against the sanctions list",
    )
    payload.update(overrides)
    return ExtractedRequirement(**payload)


def test_well_formed_requirement_has_no_blocking_defects():
    defects, pattern = inspect(
        _req(
            "When a customer is onboarded remotely, the system shall screen the "
            "customer against the designated-persons list before activation."
        )
    )
    assert pattern == "event_driven"
    assert not [d for d in defects if d.severity is Severity.MAJOR]


def test_echoed_input_is_rejected_as_untestable():
    """The exact failure mode measured before EARS templating existed.

    A stakeholder's sentence is well-formed JSON and passes schema validation,
    but is not a requirement. Only the linters catch this.
    """
    defects, pattern = inspect(
        _req("For any customer we onboard remotely we have to check them against a list.")
    )
    assert pattern == "none"
    assert any(d.detector == "ears_template" for d in defects)
    assert any(d.defect_type is DefectType.UNTESTABLE for d in defects)


def test_missing_acceptance_criteria_is_blocking():
    defects, _ = inspect(
        _req("The system shall retain records for five years.", acceptance_criteria=[])
    )
    assert any(d.detector == "completeness_check" and d.severity is Severity.MAJOR for d in defects)


def test_missing_quoted_source_is_blocking():
    defects, _ = inspect(
        _req("The system shall retain records for five years.", quoted_source="  ")
    )
    assert any(d.defect_type is DefectType.MISSING_SOURCE for d in defects)


def test_vague_statement_is_flagged():
    defects, _ = inspect(_req("The system shall provide appropriate security quickly."))
    assert any(d.detector == "weak_word_lexicon" for d in defects)


def test_provenance_accepts_a_verbatim_quotation():
    source = (
        "Compliance officer said: for any customer we onboard remotely we have to "
        "check them against the sanctions list before the account goes live."
    )
    assert verify_provenance(_req("The system shall screen customers."), source) is None


def test_provenance_tolerates_reflowed_whitespace():
    """Models reflow text; that is not fabrication."""
    source = "we have to check them\n  against the sanctions   list before activation"
    assert verify_provenance(_req("The system shall screen customers."), source) is None


def test_fabricated_quotation_is_caught():
    """A composed quotation is the most damaging failure: it looks like evidence."""
    defect = verify_provenance(
        _req(
            "The system shall screen customers.",
            quoted_source="the regulator requires quarterly penetration testing",
        ),
        "we have to check them against the sanctions list",
    )
    assert defect is not None
    assert defect.defect_type is DefectType.MISSING_SOURCE
    assert defect.severity is Severity.MAJOR
