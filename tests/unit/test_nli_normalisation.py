"""EARS-to-declarative normalisation for entailment checking.

Pure string transformation, so it is tested without loading a model. The
measured effect of this transform is recorded in the engineering log: a correct
clause-requirement pair scored `contradicts` 0.003 in raw EARS form and
`supports` 0.994 after normalisation.
"""

from __future__ import annotations

import pytest

from nyaya.retrieval.nli import to_obligation_claim


@pytest.mark.parametrize(
    ("statement", "expected_fragment"),
    [
        (
            "When a customer is onboarded remotely, the system shall screen the customer.",
            "screen the customer",
        ),
        (
            "If liveness detection fails, then the system shall terminate the session.",
            "terminate the session",
        ),
        (
            "While the account is frozen, the system shall reject transfers.",
            "reject transfers",
        ),
        ("The system shall encrypt records at rest.", "encrypt records at rest"),
    ],
)
def test_scaffolding_is_stripped(statement, expected_fragment):
    claim = to_obligation_claim(statement)
    assert claim.startswith("It is required that ")
    assert expected_fragment in claim


def test_conditional_prefix_is_removed():
    """The trigger narrows *when* a duty applies; the clause obliges the action."""
    claim = to_obligation_claim(
        "When a customer is onboarded through a remote channel, the system shall screen."
    )
    assert "onboarded through a remote channel" not in claim


def test_actor_is_removed():
    """A requirement names the software; a regulation names the institution.

    Keeping the mismatched subject halves the separation between correct and
    incorrect citations, so the actor is dropped.
    """
    claim = to_obligation_claim("The system shall screen the customer.")
    assert "the system" not in claim.lower()


def test_modal_is_removed():
    assert "shall" not in to_obligation_claim("The system shall retain records.")


def test_plain_prose_is_handled_without_raising():
    assert to_obligation_claim("Security matters.").startswith("It is required that")


def test_normalisation_is_idempotent_enough_to_be_safe():
    once = to_obligation_claim("The system shall encrypt records.")
    twice = to_obligation_claim(once)
    assert "encrypt records" in twice
