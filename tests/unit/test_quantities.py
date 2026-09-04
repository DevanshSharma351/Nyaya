"""Fabricated-quantity detection.

Guards a failure observed in a real run: asked to remove vague language, the
model invented a threshold the stakeholder never gave. The fabricated statement
was *more* dangerous than the vague one, because it read as precise and passed
every other check.
"""

from __future__ import annotations

import pytest

from nyaya.agents.quality.quantities import extract_quantities, unsupported_quantities


def test_the_observed_fabrication_is_caught():
    """The exact statement produced by a repair round, and its actual source."""
    statement = (
        "The system shall limit the onboarding process to no more than three "
        "distinct user actions."
    )
    source = (
        "onboarding needs to be really smooth and modern, users hate friction, "
        "make it as quick as possible"
    )
    found = unsupported_quantities(statement, source)
    assert found
    assert any("three" in q.raw.lower() for q in found)


def test_units_may_be_separated_from_their_number():
    """'three distinct user actions' - modifiers sit between number and unit."""
    quantities = extract_quantities("no more than three distinct user actions")
    assert any(q.value == "3" and q.unit and "action" in q.unit for q in quantities)


def test_supported_quantity_passes():
    assert not unsupported_quantities(
        "The system shall retain evidence for five years from screening.",
        "keep proof of that check for five years",
    )


def test_number_words_and_digits_are_equivalent():
    """A stakeholder writes 'five years'; a model writes '5 years'."""
    assert not unsupported_quantities(
        "The system shall retain records for 5 years.",
        "keep proof for five years",
    )
    assert not unsupported_quantities(
        "The system shall retain records for five years.",
        "keep proof for 5 years",
    )


@pytest.mark.parametrize(
    "statement",
    [
        "The system shall encrypt records at rest using AES-256.",
        "The system shall comply with ISO 27001 controls.",
        "The system shall implement the control in section 16 of the Direction.",
    ],
)
def test_identifiers_are_not_treated_as_thresholds(statement):
    """A standard or clause reference names something; it asserts no magnitude."""
    assert not unsupported_quantities(statement, "encrypt the records securely")


def test_prose_without_quantities_is_clean():
    assert not unsupported_quantities(
        "When a customer is onboarded remotely, the system shall screen the "
        "customer before activation.",
        "check them against the sanctions list before the account goes live",
    )


def test_bare_small_integers_are_not_thresholds():
    """'one of the following' is prose, not an asserted magnitude."""
    assert not unsupported_quantities(
        "The system shall accept one of the accepted document types.",
        "accept the usual documents",
    )
