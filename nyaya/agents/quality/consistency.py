"""Checks that only make sense across a *set* of requirements.

Every other detector in this package reads one statement at a time - is it in
EARS form, does it use a vague word, does it quote a number nobody gave. Three
of the defects the brief lists in §10 cannot be found that way at all:
duplication, conflicting expectations, and incompleteness of a set rather than
of a sentence. They are properties of the collection.

They also only started to matter once extraction worked. While a dense brief
produced two requirements there was nothing to duplicate or contradict; at
thirteen there is, and a review that hands a stakeholder the same obligation
twice, or two obligations that cannot both be satisfied, has wasted their time
in the one way it cannot afford to.

Deterministic on purpose. A model asked "are these contradictory?" produces a
confident answer either way, and the reviewer cannot tell which answers were
reasoned. Everything here is a rule that can be read, disputed and re-run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Words that carry no distinguishing weight. Kept short deliberately: an
# aggressive stop list makes unrelated requirements look similar, which is the
# failure direction that wastes a reviewer's attention.
_NOISE = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "been", "being", "by", "for", "from", "has", "have", "if", "in", "into", "is", "it", "its", "must", "of", "on", "or", "shall", "should", "that", "the", "then", "there", "these", "this", "to", "when", "where", "which", "while", "with", "within", "system"]
)

_WORD = re.compile(r"[a-z0-9][a-z0-9-]*")

# Quantities with a unit, which is what a conflicting obligation usually turns
# on: two retention periods, two timeouts, two thresholds.
_QUANTITY = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>"
    r"seconds?|minutes?|hours?|days?|weeks?|months?|years?|percent|%"
    r")\b",
    re.IGNORECASE,
)

_NEGATION = re.compile(r"\b(not|never|no longer|must not|shall not|without)\b", re.IGNORECASE)

# Above this, two requirements are saying the same thing in different words.
# Fitted by hand against extraction output rather than tuned: at 0.7 genuine
# near-duplicates were missed, at 0.9 unrelated obligations sharing a subject
# were flagged.
DUPLICATE_THRESHOLD = 0.82

# Two requirements must be talking about the same thing before a difference
# between them is a conflict rather than a coincidence.
RELATED_THRESHOLD = 0.45

_UNIT_SECONDS = {
    "second": 1, "seconds": 1,
    "minute": 60, "minutes": 60,
    "hour": 3600, "hours": 3600,
    "day": 86400, "days": 86400,
    "week": 604800, "weeks": 604800,
    "month": 2629800, "months": 2629800,
    "year": 31557600, "years": 31557600,
}


@dataclass(slots=True)
class SetDefect:
    """A defect involving two requirements, or a whole set."""

    kind: str
    """One of 'duplication', 'conflict', 'incompleteness'."""

    left: int
    right: int | None
    detail: str


def terms(statement: str) -> frozenset[str]:
    """Content words, lowercased, with noise removed."""
    return frozenset(
        word
        for word in _WORD.findall(statement.lower())
        if word not in _NOISE and len(word) > 2
    )


def similarity(left: str, right: str) -> float:
    """Jaccard overlap of content words.

    Chosen over an embedding because it is explicable. A reviewer told two
    requirements are duplicates can be shown the words they share; told a cosine
    distance, they can only be asked to agree.
    """
    a, b = terms(left), terms(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _quantities(statement: str) -> list[tuple[float, str]]:
    found = []
    for match in _QUANTITY.finditer(statement):
        unit = match.group("unit").lower().rstrip("s") or match.group("unit").lower()
        found.append((float(match.group("value")), unit))
    return found


def _comparable(left: tuple[float, str], right: tuple[float, str]) -> bool:
    """Whether two quantities measure the same kind of thing."""
    left_unit, right_unit = left[1], right[1]
    if left_unit == right_unit:
        return True
    return (
        left_unit in _UNIT_SECONDS
        and right_unit in _UNIT_SECONDS
    )


def _to_seconds(quantity: tuple[float, str]) -> float | None:
    value, unit = quantity
    factor = _UNIT_SECONDS.get(unit)
    return value * factor if factor else None


def _conflict_between(left: str, right: str) -> str | None:
    """Why these two cannot both hold, or None.

    Checked before duplication, and without an upper bound on similarity. The
    first version had it the other way round and got both cases wrong: two
    requirements identical except for a retention period scored as duplicates,
    and so did "shall disclose" against "shall not disclose", because the word
    that reverses the meaning is one character of noise in a shared sentence.
    Near-identical wording makes a conflict *more* likely, not less - it means
    two people wrote the same obligation and disagreed about the value.
    """
    for one in _quantities(left):
        for other in _quantities(right):
            if not _comparable(one, other):
                continue
            left_seconds, right_seconds = _to_seconds(one), _to_seconds(other)
            same = (
                left_seconds == right_seconds
                if left_seconds is not None and right_seconds is not None
                else one[0] == other[0]
            )
            if not same:
                return (
                    f"gives {other[0]:g} {other[1]}(s) where the other gives "
                    f"{one[0]:g} {one[1]}(s) for what reads as the same obligation. "
                    "Both cannot hold; a stakeholder must decide which applies."
                )

    if bool(_NEGATION.search(left)) != bool(_NEGATION.search(right)):
        return (
            "reads as the opposite: one permits or requires what the other "
            "forbids. Neither is wrong alone, so this needs a stakeholder "
            "decision rather than a rewrite."
        )
    return None


def find_duplicates(statements: list[str]) -> list[SetDefect]:
    """Pairs that state the same obligation.

    Reported once per pair, against the later of the two, because the earlier is
    the one a reviewer will keep. A pair that conflicts is never a duplicate,
    however similar the wording: the difference is the whole point of it.
    """
    defects: list[SetDefect] = []
    for i in range(len(statements)):
        for j in range(i + 1, len(statements)):
            score = similarity(statements[i], statements[j])
            if score < DUPLICATE_THRESHOLD:
                continue
            if _conflict_between(statements[i], statements[j]):
                continue
            shared = sorted(terms(statements[i]) & terms(statements[j]))[:6]
            defects.append(
                SetDefect(
                    kind="duplication",
                    left=j,
                    right=i,
                    detail=(
                        f"states the same obligation as requirement {i + 1} "
                        f"({score:.0%} of content words shared: {', '.join(shared)}). "
                        "Keep one, or state what distinguishes them."
                    ),
                )
            )
    return defects


def find_conflicts(statements: list[str]) -> list[SetDefect]:
    """Pairs that cannot both be satisfied.

    Two shapes, both deterministic:

    *Incompatible quantities.* Two requirements about the same subject giving
    different values for the same kind of measure - two retention periods, two
    timeouts. This is the shape that actually appears in financial briefs, where
    one team says five years and another says seven.

    *Opposed polarity.* Two closely related requirements, one of which negates.
    "shall disclose" against "shall not disclose" is a conflict a reviewer must
    settle, and neither statement is wrong on its own.

    Deliberately not attempted: contradiction by meaning. The entailment model
    could be asked, but at thirteen requirements that is seventy-eight pairs and
    a model that answers confidently either way. A missed conflict is recoverable
    at review; a confident false one sends someone to argue with a stakeholder
    about a disagreement that does not exist.
    """
    defects: list[SetDefect] = []
    for i in range(len(statements)):
        for j in range(i + 1, len(statements)):
            # Related is enough. There is no upper bound: the more alike two
            # statements are, the more likely a difference between them is a
            # disagreement rather than a coincidence.
            if similarity(statements[i], statements[j]) < RELATED_THRESHOLD:
                continue
            reason = _conflict_between(statements[i], statements[j])
            if reason is None:
                continue
            defects.append(
                SetDefect(
                    kind="conflict",
                    left=j,
                    right=i,
                    detail=f"{reason} (compare requirement {i + 1})",
                )
            )
    return defects


def find_incompleteness(
    statements: list[str], acceptance_criteria: list[list[str]]
) -> list[SetDefect]:
    """Requirements stating a measure with no criterion that verifies it.

    Distinct from the existing "no acceptance criteria" check, which fires on
    every requirement lacking them. This one fires where the statement contains
    a specific quantity and nothing verifies it - the case where a number was
    agreed and then never tested, which reads as complete and is not.
    """
    defects: list[SetDefect] = []
    for index, statement in enumerate(statements):
        quantities = _quantities(statement)
        if not quantities:
            continue
        criteria = acceptance_criteria[index] if index < len(acceptance_criteria) else []
        joined = " ".join(criteria).lower()
        unverified = [
            f"{value:g} {unit}"
            for value, unit in quantities
            if f"{value:g}" not in joined and str(int(value)) not in joined
        ]
        if unverified:
            defects.append(
                SetDefect(
                    kind="incompleteness",
                    left=index,
                    right=None,
                    detail=(
                        f"states {', '.join(unverified)} but no acceptance criterion "
                        "verifies it. A quantity nobody tests is a number that was "
                        "agreed and then not built."
                    ),
                )
            )
    return defects


def analyse_set(
    statements: list[str], acceptance_criteria: list[list[str]]
) -> list[SetDefect]:
    """Every cross-requirement check, in the order a reviewer should read them."""
    return [
        *find_duplicates(statements),
        *find_conflicts(statements),
        *find_incompleteness(statements, acceptance_criteria),
    ]


__all__ = [
    "DUPLICATE_THRESHOLD",
    "RELATED_THRESHOLD",
    "SetDefect",
    "analyse_set",
    "find_conflicts",
    "find_duplicates",
    "find_incompleteness",
    "similarity",
    "terms",
]
