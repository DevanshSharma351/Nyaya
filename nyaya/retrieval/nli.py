"""Natural language inference over citations.

This is the component that turns "the model said this clause supports the
requirement" into "the clause was checked and does support it".

A citation has three possible relations to the claim it is attached to, and the
distinction is the whole point:

- **entails** — the clause genuinely obliges what the requirement states.
- **neutral** — the clause is topically related but does not oblige it. This is
  the dangerous case, and the one a plausible-looking citation usually is: a
  clause about record retention cited for an obligation about screening.
- **contradicts** — the clause says the opposite. Rare, and always a finding.

The verdict is recorded on `Evidence.relation` *instead of* whatever the
generating model asserted. A citation the model was confident about but which
does not entail the claim counts against citation correctness, which is how
hallucinated citations get caught rather than trusted.

Runs on a small local cross-attention model. Loaded lazily; entailment checking
degrades to unverified rather than failing when it is unavailable, because a
system that cannot verify a citation must say so, not refuse to run.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from nyaya.config import get_settings
from nyaya.core.enums import EvidenceRelation

if TYPE_CHECKING:  # pragma: no cover
    from transformers import Pipeline

# Below this, an "entails" verdict is too weak to treat as support.
#
# Measured on matched and mismatched clause-requirement pairs after
# normalisation: correct citations scored at least 0.769, incorrect ones at most
# 0.043. The threshold sits in that gap, nearer the wrong-citation end because a
# false "supports" is a fabricated compliance claim, whereas a false "neutral"
# merely sends a correct citation for human review. The costs are not symmetric.
ENTAILMENT_THRESHOLD = 0.55

# Label strings vary between MNLI checkpoints; normalise defensively.
_LABEL_MAP = {
    "entailment": EvidenceRelation.SUPPORTS,
    "entail": EvidenceRelation.SUPPORTS,
    "neutral": EvidenceRelation.NEUTRAL,
    "contradiction": EvidenceRelation.CONTRADICTS,
    "contradict": EvidenceRelation.CONTRADICTS,
    "label_0": EvidenceRelation.SUPPORTS,
    "label_1": EvidenceRelation.NEUTRAL,
    "label_2": EvidenceRelation.CONTRADICTS,
}


@dataclass(slots=True)
class EntailmentVerdict:
    """The outcome of checking one (clause, claim) pair."""

    relation: EvidenceRelation
    score: float
    """Probability of the winning relation."""

    entailment_score: float
    """Probability of `entails` specifically, retained even when another label
    wins - it is the quantity confidence fusion consumes."""

    verified: bool = True
    """False when no model was available, so the verdict is `NEUTRAL` by
    default rather than by measurement. Callers must not read an unverified
    NEUTRAL as evidence of anything."""

    @property
    def supports(self) -> bool:
        return (
            self.relation is EvidenceRelation.SUPPORTS
            and self.entailment_score >= ENTAILMENT_THRESHOLD
        )


UNVERIFIED = EntailmentVerdict(
    relation=EvidenceRelation.NEUTRAL, score=0.0, entailment_score=0.0, verified=False
)


@lru_cache(maxsize=2)
def _load(model_name: str) -> Pipeline:
    from transformers import pipeline

    return pipeline(
        "text-classification",
        model=model_name,
        top_k=None,  # return the full label distribution, not just the argmax
    )


def available(model_name: str | None = None) -> bool:
    try:
        _load(model_name or get_settings().nli_model)
    except Exception:
        return False
    return True


# EARS scaffolding, stripped before entailment checking. See `to_obligation_claim`.
_EARS_LEAD = re.compile(r"^\s*(?:when|while|if|where|upon|on)\b[^,]*,\s*(?:then\s+)?", re.I)
_EARS_ACTOR = re.compile(r"^\s*(?:the\s+)?[\w \-/]{2,60}?\s+(?:shall|must|will)\s+", re.I)


def to_obligation_claim(statement: str) -> str:
    """Restate an EARS requirement as a declarative obligation.

    **This normalisation is required, not cosmetic.** MNLI models are trained on
    declarative factual pairs. An EARS statement - "When a customer is onboarded
    remotely, the system shall screen..." - reads to such a model as a
    conditional prescription about some particular system rather than a claim the
    premise could entail. Measured on a correct clause-requirement pair, the raw
    EARS form scored `contradicts` at 0.003 while the same content as a
    declarative claim scored `supports` at 0.994.

    Without this step the validator rejects correct citations, which is the worst
    available failure: it would train reviewers to override the checker.

    The conditional prefix is dropped deliberately. The question is whether the
    clause obliges the *action*; the trigger narrows when the duty applies and
    is checked separately by the rule engine.

    **The actor is dropped too**, and this was decided by measurement rather
    than taste. A requirement names the software ("the system"); a regulation
    names the institution ("the Regulated Entity"). Those subjects differ by
    design, and an NLI model reads the mismatch as evidence against entailment.
    Over matched and mismatched clause-requirement pairs:

        keeping the actor   correct min 0.404, wrong max 0.046  (separation 0.358)
        dropping the actor  correct min 0.769, wrong max 0.043  (separation 0.726)

    Dropping it doubles the margin between correct and incorrect citations
    without raising the score of a wrong one. The result reads
    ungrammatically - "It is required that screen the customer" - which does not
    trouble the model and is never shown to a user.
    """
    text = " ".join(statement.split()).rstrip(".")
    body = _EARS_LEAD.sub("", text)
    body = _EARS_ACTOR.sub("", body)
    return f"It is required that {body}."


def check_sync(
    premise: str,
    hypothesis: str,
    *,
    model_name: str | None = None,
    normalise: bool = True,
) -> EntailmentVerdict:
    """Does `premise` (the clause) entail `hypothesis` (the requirement)?

    Direction matters and is easy to get backwards. The clause is the premise:
    the question is whether the *regulation* obliges the requirement, not
    whether the requirement implies the regulation.

    `normalise` restates the hypothesis as a declarative obligation first; see
    `to_obligation_claim` for why that is necessary rather than tidy.
    """
    if normalise:
        hypothesis = to_obligation_claim(hypothesis)
    try:
        model = _load(model_name or get_settings().nli_model)
        scores = model({"text": premise, "text_pair": hypothesis})
    except Exception:
        return UNVERIFIED

    # `top_k=None` yields a list of {label, score}; some versions nest it once.
    if scores and isinstance(scores[0], list):
        scores = scores[0]

    distribution: dict[EvidenceRelation, float] = {}
    for entry in scores:
        relation = _LABEL_MAP.get(str(entry["label"]).lower())
        if relation is not None:
            distribution[relation] = float(entry["score"])

    if not distribution:
        return UNVERIFIED

    relation = max(distribution, key=lambda r: distribution[r])
    return EntailmentVerdict(
        relation=relation,
        score=distribution[relation],
        entailment_score=distribution.get(EvidenceRelation.SUPPORTS, 0.0),
    )


async def check(
    premise: str,
    hypothesis: str,
    *,
    model_name: str | None = None,
    normalise: bool = True,
) -> EntailmentVerdict:
    """Async wrapper; the model is CPU/GPU-bound so it runs off the event loop."""
    return await asyncio.to_thread(
        check_sync, premise, hypothesis, model_name=model_name, normalise=normalise
    )


async def check_many(
    pairs: list[tuple[str, str]], *, model_name: str | None = None
) -> list[EntailmentVerdict]:
    """Check several pairs, preserving order."""
    return await asyncio.to_thread(
        lambda: [check_sync(p, h, model_name=model_name) for p, h in pairs]
    )


__all__ = [
    "ENTAILMENT_THRESHOLD",
    "UNVERIFIED",
    "EntailmentVerdict",
    "available",
    "check",
    "check_many",
    "check_sync",
    "to_obligation_claim",
]
