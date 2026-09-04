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

# Corroboration weights. These modulate a score that entailment has already
# bounded; they never establish confidence on their own.
CORROBORATION_WEIGHTS: dict[str, float] = {
    "retrieval": 0.55,
    "consistency": 0.45,
}

# The share of the score that entailment alone commands. The remainder is what
# corroborating signals can add, so a well-entailed citation with weak retrieval
# still scores well while a poorly-entailed one cannot be rescued.
ENTAILMENT_SHARE = 0.70

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
    """Combine signals into one score, recording why it is not higher.

    **Gated, not a weighted sum.** A weighted sum was measured on the labelled
    citation set and found badly miscalibrated (ECE 0.276): retrieval,
    validation and consistency together gave every proposal a floor of 0.52
    *regardless of entailment*, so a citation with zero entailment still scored
    0.522. The [0.4,0.6) confidence band held 38 citations of which only 18 %
    were genuine - confidently wrong exactly where a reviewer would trust it.

    So the structure mirrors what the signals mean:

    - **validation is a gate.** It records objective facts - the citation
      resolves, the quotation was copied. If those fail, nothing else matters
      and the score is zero.
    - **entailment bounds the score.** It is the only signal that tests the
      claim against its cited authority. A citation the clause does not oblige
      cannot be confident however well it was retrieved.
    - **retrieval and consistency corroborate.** They modulate within the range
      entailment permits; they cannot establish confidence on their own.
    """
    if components.validation <= 0.0:
        return Confidence(
            score=0.0,
            components=components,
            reasons=["a deterministic validation check failed"],
        )

    corroboration = (
        CORROBORATION_WEIGHTS["retrieval"] * components.retrieval
        + CORROBORATION_WEIGHTS["consistency"] * components.consistency
    )
    score = components.entailment * (
        ENTAILMENT_SHARE + (1.0 - ENTAILMENT_SHARE) * corroboration
    )

    reasons: list[str] = []
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
    "CORROBORATION_WEIGHTS",
    "ENTAILMENT_SHARE",
    "REVIEW_THRESHOLD",
    "Confidence",
    "ConfidenceComponents",
    "agreement",
    "fuse",
]
