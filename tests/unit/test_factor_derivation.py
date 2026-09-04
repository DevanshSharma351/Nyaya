"""Deriving SDLC factors from an extracted requirement set.

The factor vector decides the lifecycle recommendation, so how it is produced is
the difference between a recommendation traceable to evidence and one that
launders whoever moved the sliders. These fix the two behaviours that make the
derivation defensible: it responds to what was actually extracted, and it does
not let an incomplete brief argue for a lighter process.
"""

from __future__ import annotations

from dataclasses import dataclass

from nyaya.core.enums import RequirementCategory, RiskLevel
from nyaya.mcda.derive import FLOORS, derive


@dataclass
class _Requirement:
    categories: list[RequirementCategory]
    risk_level: RiskLevel


@dataclass
class _Item:
    """Stands in for an extraction result item, which carries a requirement."""

    requirement: _Requirement


def _item(categories: list[RequirementCategory], risk: RiskLevel) -> _Item:
    return _Item(_Requirement(categories, risk))


REGULATORY = RequirementCategory.REGULATORY
SECURITY = RequirementCategory.SECURITY


def test_floors_apply_when_a_brief_says_nothing_about_risk():
    """Silence is not evidence of low risk.

    A brief that mentions no security requirement is far more often one where
    nobody wrote it down than one where security does not matter. Letting the
    factor fall to zero would let an incomplete brief argue for a lighter
    process, which is exactly backwards.
    """
    derivation = derive([_item([], RiskLevel.LOW)], unclear=[])

    assert derivation.factors["security_risk"] == FLOORS["security_risk"]
    assert derivation.factors["regulatory_criticality"] == FLOORS["regulatory_criticality"]
    assert derivation.factors["failure_consequence"] == FLOORS["failure_consequence"]


def test_factors_rise_with_what_was_actually_found():
    """A wholly regulatory, wholly critical set must exceed the floors."""
    requirements = [
        _item([REGULATORY, SECURITY], RiskLevel.CRITICAL),
        _item([REGULATORY, SECURITY], RiskLevel.HIGH),
    ]
    derivation = derive(requirements, unclear=[])

    assert derivation.factors["regulatory_criticality"] == 1.0
    assert derivation.factors["security_risk"] == 1.0
    assert derivation.factors["failure_consequence"] == 1.0
    assert derivation.factors["formal_verification_need"] == 1.0


def test_open_questions_trade_stability_against_change_frequency():
    """Unanswered questions mean the requirements are not settled.

    The two factors must move in opposite directions: a brief full of open
    questions is unstable *and* likely to change, and a lifecycle chosen as if
    it were stable would be chosen on a false premise.
    """
    requirements = [_item([REGULATORY], RiskLevel.HIGH)] * 2

    settled = derive(requirements, unclear=[])
    unsettled = derive(requirements, unclear=["a?", "b?", "c?", "d?"])

    assert settled.factors["requirement_stability"] == 1.0
    assert settled.factors["change_frequency"] == 0.0
    assert unsettled.factors["requirement_stability"] < settled.factors["requirement_stability"]
    assert unsettled.factors["change_frequency"] > settled.factors["change_frequency"]
    assert (
        unsettled.factors["requirement_stability"]
        + unsettled.factors["change_frequency"]
        == 1.0
    )


def test_question_count_is_read_relative_to_the_number_of_requirements():
    """A large brief naturally raises more questions.

    Counting them absolutely would make every long brief look unstable, so the
    ratio is what matters. Ten questions across twenty requirements is a settled
    set; ten across two is not.
    """
    small = derive([_item([REGULATORY], RiskLevel.LOW)] * 2, unclear=["q?"] * 4)
    large = derive([_item([REGULATORY], RiskLevel.LOW)] * 20, unclear=["q?"] * 4)

    assert small.factors["requirement_stability"] < large.factors["requirement_stability"]


def test_the_derivation_explains_itself():
    """Each observation names the number it produced.

    A recommendation an architect cannot re-derive is one they cannot
    challenge, and the factors are where the argument actually lives.
    """
    derivation = derive([_item([REGULATORY], RiskLevel.CRITICAL)], unclear=["q?"])

    assert derivation.observations
    joined = " ".join(derivation.observations)
    assert "1 requirement" in joined
    assert "open question" in joined


def test_no_requirements_does_not_divide_by_zero():
    """An empty extraction must still produce a usable vector.

    It happens: a brief with no obligation in it extracts nothing. The floors
    are the right answer there, and a crash is not.
    """
    derivation = derive([], unclear=[])
    assert derivation.factors["regulatory_criticality"] == FLOORS["regulatory_criticality"]
