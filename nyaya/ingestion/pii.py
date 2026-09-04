"""PII detection and reversible pseudonymisation.

Nothing sensitive reaches a model. Detected identifiers are replaced with stable
surrogates before any text leaves the process; the mapping is held in the
`PIIToken` vault so approved artefacts can be rehydrated for human readers.

Two properties matter more than raw recall:

**Surrogates are stable within a project.** The same Aadhaar number always maps
to the same token, so a model can still reason that two statements concern the
same customer without ever seeing the identifier. A random surrogate per
occurrence would destroy that coreference.

**Detection is checksum-validated where the format allows it.** Aadhaar carries a
Verhoeff check digit and PAN a positional structure; validating them turns a
loose regex into a precise recogniser and avoids masking ordinary 12-digit
numbers such as transaction references.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

# --- Verhoeff, the checksum used by Aadhaar -------------------------------
# Dihedral group D5 multiplication, permutation, and inverse tables.
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff_valid(number: str) -> bool:
    """Validate a Verhoeff checksum, as used by Aadhaar."""
    if not number.isdigit():
        return False
    check = 0
    for i, digit in enumerate(reversed(number)):
        check = _D[check][_P[i % 8][int(digit)]]
    return check == 0


def pan_valid(value: str) -> bool:
    """Validate an Indian PAN's positional structure (AAAAA9999A).

    The fourth character encodes holder type and the fifth is the surname
    initial, so a well-formed PAN is far more constrained than five letters,
    four digits and a letter.
    """
    if len(value) != 10:
        return False
    return (
        value[:5].isalpha()
        and value[5:9].isdigit()
        and value[9].isalpha()
        and value[3].upper() in "ABCFGHLJPTK"
    )


@dataclass(frozen=True, slots=True)
class Recogniser:
    """A pattern-based detector, optionally gated by a validator."""

    entity_type: str
    pattern: re.Pattern[str]
    validator: Callable[[str], bool] | None = None
    normalise: bool = False
    """Strip separators before validating - Aadhaar is written both as
    `1234 5678 9012` and `123456789012`."""


RECOGNISERS: tuple[Recogniser, ...] = (
    Recogniser(
        "IN_AADHAAR",
        re.compile(r"\b(\d{4}[\s-]?\d{4}[\s-]?\d{4})\b"),
        validator=verhoeff_valid,
        normalise=True,
    ),
    Recogniser(
        "IN_PAN",
        re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b"),
        validator=pan_valid,
    ),
    Recogniser("EMAIL_ADDRESS", re.compile(r"\b([\w.%-]+@[\w.-]+\.[A-Za-z]{2,})\b")),
    Recogniser("IN_PHONE", re.compile(r"\b((?:\+91[\s-]?)?[6-9]\d{9})\b")),
    Recogniser("IFSC_CODE", re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")),
    Recogniser(
        "CREDIT_CARD",
        re.compile(r"\b((?:\d{4}[\s-]?){3}\d{4})\b"),
        validator=lambda v: _luhn(v),
        normalise=True,
    ),
    Recogniser("IN_PASSPORT", re.compile(r"\b([A-PR-WY][0-9]{7})\b")),
    Recogniser("DATE_OF_BIRTH", re.compile(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b")),
)


def _luhn(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


@dataclass(slots=True)
class Detection:
    entity_type: str
    value: str
    start: int
    end: int
    token: str


@dataclass(slots=True)
class MaskResult:
    """Masked text plus the mapping needed to reverse it."""

    text: str
    detections: list[Detection] = field(default_factory=list)

    @property
    def mapping(self) -> dict[str, str]:
        """Surrogate token -> original value."""
        return {d.token: d.value for d in self.detections}

    @property
    def entity_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.detections:
            counts[d.entity_type] = counts.get(d.entity_type, 0) + 1
        return counts


def _surrogate(entity_type: str, value: str, salt: str) -> str:
    """Derive a stable surrogate for a value within one project.

    Keyed by a per-project salt so the same identifier yields the same token
    inside a project but is not correlatable across projects - and so the token
    itself cannot be brute-forced back to the value without the salt.
    """
    digest = hashlib.sha256(f"{salt}:{entity_type}:{value}".encode()).hexdigest()[:8]
    return f"<{entity_type}_{digest}>"


def mask(text: str, *, salt: str = "") -> MaskResult:
    """Replace detected identifiers with stable surrogates.

    Overlapping detections are resolved in favour of the longer match, so a
    card number is not partially consumed by a shorter pattern.
    """
    hits: list[tuple[int, int, str, str]] = []
    for rec in RECOGNISERS:
        for m in rec.pattern.finditer(text):
            raw = m.group(1)
            candidate = re.sub(r"[\s-]", "", raw) if rec.normalise else raw
            if rec.validator is not None and not rec.validator(candidate):
                continue
            hits.append((m.start(1), m.end(1), rec.entity_type, raw))

    # Longest match wins; ties broken by earlier start.
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    chosen: list[tuple[int, int, str, str]] = []
    last_end = -1
    for start, end, etype, raw in hits:
        if start >= last_end:
            chosen.append((start, end, etype, raw))
            last_end = end

    out: list[str] = []
    detections: list[Detection] = []
    cursor = 0
    for start, end, etype, raw in chosen:
        token = _surrogate(etype, raw, salt)
        out.append(text[cursor:start])
        out.append(token)
        detections.append(Detection(etype, raw, start, end, token))
        cursor = end
    out.append(text[cursor:])

    return MaskResult(text="".join(out), detections=detections)


def unmask(text: str, mapping: dict[str, str]) -> str:
    """Restore original values from surrogates."""
    for token, value in mapping.items():
        text = text.replace(token, value)
    return text


@lru_cache(maxsize=1)
def _presidio_analyzer():
    """Presidio's NER analyser, loaded lazily.

    Deliberately optional. The pattern recognisers above cover the structured
    identifiers that dominate eKYC and need no model; Presidio adds names,
    locations and organisations, which require spaCy. Ingestion must not fail
    outright when the model is absent, so callers fall back to patterns alone.
    """
    from presidio_analyzer import AnalyzerEngine

    return AnalyzerEngine()


def mask_with_ner(text: str, *, salt: str = "", language: str = "en") -> MaskResult:
    """Pattern masking plus Presidio NER for unstructured identifiers.

    Falls back to pattern-only masking if the spaCy pipeline is unavailable.
    """
    try:
        analyzer = _presidio_analyzer()
        results = analyzer.analyze(
            text=text, language=language, entities=["PERSON", "LOCATION", "NRP"]
        )
    except Exception:
        return mask(text, salt=salt)

    ner_spans = [(r.start, r.end, r.entity_type, text[r.start : r.end]) for r in results]

    pattern_result = mask(text, salt=salt)
    if not ner_spans:
        return pattern_result

    # Re-run over the original text with both sources merged, so offsets agree.
    combined = sorted(
        ner_spans + [(d.start, d.end, d.entity_type, d.value) for d in pattern_result.detections],
        key=lambda h: (h[0], -(h[1] - h[0])),
    )
    out: list[str] = []
    detections: list[Detection] = []
    cursor = 0
    for start, end, etype, raw in combined:
        if start < cursor:
            continue  # overlapped by a longer preceding match
        token = _surrogate(etype, raw, salt)
        out.append(text[cursor:start])
        out.append(token)
        detections.append(Detection(etype, raw, start, end, token))
        cursor = end
    out.append(text[cursor:])
    return MaskResult(text="".join(out), detections=detections)


__all__ = [
    "RECOGNISERS",
    "Detection",
    "MaskResult",
    "mask",
    "mask_with_ner",
    "pan_valid",
    "unmask",
    "verhoeff_valid",
]
