"""Deterministic ambiguity detection.

Runs before any model. Three reasons it goes first:

1. **It is free and instant**, so it can run on every requirement on every edit.
2. **It is reproducible.** The same statement yields the same findings on every
   run, which matters when a finding is part of an audit record.
3. **It gives the extraction agent specific, actionable feedback** - "the word
   'appropriate' is unverifiable, state the threshold" - rather than an
   unfalsifiable request to be clearer.

The categories follow long-standing requirements-engineering practice (the
INCOSE and IEEE 830 guidance on ambiguous language). The LLM handles only what
remains: semantic ambiguity that no word list can catch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from nyaya.core.enums import Severity


class AmbiguityKind(StrEnum):
    VAGUE_QUALIFIER = "vague_qualifier"
    """Unverifiable adjectives and adverbs - 'appropriate', 'sufficient'."""

    UNQUANTIFIED = "unquantified"
    """A comparative or bound with no number - 'fast', 'minimal', 'as soon as'."""

    OPTIONALITY = "optionality"
    """Words that make the obligation discretionary - 'if possible', 'as needed'."""

    UNDEFINED_PRONOUN = "undefined_pronoun"
    """A referent that cannot be resolved from the statement alone."""

    OPEN_ENDED = "open_ended"
    """Unbounded lists - 'etc.', 'and so on', 'including but not limited to'."""

    PASSIVE_ACTOR = "passive_actor"
    """Passive voice hiding who is responsible."""

    SUPERLATIVE = "superlative"
    """Absolutes that cannot be tested - 'all', 'always', 'never', 'best'."""


# Each entry maps a category to the terms that signal it. Matching is
# whole-word and case-insensitive.
LEXICON: dict[AmbiguityKind, tuple[str, ...]] = {
    AmbiguityKind.VAGUE_QUALIFIER: (
        "appropriate",
        "adequate",
        "sufficient",
        "reasonable",
        "suitable",
        "acceptable",
        "satisfactory",
        "proper",
        "relevant",
        "significant",
        "substantial",
        "normal",
        "typical",
        "standard",
        "robust",
        "seamless",
        "user-friendly",
        "intuitive",
        "efficient",
        "effective",
        "flexible",
        "state of the art",
        "best practice",
    ),
    AmbiguityKind.UNQUANTIFIED: (
        "fast",
        "quickly",
        "rapidly",
        "slow",
        "large",
        "small",
        "minimal",
        "maximal",
        "many",
        "few",
        "several",
        "some",
        "most",
        "high",
        "low",
        "quick",
        "timely",
        "promptly",
        "immediately",
        "soon",
        "periodically",
        "regularly",
        "frequently",
        "occasionally",
        "up to date",
        "as soon as possible",
        "in a timely manner",
        "near real time",
    ),
    AmbiguityKind.OPTIONALITY: (
        "if possible",
        "if practical",
        "if needed",
        "as needed",
        "as required",
        "as appropriate",
        "where possible",
        "where applicable",
        "may",
        "optionally",
        "preferably",
        "ideally",
        "to the extent possible",
    ),
    AmbiguityKind.UNDEFINED_PRONOUN: (
        "it",
        "they",
        "them",
        "this",
        "that",
        "these",
        "those",
        "such",
    ),
    AmbiguityKind.OPEN_ENDED: (
        "etc",
        "etc.",
        "and so on",
        "and so forth",
        "among others",
        "including but not limited to",
        "such as",
        "e.g.",
        "and/or",
    ),
    AmbiguityKind.SUPERLATIVE: (
        "all",
        "any",
        "every",
        "always",
        "never",
        "none",
        "best",
        "worst",
        "optimal",
        "maximum",
        "minimum",
        "completely",
        "fully",
        "totally",
        "100%",
    ),
}

# Guidance shown to a human, and fed back to the extraction agent on a retry.
REMEDY: dict[AmbiguityKind, str] = {
    AmbiguityKind.VAGUE_QUALIFIER: "replace with a stated threshold, standard or measurable criterion",
    AmbiguityKind.UNQUANTIFIED: "state the number, unit and measurement point (e.g. 'within 2 seconds at the 95th percentile')",
    AmbiguityKind.OPTIONALITY: "state the condition explicitly, or drop the requirement - a discretionary obligation cannot be verified",
    AmbiguityKind.UNDEFINED_PRONOUN: "name the referent, so the statement stands alone without its context",
    AmbiguityKind.OPEN_ENDED: "enumerate the list exhaustively, or cite the source that defines it",
    AmbiguityKind.PASSIVE_ACTOR: "name the responsible actor - passive voice hides who must act",
    AmbiguityKind.SUPERLATIVE: "bound the scope, or state how the absolute will be demonstrated",
}

_PASSIVE = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(\w+(?:ed|en))\b(?!\s+by\b)",
    re.I,
)

# The leading conditional clause of an EARS statement. Passive voice inside it
# describes a *state or trigger*, not an obligation, so it hides no responsible
# actor: "While a customer is categorised as high risk, the system shall ...".
# Flagging it would penalise correctly-formed requirements, and a linter that
# fires on good input is one people learn to ignore.
_CONDITION_CLAUSE = re.compile(r"^\s*(?:when|while|if|where|upon|on)\b.*?,", re.I)

# Multi-word terms of art whose components would otherwise trip the lexicon.
# "high risk" is a defined regulatory category, not a vague qualifier; the
# regulation itself supplies its meaning.
DEFINED_TERMS: tuple[str, ...] = (
    "high risk",
    "medium risk",
    "low risk",
    "higher risk",
    "high value",
    "senior management",
    "beneficial owner",
    "politically exposed person",
    "officially valid document",
    "customer due diligence",
    "enhanced due diligence",
    "simplified due diligence",
    "know your customer",
    "suspicious transaction",
    "designated person",
    "data fiduciary",
    "data principal",
    "personal data breach",
    "supervisory authority",
    "state of the art",
)

_DEFINED = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(t) for t in sorted(DEFINED_TERMS, key=len, reverse=True))
    + r")(?!\w)",
    re.I,
)


# Not every ambiguity is equally damaging, and treating them alike produces a
# wall of findings that reviewers stop reading. Severity is what lets the
# extraction agent block on the ones that make a requirement untestable while
# merely noting the rest.
SEVERITY: dict[AmbiguityKind, Severity] = {
    AmbiguityKind.VAGUE_QUALIFIER: Severity.MAJOR,
    AmbiguityKind.UNQUANTIFIED: Severity.MAJOR,
    AmbiguityKind.OPTIONALITY: Severity.MAJOR,
    AmbiguityKind.OPEN_ENDED: Severity.MAJOR,
    AmbiguityKind.PASSIVE_ACTOR: Severity.MINOR,
    AmbiguityKind.UNDEFINED_PRONOUN: Severity.MINOR,
    # Superlatives are frequently correct once scope is bounded elsewhere in the
    # statement ("every high risk customer"), so they are reported, not blocked.
    AmbiguityKind.SUPERLATIVE: Severity.INFO,
}


@dataclass(slots=True)
class Finding:
    """One ambiguity detected in a statement."""

    kind: AmbiguityKind
    term: str
    start: int
    end: int
    remedy: str
    severity: Severity = Severity.MINOR

    @property
    def blocking(self) -> bool:
        """Whether this defect makes the requirement untestable as written."""
        return self.severity in {Severity.MAJOR, Severity.BLOCKER}

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.kind.value}: {self.term!r} - {self.remedy}"


def _compile() -> dict[AmbiguityKind, re.Pattern[str]]:
    compiled: dict[AmbiguityKind, re.Pattern[str]] = {}
    for kind, terms in LEXICON.items():
        # Longest first, so "as soon as possible" wins over "soon".
        ordered = sorted(terms, key=len, reverse=True)
        alternation = "|".join(re.escape(t) for t in ordered)
        compiled[kind] = re.compile(rf"(?<!\w)({alternation})(?!\w)", re.I)
    return compiled


_COMPILED = _compile()


def scan(statement: str) -> list[Finding]:
    """Report every ambiguity term in `statement`, without overlaps.

    Spans covered by a defined regulatory term are excluded first, so the
    components of a term of art are never reported as ambiguous.
    """
    findings: list[Finding] = []
    # Seeding `claimed` with the defined-term spans suppresses any finding that
    # falls inside one, using the same overlap check as everything else.
    claimed: list[tuple[int, int]] = [m.span() for m in _DEFINED.finditer(statement)]

    condition = _CONDITION_CLAUSE.match(statement)
    condition_end = condition.end() if condition else 0

    for kind, pattern in _COMPILED.items():
        for match in pattern.finditer(statement):
            span = (match.start(1), match.end(1))
            if any(s < span[1] and span[0] < e for s, e in claimed):
                continue
            claimed.append(span)
            findings.append(
                Finding(
                    kind=kind,
                    term=match.group(1),
                    start=span[0],
                    end=span[1],
                    remedy=REMEDY[kind],
                    severity=SEVERITY[kind],
                )
            )

    for match in _PASSIVE.finditer(statement):
        span = (match.start(), match.end())
        if span[0] < condition_end:
            continue  # passive inside a trigger/state clause is correct form
        if any(s < span[1] and span[0] < e for s, e in claimed):
            continue
        claimed.append(span)
        findings.append(
            Finding(
                kind=AmbiguityKind.PASSIVE_ACTOR,
                term=match.group(0),
                start=span[0],
                end=span[1],
                remedy=REMEDY[AmbiguityKind.PASSIVE_ACTOR],
                severity=SEVERITY[AmbiguityKind.PASSIVE_ACTOR],
            )
        )

    return sorted(findings, key=lambda f: f.start)


def summarise(findings: list[Finding], *, blocking_only: bool = False) -> str:
    """Render findings as feedback for a model retry or a human reviewer."""
    selected = [f for f in findings if f.blocking] if blocking_only else findings
    if not selected:
        return "no lexical ambiguity detected"
    return "; ".join(f"{f.term!r} ({f.kind.value}) - {f.remedy}" for f in selected)


def blocking(findings: list[Finding]) -> list[Finding]:
    """Only the findings that make a requirement untestable."""
    return [f for f in findings if f.blocking]


__all__ = [
    "DEFINED_TERMS",
    "LEXICON",
    "REMEDY",
    "SEVERITY",
    "AmbiguityKind",
    "Finding",
    "blocking",
    "scan",
    "summarise",
]
