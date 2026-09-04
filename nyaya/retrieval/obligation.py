"""Two-signal obligation checking.

Deciding whether a clause obliges a requirement is the load-bearing judgement in
this system, and a single model was measured to be insufficient for it. Two
independent models are used instead, and **their agreement is what licenses
auto-acceptance**.

Measured over 49 labelled (requirement, clause) pairs:

| signal | AUC | precision | recall | false confirmations |
|---|---|---|---|---|
| NLI entailment (DeBERTa-MNLI) | 0.796 | 0.909 | 0.588 | 1 |
| cross-encoder relevance | **0.910** | 0.923 | 0.706 | 1 |
| **both agreeing** | — | **1.000** | 0.529 | **0** |

Two things that measurement settled:

**The cross-encoder is the better single signal**, despite being loaded for
retrieval rather than chosen for this. It is a large model trained on relevance
across many domains, where the NLI model is trained on a narrow entailment task
in a register regulatory text does not share.

**Agreement is worth more than either alone.** The models fail differently - one
on general-to-specific obligations, the other on topical adjacency - so requiring
both removes every false confirmation on the labelled set. That is the property
an auto-accept gate needs; a tier that is merely *usually* right still ships
fabricated compliance claims.

The outcome is three tiers rather than a threshold, because the useful question
is not "is this citation good" but "what should happen to it now".
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from nyaya.retrieval import nli
from nyaya.retrieval.hybrid import Retrieved
from nyaya.retrieval.rerank import available as reranker_available
from nyaya.retrieval.rerank import rerank_sync

# Thresholds from the sweep in `nyaya.eval.obligation_eval`. The agreement
# thresholds are lower than either signal's solo operating point, because
# requiring both already supplies the precision that a high solo bar was buying.
NLI_AGREE = 0.20
RERANK_AGREE = 0.30

# A single signal strong enough to rank a citation high in the review queue,
# though not to accept it unreviewed.
RERANK_STRONG = 0.70


class ObligationTier(StrEnum):
    """What should happen to this citation."""

    CONFIRMED = "confirmed"
    """Both signals agree. Measured precision 1.000 - safe to accept unreviewed."""

    LIKELY = "likely"
    """One signal is confident. Measured purity 0.667 - review, ranked high."""

    UNCONFIRMED = "unconfirmed"
    """Neither signal confirms. Measured purity 0.118 - review, ranked low."""

    CONFLICTING = "conflicting"
    """The clause appears to contradict the requirement. A finding, not a doubt."""


@dataclass(slots=True)
class ObligationCheck:
    tier: ObligationTier
    entailment: float
    relevance: float
    contradiction: float = 0.0
    verified: bool = True
    """False when a model was unavailable, so the tier reflects missing evidence
    rather than measured absence of obligation."""

    @property
    def auto_acceptable(self) -> bool:
        return self.verified and self.tier is ObligationTier.CONFIRMED

    @property
    def review_priority(self) -> int:
        """Ordering for the human review queue; lower is more urgent to see."""
        return {
            ObligationTier.CONFLICTING: 0,
            ObligationTier.LIKELY: 1,
            ObligationTier.UNCONFIRMED: 2,
            ObligationTier.CONFIRMED: 3,
        }[self.tier]

    def explain(self) -> str:
        return {
            ObligationTier.CONFIRMED: (
                f"both checks agree the clause obliges this requirement "
                f"(entailment {self.entailment:.2f}, relevance {self.relevance:.2f})"
            ),
            ObligationTier.LIKELY: (
                f"one check supports the obligation but the other does not "
                f"(entailment {self.entailment:.2f}, relevance {self.relevance:.2f}); "
                f"human confirmation required"
            ),
            ObligationTier.UNCONFIRMED: (
                f"neither check confirms an obligation "
                f"(entailment {self.entailment:.2f}, relevance {self.relevance:.2f}); "
                f"the citation may still be correct but is unsupported by evidence here"
            ),
            ObligationTier.CONFLICTING: (
                f"the clause appears to contradict the requirement "
                f"(contradiction {self.contradiction:.2f})"
            ),
        }[self.tier]


def check_sync(clause: Retrieved, requirement: str) -> ObligationCheck:
    """Assess whether `clause` obliges `requirement` using both signals."""
    premise = clause.contextual
    verdict = nli.check_sync(premise, requirement)

    # The cross-encoder is scored against the normalised obligation claim, which
    # measured marginally better than the raw requirement (AUC 0.910 vs 0.908)
    # and keeps both signals reading the same framing.
    relevance = 0.0
    verified = verdict.verified
    if reranker_available():
        claim = nli.to_obligation_claim(requirement)
        scored = rerank_sync(claim, [clause], top_n=1)
        # bge-reranker applies a sigmoid internally, so its output is already a
        # probability in [0,1]. Squashing it again collapsed the range to
        # [0.50, 0.73] and made the agreement threshold pass everything - the
        # auto-accept tier admitted a false confirmation as a result.
        relevance = scored[0].rerank_score or 0.0
    else:
        verified = False

    contradiction = verdict.score if verdict.relation.value == "contradicts" else 0.0
    if verdict.verified and contradiction > 0.8:
        tier = ObligationTier.CONFLICTING
    elif verdict.entailment_score >= NLI_AGREE and relevance >= RERANK_AGREE:
        tier = ObligationTier.CONFIRMED
    elif relevance >= RERANK_STRONG or verdict.entailment_score >= NLI_AGREE:
        tier = ObligationTier.LIKELY
    else:
        tier = ObligationTier.UNCONFIRMED

    return ObligationCheck(
        tier=tier,
        entailment=verdict.entailment_score,
        relevance=relevance,
        contradiction=contradiction,
        verified=verified,
    )


async def check(clause: Retrieved, requirement: str) -> ObligationCheck:
    """Async wrapper; both models are compute-bound."""
    return await asyncio.to_thread(check_sync, clause, requirement)


__all__ = [
    "NLI_AGREE",
    "RERANK_AGREE",
    "RERANK_STRONG",
    "ObligationCheck",
    "ObligationTier",
    "check",
    "check_sync",
]
