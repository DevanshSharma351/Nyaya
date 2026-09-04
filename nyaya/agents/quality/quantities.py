"""Detect quantities a requirement asserts but its source never supplied.

This guard exists because of a measured failure, not a hypothetical one. Asked
to remove vague language from "make onboarding as quick as possible", the model
produced:

    The system shall limit the onboarding process to no more than three
    distinct user actions.

The stakeholder never said three. **Pressure to eliminate vagueness was
satisfied by inventing specificity** - and the fabricated version is more
dangerous than the vague original, because it reads as precise, passes every
ambiguity check, and would be baselined and built.

So every quantity in a requirement must trace to the source text. Quantities are
compared after normalisation, since a stakeholder writes "five years" and a model
writes "5 years".

Deliberately narrow: it checks *quantities*, which are objectively present or
absent in the source. It does not attempt to judge invented prose, which is the
LLM reviewer's job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NUMBER_WORDS: dict[str, str] = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "fifteen": "15",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
    "hundred": "100",
    "thousand": "1000",
}

# Numerals that are identifiers rather than thresholds: a cited clause, a named
# cryptographic standard, an ISO reference. These name something external
# instead of asserting a magnitude, so they are not fabricated quantities.
_IDENTIFIER = re.compile(
    r"""(?ix)
    \b(?:
        (?:AES|SHA|RSA|TLS|ECDSA|HMAC)[- ]?\d+     # crypto standards
      | ISO[/ ]?(?:IEC[/ ]?)?\d+                    # ISO references
      | (?:PCI[- ]?DSS|NIST|SOC)\s*\d*
      | (?:section|clause|article|rule|regulation|paragraph)\s+\d+[a-z]?
      | [A-Z]{2,}[-]\w*\d+                           # requirement / doc refs
      | \d{1,2}:\d{2}                                # times
    )\b
    """
)

_UNITS = (
    r"%|percent|percentile|"
    r"seconds?|secs?|minutes?|mins?|hours?|days?|weeks?|months?|years?|"
    r"times?|attempts?|characters?|digits?|items?|steps?|actions?|records?|"
    r"bits?|bytes?|users?|failures?|retries|retr(?:y|ies)"
)

# A unit may be separated from its number by modifiers - "three distinct user
# actions", "5 calendar days". Up to three intervening words are tolerated;
# beyond that the association is too weak to be confident about.
_GAP = r"(?:\s+[\w-]+){0,3}\s*"

_QUANTITY = re.compile(
    rf"""(?ix)
    (?<!\w)
    (?P<token>
        (?P<num>\d+(?:[.,]\d+)?)
      | (?P<word>zero|one|two|three|four|five|six|seven|eight|nine|ten|
            eleven|twelve|fifteen|twenty|thirty|forty|fifty|sixty|seventy|
            eighty|ninety|hundred|thousand)
    )
    (?:{_GAP}(?P<unit>{_UNITS})(?!\w))?
    """,
)

# Bare small integers that are almost never thresholds in requirement prose.
_UNITLESS_NOISE = {"0", "1"}


@dataclass(frozen=True, slots=True)
class Quantity:
    """A magnitude asserted in text."""

    raw: str
    value: str
    unit: str | None
    start: int
    end: int

    @property
    def normalised(self) -> str:
        """Comparable form: numeric value plus singular unit."""
        unit = (self.unit or "").lower().rstrip("s")
        unit = {"sec": "second", "min": "minute", "percent": "%"}.get(unit, unit)
        return f"{self.value}:{unit}"


def extract_quantities(text: str) -> list[Quantity]:
    """Find every quantity in `text`, skipping identifiers."""
    masked = _IDENTIFIER.sub(lambda m: " " * len(m.group(0)), text)

    found: list[Quantity] = []
    for match in _QUANTITY.finditer(masked):
        if match.group("num") is not None:
            value = match.group("num").replace(",", "")
        else:
            value = NUMBER_WORDS[match.group("word").lower()]
        unit = match.group("unit")

        # A bare 0 or 1 with no unit is almost always ordinary prose ("one of
        # the following"), not an asserted threshold.
        if unit is None and value in _UNITLESS_NOISE:
            continue

        found.append(
            Quantity(
                raw=text[match.start() : match.end()].strip(),
                value=value,
                unit=unit,
                start=match.start(),
                end=match.end(),
            )
        )
    return found


def unsupported_quantities(statement: str, source_text: str) -> list[Quantity]:
    """Quantities asserted in `statement` that `source_text` does not supply."""
    supported = {q.normalised for q in extract_quantities(source_text)}
    # Also accept a bare value whose unit differs, e.g. source "5 years",
    # statement "5-year". The magnitude is what the stakeholder committed to.
    supported_values = {q.value for q in extract_quantities(source_text)}

    return [
        q
        for q in extract_quantities(statement)
        if q.normalised not in supported and q.value not in supported_values
    ]


__all__ = ["NUMBER_WORDS", "Quantity", "extract_quantities", "unsupported_quantities"]
