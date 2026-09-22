"""Checks that only make sense across a set of requirements.

Three of the defects the brief lists in §10 - duplication, conflicting
expectations, and a quantity nothing verifies - are properties of a collection
and cannot be found one statement at a time. They also only began to matter once
extraction stopped losing requirements: at two there is nothing to contradict.
"""

from __future__ import annotations

from nyaya.agents.quality.consistency import (
    analyse_set,
    find_conflicts,
    find_duplicates,
    find_incompleteness,
    similarity,
)

SCREEN = "When a customer is onboarded, the system shall screen the customer against the designated-persons list before activation."
SCREEN_REWORDED = "When a customer is onboarded, the system shall check the customer against the designated-persons list before activation."
RETAIN_FIVE = "The system shall retain customer identification records for five years from cessation."
RETAIN_5Y = "The system shall retain customer identification records for 5 years from cessation."
RETAIN_7Y = "The system shall retain customer identification records for 7 years from cessation."
ENCRYPT = "The system shall encrypt customer information transmitted over public networks."


def test_a_restatement_of_the_same_obligation_is_flagged():
    defects = find_duplicates([RETAIN_5Y, RETAIN_5Y])
    assert len(defects) == 1
    assert defects[0].kind == "duplication"
    # Reported against the later one: the earlier is what a reviewer keeps.
    assert defects[0].left == 1
    assert defects[0].right == 0


def test_unrelated_requirements_are_not_flagged_as_duplicates():
    """The failure direction that wastes attention is a false positive."""
    assert find_duplicates([SCREEN, ENCRYPT]) == []


def test_two_retention_periods_are_a_conflict():
    """The shape that actually appears: one team says five years, another seven."""
    defects = find_conflicts([RETAIN_5Y, RETAIN_7Y])
    assert len(defects) == 1
    assert defects[0].kind == "conflict"
    assert "7" in defects[0].detail and "5" in defects[0].detail


def test_the_same_period_in_different_units_is_not_a_conflict():
    """1440 minutes and 24 hours are the same obligation stated twice."""
    a = "The system shall time out an idle session after 24 hours."
    b = "The system shall time out an idle session after 1440 minutes."
    assert [d for d in find_conflicts([a, b]) if "hour" in d.detail or "minute" in d.detail] == []


def test_opposed_polarity_on_a_related_pair_is_a_conflict():
    a = "The system shall disclose the assigned risk category to the customer."
    b = "The system shall not disclose the assigned risk category to the customer."
    defects = find_conflicts([a, b])
    assert any(d.kind == "conflict" for d in defects)


def test_unrelated_requirements_do_not_conflict_on_polarity():
    """A negation somewhere else in the set is not a disagreement."""
    a = "The system shall encrypt customer information in transit."
    b = "The system shall not permit an unauthenticated session to resume."
    assert find_conflicts([a, b]) == []


def test_a_quantity_no_criterion_verifies_is_incomplete():
    defects = find_incompleteness([RETAIN_5Y], [["records are retained"]])
    assert len(defects) == 1
    assert "5 year" in defects[0].detail


def test_a_verified_quantity_is_not_flagged():
    defects = find_incompleteness(
        [RETAIN_5Y], [["records are still retrievable 5 years after cessation"]]
    )
    assert defects == []


def test_a_requirement_with_no_quantity_is_not_flagged():
    """This check is about untested numbers, not about missing criteria at all -
    that is a separate, per-statement defect."""
    assert find_incompleteness([ENCRYPT], [[]]) == []


def test_similarity_is_explicable_by_shared_words():
    assert similarity(RETAIN_5Y, RETAIN_5Y) == 1.0
    assert similarity(SCREEN, ENCRYPT) < 0.3
    assert similarity(SCREEN, SCREEN_REWORDED) > 0.7


def test_duplicates_are_not_also_reported_as_conflicts():
    """One finding per problem, or a reviewer reads the same pair twice."""
    found = analyse_set([RETAIN_5Y, RETAIN_5Y], [[], []])
    kinds = {d.kind for d in found if d.right is not None}
    assert "conflict" not in kinds
