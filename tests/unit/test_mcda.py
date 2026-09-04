"""AHP weight derivation and TOPSIS ranking.

Entirely deterministic, which is the point: an SDLC recommendation an architect
cannot re-derive is one they cannot challenge.
"""

from __future__ import annotations

import pytest

from nyaya.core.enums import SDLCModel
from nyaya.mcda import (
    Alternative,
    InconsistentJudgementsError,
    default_factors,
    derive_weights,
    rank,
    recommend,
)
from nyaya.mcda.ahp import CONSISTENCY_LIMIT, build_matrix

CRITERIA = ["regulatory", "security", "speed", "stability"]


# --- AHP ------------------------------------------------------------------


def test_matrix_is_reciprocal():
    matrix = build_matrix(CRITERIA, {("regulatory", "speed"): 5})
    i, j = CRITERIA.index("regulatory"), CRITERIA.index("speed")
    assert matrix[i, j] == 5
    assert matrix[j, i] == pytest.approx(1 / 5)
    assert all(matrix[k, k] == 1 for k in range(len(CRITERIA)))


def test_weights_sum_to_one_and_reflect_preference():
    result = derive_weights(
        CRITERIA,
        {
            ("regulatory", "speed"): 5,
            ("security", "speed"): 5,
            ("regulatory", "stability"): 3,
            ("security", "stability"): 3,
            ("regulatory", "security"): 1,
            ("stability", "speed"): 2,
        },
    )
    assert sum(result.weights.values()) == pytest.approx(1.0)
    assert result.weights["regulatory"] > result.weights["speed"]
    assert result.consistent


def test_perfectly_consistent_judgements_have_near_zero_ratio():
    result = derive_weights(CRITERIA, {})  # all equal
    assert result.consistency_ratio < 1e-6


def test_cyclic_judgements_are_rejected():
    """A > B > C > A is incoherent, and a hand-assigned weight vector could
    never reveal that. Detecting it is the reason AHP is used at all."""
    with pytest.raises(InconsistentJudgementsError):
        derive_weights(
            CRITERIA,
            {
                ("regulatory", "security"): 9,
                ("security", "speed"): 9,
                ("speed", "regulatory"): 9,
            },
        )


def test_inconsistency_can_be_reported_instead_of_raised():
    result = derive_weights(
        CRITERIA,
        {
            ("regulatory", "security"): 9,
            ("security", "speed"): 9,
            ("speed", "regulatory"): 9,
        },
        strict=False,
    )
    assert not result.consistent
    assert result.consistency_ratio > CONSISTENCY_LIMIT


def test_comparison_outside_the_scale_is_rejected():
    with pytest.raises(ValueError):
        derive_weights(CRITERIA, {("regulatory", "speed"): 42})


def test_unknown_criterion_is_rejected():
    with pytest.raises(ValueError):
        derive_weights(CRITERIA, {("teleportation", "speed"): 3})


# --- TOPSIS ---------------------------------------------------------------


def test_dominant_alternative_ranks_first():
    result = rank(
        [
            Alternative("best", {"a": 1.0, "b": 1.0}),
            Alternative("middling", {"a": 0.5, "b": 0.5}),
            Alternative("worst", {"a": 0.1, "b": 0.1}),
        ],
        {"a": 0.5, "b": 0.5},
    )
    assert [r.name for r in result.rankings] == ["best", "middling", "worst"]
    assert result.rankings[0].closeness == pytest.approx(1.0)


def test_weights_change_the_ranking():
    alternatives = [
        Alternative("specialist_a", {"a": 1.0, "b": 0.1}),
        Alternative("specialist_b", {"a": 0.1, "b": 1.0}),
    ]
    assert rank(alternatives, {"a": 0.9, "b": 0.1}).recommended.name == "specialist_a"
    assert rank(alternatives, {"a": 0.1, "b": 0.9}).recommended.name == "specialist_b"


def test_identical_alternatives_tie_without_dividing_by_zero():
    result = rank([Alternative("x", {"a": 0.5}), Alternative("y", {"a": 0.5})], {"a": 1.0})
    assert all(r.closeness == pytest.approx(0.5) for r in result.rankings)


def test_cost_criteria_are_minimised():
    result = rank(
        [Alternative("cheap", {"cost": 0.1}), Alternative("dear", {"cost": 0.9})],
        {"cost": 1.0},
        benefit={"cost": False},
    )
    assert result.recommended.name == "cheap"


def test_contributions_explain_the_ranking():
    """A ranking that cannot be attributed to criteria cannot be argued with."""
    result = rank([Alternative("x", {"a": 0.8, "b": 0.2})], {"a": 0.7, "b": 0.3})
    assert set(result.recommended.contributions) == {"a", "b"}


def test_empty_alternatives_is_rejected():
    with pytest.raises(ValueError):
        rank([], {"a": 1.0})


# --- end-to-end SDLC selection -------------------------------------------
#
# Each scenario asserts the lifecycle the brief's own guidance prescribes.


@pytest.mark.parametrize(
    ("label", "overrides", "expected"),
    [
        (
            "regulated with fast-changing requirements",
            dict(
                regulatory_criticality=0.95,
                security_risk=0.9,
                change_frequency=0.85,
                continuous_delivery_need=0.8,
                requirement_stability=0.35,
                failure_consequence=0.85,
            ),
            SDLCModel.AGILE_DEVSECOPS_HYBRID,
        ),
        (
            "stable with strict verification",
            dict(
                regulatory_criticality=0.95,
                security_risk=0.9,
                failure_consequence=0.95,
                formal_verification_need=0.95,
                requirement_stability=0.85,
                documentation_need=0.9,
                change_frequency=0.2,
                continuous_delivery_need=0.2,
            ),
            SDLCModel.V_MODEL,
        ),
        (
            "low risk and exploratory",
            dict(
                regulatory_criticality=0.2,
                security_risk=0.3,
                change_frequency=0.9,
                requirement_stability=0.2,
                failure_consequence=0.2,
                documentation_need=0.2,
                stakeholder_availability=0.9,
                formal_verification_need=0.1,
                continuous_delivery_need=0.6,
            ),
            SDLCModel.AGILE,
        ),
        (
            "high uncertainty and technical risk",
            dict(
                project_complexity=0.95,
                requirement_stability=0.25,
                security_risk=0.85,
                regulatory_criticality=0.7,
                failure_consequence=0.8,
                change_frequency=0.6,
                legacy_dependence=0.8,
                formal_verification_need=0.6,
                documentation_need=0.6,
            ),
            SDLCModel.SPIRAL,
        ),
    ],
)
def test_scenarios_match_established_guidance(label, overrides, expected):
    assert recommend(default_factors(**overrides)).recommended is expected, label


def test_recommendation_is_ranked_not_a_single_label():
    """The brief asks for ranked recommendations; a single label hides how close
    the runner-up was, and a 0.02 margin means something different from 0.30."""
    result = recommend(default_factors(regulatory_criticality=0.9))
    ranked = result.ranked()
    assert len(ranked) == len(SDLCModel)
    assert [p for _, p in ranked] == sorted((p for _, p in ranked), reverse=True)


def test_near_ties_are_flagged_for_human_decision():
    result = recommend(default_factors())
    if result.ranking.margin < 0.05:
        assert result.close_call
        assert any("close call" in n for n in result.notes)


def test_missing_factor_scores_are_rejected():
    with pytest.raises(ValueError, match="missing factor"):
        recommend({"regulatory_criticality": 0.9})
