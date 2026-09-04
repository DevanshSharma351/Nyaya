"""Confidence fusion.

Confidence is **computed from independent signals, never self-reported**.
Language models are poorly calibrated when asked how sure they are, and a
self-reported score is not independent evidence about its own output - it is
another output from the same process that produced the claim.

Four signals, each measuring something the others cannot:

| signal | what it measures | failure it catches |
|---|---|---|
| retrieval | was the right clause even available | the claim was made without evidence in reach |
| entailment | does the clause oblige the claim | a plausible but irrelevant citation |
| validation | did the deterministic rules accept it | a citation that resolves to nothing |
| consistency | is the answer stable across samples | a guess the model would not repeat |

Components are stored alongside the fused score so a low value can be
*explained* — "the citation does not entail the claim" is actionable in a way
that "confidence 0.41" is not — and so each component's calibration can be
measured separately during evaluation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

# Weights. Entailment carries the most because it is the only signal that
# directly tests the claim against its cited authority; retrieval scores merely
# say something topically similar was found. Validation is binary and acts more
# as a gate than a gradient.
WEIGHTS: dict[str, float] = {
    "retrieval": 0.20,
    "entailment": 0.40,
    "validation": 0.25,
    "consistency": 0.15,
}

# Below this a claim must not be presented as supported; it is routed for human
# review instead. Deliberately high: the cost of a wrong compliance mapping that
# looks confident far exceeds the cost of a correct one sent for review.
REVIEW_THRESHOLD = 0.60


@dataclass(slots=True)
class ConfidenceComponents:
    """The independent signals feeding a confidence score."""

    retrieval: float = 0.0
    """Reranker or fused retrieval score for the supporting clause, in [0,1]."""

    entailment: float = 0.0
    """NLI probability that the clause entails the claim."""

    validation: float = 0.0
    """1.0 if every deterministic check passed, 0.0 otherwise."""

    consistency: float = 0.0
    """Agreement across repeated samples, in [0,1]."""

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class Confidence:
    """A fused score with its components and the reason for any shortfall."""

    score: float
    components: ConfidenceComponents
    reasons: list[str]

    @property
    def needs_review(self) -> bool:
        return self.score < REVIEW_THRESHOLD

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "components": self.components.as_dict(),
            "reasons": self.reasons,
            "needs_review": self.needs_review,
        }


def fuse(components: ConfidenceComponents) -> Confidence:
    """Combine signals into one score, recording why it is not higher."""
    score = sum(WEIGHTS[name] * value for name, value in components.as_dict().items())

    reasons: list[str] = []
    if components.validation < 1.0:
        reasons.append("a deterministic validation check failed")
    if components.entailment < 0.5:
        reasons.append("the cited clause does not clearly entail the claim")
    if components.retrieval < 0.3:
        reasons.append("no closely matching clause was retrieved")
    if components.consistency < 0.6:
        reasons.append("the answer was not stable across repeated samples")

    return Confidence(score=round(score, 4), components=components, reasons=reasons)


def agreement(samples: list[str]) -> float:
    """Fraction of samples agreeing with the most common answer.

    Self-consistency across independent samples is genuinely independent of the
    model's own confidence: a claim it would not reproduce is one it guessed.
    """
    if not samples:
        return 0.0
    counts: dict[str, int] = {}
    for sample in samples:
        key = " ".join(sample.split()).lower()
        counts[key] = counts.get(key, 0) + 1
    return max(counts.values()) / len(samples)


__all__ = [
    "REVIEW_THRESHOLD",
    "WEIGHTS",
    "Confidence",
    "ConfidenceComponents",
    "agreement",
    "fuse",
]
