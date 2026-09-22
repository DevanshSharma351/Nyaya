"""The repair pass must never lose a requirement.

It used to. The repair prompt says "rewrite only the statements listed below",
the model obeyed and returned only those, and the pipeline replaced the whole
set with what came back - so a brief containing thirteen obligations extracted
thirteen requirements and then reported two. The suite passed throughout,
because every test used an input small enough that nothing was flagged.
"""

from __future__ import annotations

from nyaya.agents.extraction import _clean_repair, _problem_list
from nyaya.agents.schemas import RepairedStatement
from nyaya.core.enums import Severity


class _Defect:
    def __init__(self, severity: Severity, detail: str = "not testable") -> None:
        self.severity = severity
        self.detail = detail


class _Requirement:
    def __init__(self, statement: str) -> None:
        self.statement = statement


class _Analysed:
    def __init__(self, statement: str, defects: list[_Defect]) -> None:
        self.requirement = _Requirement(statement)
        self.defects = defects


def test_problem_positions_point_back_at_the_requirements():
    """Problem n belongs to requirement flagged[n-1]; that is the whole splice."""
    analysed = [
        _Analysed("clean one", []),
        _Analysed("bad one", [_Defect(Severity.MAJOR)]),
        _Analysed("clean two", []),
        _Analysed("bad two", [_Defect(Severity.BLOCKER)]),
    ]
    problems, flagged = _problem_list(analysed)

    assert len(problems) == 2
    assert flagged == [1, 3]
    assert "bad one" in problems[0]
    assert "bad two" in problems[1]


def test_minor_defects_are_not_sent_for_repair():
    """Repair is for blocking problems; churning on minor ones invites drift."""
    problems, flagged = _problem_list([_Analysed("x", [_Defect(Severity.MINOR)])])
    assert problems == []
    assert flagged == []


def test_a_repair_index_is_one_based_and_matches_the_rendered_list():
    """The model is shown a 1-based numbered list, so the schema must agree."""
    assert RepairedStatement(index=1, statement="The system shall do x.").index == 1


def test_explanatory_bleed_is_trimmed_to_the_obligation():
    """A model told why a sentence was wrong tends to explain itself in the fix."""
    cleaned = _clean_repair(
        "The system shall re-screen all customers. The quoted source for this "
        "requirement is: 're-screened whenever the list changes'.",
        original="If the list changes, re-screen.",
    )
    assert cleaned == "The system shall re-screen all customers."


def test_a_repair_that_is_only_narration_is_rejected():
    """Better a flagged original than a mangled statement that looks repaired.

    A rejected repair leaves the defect attached and visible to a reviewer. An
    accepted mangle removes the defect from the record but not the problem.
    """
    assert _clean_repair("The quoted source is 'x'.", original="orig") is None


def test_a_repair_without_an_obligation_is_rejected():
    assert _clean_repair("This is clearer now.", original="orig") is None


def test_a_repair_identical_to_the_original_is_rejected():
    """No change means no progress; accepting it would spend another round."""
    statement = "The system shall screen the customer."
    assert _clean_repair(statement, original=statement) is None


def test_a_genuine_repair_is_accepted():
    cleaned = _clean_repair(
        "  When a customer is onboarded, the system shall screen them.  ",
        original="The system shall screen appropriately.",
    )
    assert cleaned == "When a customer is onboarded, the system shall screen them."
