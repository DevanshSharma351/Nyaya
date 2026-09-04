"""EARS — Easy Approach to Requirements Syntax.

A constrained grammar for requirement statements. Its value here is not style
enforcement: **a statement matching an EARS pattern is structurally testable**,
because the pattern forces a subject, a modal obligation, and a response, and
the conditional forms force the trigger to be stated rather than implied.

"The system should be secure" matches nothing. "When a customer submits an
onboarding application, the system shall screen the applicant against the
designated-persons list before activating the account" is event-driven EARS, and
a test can be written from it directly.

Detection is deterministic and runs before any model is consulted, so the
extraction agent can be told *specifically* what is wrong with its output rather
than being asked vaguely to try harder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class EARSPattern(StrEnum):
    """The recognised EARS forms."""

    UBIQUITOUS = "ubiquitous"
    """The <system> shall <response>. An always-active obligation."""

    EVENT_DRIVEN = "event_driven"
    """When <trigger>, the <system> shall <response>."""

    STATE_DRIVEN = "state_driven"
    """While <state>, the <system> shall <response>."""

    UNWANTED = "unwanted"
    """If <condition>, then the <system> shall <response>. Error and abuse paths."""

    OPTIONAL = "optional"
    """Where <feature is included>, the <system> shall <response>."""

    COMPLEX = "complex"
    """A combination, e.g. While <state>, when <trigger>, the <system> shall ..."""

    NONE = "none"
    """Matches no pattern - not structurally testable as written."""


# Modal verbs, in descending order of obligation. Only `shall` denotes a binding
# requirement; the others are recorded so the linter can say which was used.
_MODALS = r"(?:shall|must|will|should|may|can)"
_SUBJECT = r"(?:the\s+)?[\w \-/]{2,60}?"

_PATTERNS: tuple[tuple[EARSPattern, re.Pattern[str]], ...] = (
    (
        EARSPattern.COMPLEX,
        re.compile(rf"^\s*while\s+.+?,\s*when\s+.+?,\s*{_SUBJECT}\s+{_MODALS}\s+\S.*$", re.I),
    ),
    (
        EARSPattern.UNWANTED,
        re.compile(rf"^\s*if\s+.+?,\s*(?:then\s+)?{_SUBJECT}\s+{_MODALS}\s+\S.*$", re.I),
    ),
    (
        EARSPattern.EVENT_DRIVEN,
        re.compile(rf"^\s*(?:when|upon|on)\s+.+?,\s*{_SUBJECT}\s+{_MODALS}\s+\S.*$", re.I),
    ),
    (
        EARSPattern.STATE_DRIVEN,
        re.compile(rf"^\s*while\s+.+?,\s*{_SUBJECT}\s+{_MODALS}\s+\S.*$", re.I),
    ),
    (
        EARSPattern.OPTIONAL,
        re.compile(rf"^\s*where\s+.+?,\s*{_SUBJECT}\s+{_MODALS}\s+\S.*$", re.I),
    ),
    (
        EARSPattern.UBIQUITOUS,
        re.compile(rf"^\s*{_SUBJECT}\s+{_MODALS}\s+\S.*$", re.I),
    ),
)

_MODAL_FINDER = re.compile(rf"\b{_MODALS}\b", re.I)
BINDING_MODAL = "shall"


@dataclass(slots=True)
class EARSAnalysis:
    """The outcome of checking one statement against the grammar."""

    pattern: EARSPattern
    modal: str | None
    conforms: bool
    issues: list[str]

    @property
    def is_binding(self) -> bool:
        """Whether the statement expresses a binding obligation."""
        return self.modal == BINDING_MODAL


def analyse(statement: str) -> EARSAnalysis:
    """Classify `statement` against the EARS grammar and report defects."""
    text = " ".join(statement.split())
    issues: list[str] = []

    modal_match = _MODAL_FINDER.search(text)
    modal = modal_match.group(0).lower() if modal_match else None

    pattern = EARSPattern.NONE
    for candidate, regex in _PATTERNS:
        if regex.match(text):
            pattern = candidate
            break

    if modal is None:
        issues.append(
            "no modal verb: the statement does not express an obligation (expected 'shall')"
        )
    elif modal != BINDING_MODAL:
        issues.append(
            f"non-binding modal {modal!r}: use 'shall' for a requirement, or "
            f"reclassify this as an assumption or a note"
        )

    if pattern is EARSPattern.NONE:
        issues.append(
            "does not match an EARS pattern: expected '<system> shall <response>', "
            "optionally prefixed by 'When/While/If/Where <condition>,'"
        )

    if _has_multiple_obligations(text):
        issues.append(
            "compound requirement: contains more than one obligation, which "
            "cannot be accepted or rejected independently - split it"
        )

    return EARSAnalysis(
        pattern=pattern,
        modal=modal,
        conforms=pattern is not EARSPattern.NONE and modal == BINDING_MODAL,
        issues=issues,
    )


def _has_multiple_obligations(text: str) -> bool:
    """Detect a statement carrying more than one testable obligation.

    A compound requirement cannot be individually approved, traced or verified:
    accepting it accepts both halves, and a test that fails cannot say which.
    Counting modals is a deliberately conservative proxy - it catches "shall X
    and shall Y" without flagging a single obligation containing the word "and".
    """
    return len(_MODAL_FINDER.findall(text)) > 1


__all__ = ["BINDING_MODAL", "EARSAnalysis", "EARSPattern", "analyse"]
