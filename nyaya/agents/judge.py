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

Whether this recovers recall without importing false confirmations was an
empirical question. **It was measured, and the answer is no.**

Over the same 49 labelled pairs:

| arm | precision | recall | false confirmations |
|---|---|---|---|
| NLI alone | 0.909 | 0.588 | **1** |
| judge alone | 0.714 | 0.882 | 6 |
| judge, quotation required | 0.786 | 0.647 | 3 |

On the 38 pairs NLI could not confirm, the judge recovered 5 correct citations
and newly confirmed 5 wrong ones - a one-for-one trade. F1 improves (0.714 to
0.789) but F1 assumes symmetric costs, and these costs are not symmetric: a
false confirmation is a fabricated compliance claim relied upon by people who
cannot re-check it, while a false rejection is a correct citation shown to a
human.

The failures are instructive. The judge confirmed `RBI-MD-KYC:16(a)` (customer
identity) for a beneficial-owner requirement, reasoning that identification "is
part of due diligence", and `GDPR:Article 32.1(c)` (restoration of availability)
for an encryption requirement, reasoning from "a general duty to implement
security measures". It generalises from a parent duty to any obligation within
its scope - which is precisely what the prompt's own concession about general
duties invited.

**So the judge does not confirm citations.** It annotates the `needs_review`
band with an opinion and a quotation for the human deciding, and has no
authority to accept. Its one demonstrated benefit is retained: requiring a
verified quotation halved its false confirmations (6 to 3), which is the same
constraint applied to the proposing model, doing the same work.
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
        """Whether the judge asserted an obligation *and* could point at it.

        Advisory only. Measured at precision 0.786 even with the quotation
        requirement, this is not accurate enough to auto-confirm a compliance
        mapping; it is a reason for a human to look, not a verdict.
        """
        return self.relation is EvidenceRelation.SUPPORTS and self.quote_verified

    def as_review_note(self) -> str:
        """The advisory line shown to whoever reviews this citation.

        Attributed explicitly, because an unattributed machine opinion in a
        review queue is indistinguishable from a verified finding, and a
        reviewer who cannot tell them apart will eventually stop checking.
        """
        verdict = {
            EvidenceRelation.SUPPORTS: "may oblige",
            EvidenceRelation.NEUTRAL: "appears not to oblige",
            EvidenceRelation.CONTRADICTS: "may conflict with",
        }[self.relation]
        anchor = (
            f' quoting "{self.obliging_text}"'
            if self.quote_verified
            else " (could not point to obliging text)"
        )
        return (
            f"AI reviewer opinion, unverified - the clause {verdict} this "
            f"requirement{anchor}. {self.reasoning}"
        )


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
