"""Confidence fusion.

The property under test is that confidence is *computed from independent
signals*, so a claim can be high on one and still fall below review threshold.
"""

from __future__ import annotations

from nyaya.core.confidence import (
    REVIEW_THRESHOLD,
    ConfidenceComponents,
    agreement,
    fuse,
)


def test_all_signals_strong_gives_high_confidence():
    result = fuse(
        ConfidenceComponents(retrieval=0.95, entailment=0.95, validation=1.0, consistency=1.0)
    )
    assert result.score > 0.9
    assert not result.needs_review
    assert result.reasons == []


def test_plausible_but_non_entailing_citation_is_routed_for_review():
    """The dangerous case: retrieval found something similar that obliges nothing.

    High retrieval similarity must not rescue a citation whose clause does not
    entail the claim - that is exactly the failure the validator exists to catch.
    """
    result = fuse(
        ConfidenceComponents(retrieval=0.95, entailment=0.02, validation=1.0, consistency=1.0)
    )
    assert result.needs_review
    assert any("entail" in r for r in result.reasons)


def test_failed_validation_is_recorded_as_a_reason():
    result = fuse(
        ConfidenceComponents(retrieval=0.9, entailment=0.9, validation=0.0, consistency=0.9)
    )
    assert any("validation" in r for r in result.reasons)


def test_components_are_retained_for_explanation():
    """A bare score is not actionable; the components say what went wrong."""
    components = ConfidenceComponents(
        retrieval=0.5, entailment=0.4, validation=1.0, consistency=0.7
    )
    result = fuse(components)
    assert result.components.entailment == 0.4
    assert set(result.as_dict()["components"]) == {
        "retrieval", "entailment", "validation", "consistency",
    }


def test_score_is_bounded():
    assert fuse(ConfidenceComponents()).score == 0.0
    assert fuse(
        ConfidenceComponents(retrieval=1, entailment=1, validation=1, consistency=1)
    ).score == 1.0


def test_review_threshold_separates_the_examples():
    strong = fuse(ConfidenceComponents(0.9, 0.9, 1.0, 0.9))
    weak = fuse(ConfidenceComponents(0.3, 0.1, 0.0, 0.3))
    assert strong.score >= REVIEW_THRESHOLD > weak.score


def test_agreement_measures_sample_stability():
    assert agreement(["a", "a", "a"]) == 1.0
    assert agreement(["a", "a", "b"]) > agreement(["a", "b", "c"])
    assert agreement([]) == 0.0
    # whitespace and case differences are not disagreement
    assert agreement(["The  System", "the system"]) == 1.0
