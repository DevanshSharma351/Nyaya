"""An LLM second opinion on citations the NLI model could not confirm.

Measurement showed the NLI validator is precise (0.909) but insensitive
(0.588), and *why*: it rejects citations where the clause states a general duty
and the requirement states a specific implementation. A general duty does not
logically entail a particular implementation, though the implementation plainly
satisfies it. **Compliance is a satisfaction relation; MNLI measures
entailment.**

A language model can be asked the right question directly. The risk is obvious -
the model that proposed the citation is not a neutral referee - so the judge is
constrained in three ways:

1. **It only sees the pair.** No candidate control list, no retrieval scores, no
   knowledge of which model proposed it. It cannot infer the expected answer.
2. **It runs only on the `needs_review` band.** Citations the NLI confirmed are
   already accepted, and objectively rejected ones are gone. The judge cannot
   overturn a deterministic fact.
3. **It must quote the obliging text.** A judge that cannot point at the words
   creating the duty has not established one, and the quotation is verified
   against the clause afterwards - the same check applied to the proposer.

Whether this actually recovers recall without importing false confirmations is
an empirical question, answered against the labelled set in
`nyaya.eval.judge_eval`.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from nyaya.config import ModelRole
from nyaya.core.enums import EvidenceRelation
from nyaya.llm import Message, get_provider

JUDGE_SYSTEM = """\
You decide whether a regulatory clause obliges a software requirement.

You will see ONE clause and ONE requirement. Answer only from the clause shown.

The question is NOT "does the clause logically entail the requirement". It is:

    Would a regulator accept this clause as the authority making this
    requirement mandatory?

That distinction matters. A clause often states a GENERAL duty while the
requirement states a SPECIFIC way of discharging it. That still counts as
obliged:

    clause:      personal data shall be protected by encryption
    requirement: the system shall encrypt identity documents in transit
    verdict:     obliges - the requirement is one way of discharging the duty

But a requirement that merely shares a TOPIC with the clause is NOT obliged:

    clause:      records shall be preserved for five years
    requirement: the system shall screen customers against sanctions lists
    verdict:     does not oblige - both concern compliance, neither obliges the other

And a requirement the clause forbids is a conflict, not a mapping:

    clause:      the risk category shall not be disclosed to the customer
    requirement: the system shall display the risk rating to the customer
    verdict:     conflicts

Be conservative. "does_not_oblige" is a correct and useful answer. A wrongly
confirmed citation will be relied upon by people who cannot re-check it.
"""


class JudgeVerdict(BaseModel):
    """A judge's assessment of one citation."""

    verdict: str = Field(
        description=(
            "Exactly one of: 'obliges' (the clause makes this requirement "
            "mandatory, including as a specific way of discharging a general "
            "duty), 'does_not_oblige' (related topic but no obligation), or "
            "'conflicts' (the requirement would breach the clause)."
        )
    )
    obliging_text: str = Field(
        description=(
            "The exact words in the clause that create the obligation, copied "
            "verbatim. Empty string if the verdict is 'does_not_oblige'."
        )
    )
    reasoning: str = Field(description="One sentence explaining the verdict.")


_VERDICT_MAP = {
    "obliges": EvidenceRelation.SUPPORTS,
    "does_not_oblige": EvidenceRelation.NEUTRAL,
    "conflicts": EvidenceRelation.CONTRADICTS,
}


@dataclass(slots=True)
class JudgeResult:
    relation: EvidenceRelation
    obliging_text: str
    reasoning: str
    quote_verified: bool
    raw_verdict: str

    @property
    def obliges(self) -> bool:
        """Whether the judge established an obligation *and* could point at it."""
        return self.relation is EvidenceRelation.SUPPORTS and self.quote_verified


async def judge(
    clause_text: str,
    requirement: str,
    *,
    role: ModelRole = ModelRole.REASONING,
) -> JudgeResult:
    """Ask whether `clause_text` obliges `requirement`."""
    provider = get_provider(role)
    completion = await provider.complete_structured(
        [
            Message(role="system", content=JUDGE_SYSTEM),
            Message(
                role="user",
                content=f"CLAUSE:\n{clause_text}\n\nREQUIREMENT:\n{requirement}",
            ),
        ],
        JudgeVerdict,
    )
    value = completion.value
    relation = _VERDICT_MAP.get(value.verdict.strip().lower(), EvidenceRelation.NEUTRAL)

    # The same standard applied to the proposing model: a claim of obligation
    # must be anchored in text that actually exists in the clause.
    quoted = " ".join(value.obliging_text.split()).lower()
    haystack = " ".join(clause_text.split()).lower()
    quote_verified = bool(quoted) and quoted in haystack

    return JudgeResult(
        relation=relation,
        obliging_text=value.obliging_text,
        reasoning=value.reasoning,
        quote_verified=quote_verified,
        raw_verdict=value.verdict,
    )


__all__ = ["JUDGE_SYSTEM", "JudgeResult", "JudgeVerdict", "judge"]
