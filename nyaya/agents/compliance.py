"""The compliance mapping agent.

Maps a requirement to the regulatory controls it satisfies, with citations that
have been **checked rather than trusted**.

The pipeline is deliberately adversarial toward its own model:

1. **Retrieve** candidate clauses (dense + rerank), scoped to the project's
   jurisdictions and to sources still in force.
2. **Seed deterministically.** The rule engine proposes the controls a
   requirement appears to satisfy, so the model is asked to *confirm and cite* a
   mapping rather than invent one from nothing.
3. **The model proposes** a mapping with a citation key and a quotation.
4. **The validator disposes.** Each citation must (a) resolve to a real clause
   in the versioned knowledge base, (b) have its quoted text actually appear in
   that clause, and (c) entail the requirement under NLI.
5. **Confidence is computed** from those independent signals, not reported by
   the model.

Every stage is recorded. The gap between what the model proposed and what the
validator accepted is a headline evaluation metric - it is the direct measure of
how much the grounding machinery is doing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.agents.schemas import ExtractedRequirement
from nyaya.config import ModelRole
from nyaya.core.confidence import Confidence, ConfidenceComponents, fuse
from nyaya.core.enums import EvidenceRelation
from nyaya.llm import Message, Usage, get_provider
from nyaya.retrieval import obligation
from nyaya.retrieval.hybrid import Retrieved, load_context, resolve_citation
from nyaya.retrieval.search import SearchOptions, search
from nyaya.rules import Control, controls_for_requirement, requirement_facts


class ProposedMapping(BaseModel):
    """One requirement-to-control mapping proposed by the model."""

    control_id: str = Field(
        description="The control identifier from the candidate list. Use it verbatim."
    )
    citation_key: str = Field(
        description=(
            "The citation key of the clause that establishes this obligation, "
            "copied verbatim from the evidence provided. Never construct one."
        )
    )
    quoted_text: str = Field(
        description=(
            "The exact sentence from that clause which obliges the requirement. "
            "Copy it verbatim from the evidence."
        )
    )
    reasoning: str = Field(description="One sentence: why this clause obliges this requirement.")


class ComplianceOutput(BaseModel):
    mappings: list[ProposedMapping] = Field(
        description=(
            "Only mappings genuinely supported by the evidence shown. An empty "
            "list is the correct answer when the evidence does not establish any "
            "obligation. Do not map a requirement to a control merely because "
            "they concern a similar topic."
        )
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description=(
            "Any clause shown that the requirement would VIOLATE rather than "
            "satisfy. Quote the clause and say what conflicts."
        ),
    )


COMPLIANCE_SYSTEM = """\
You are a compliance analyst mapping a software requirement to the regulatory \
clauses that oblige it.

You will be given a requirement, a list of candidate controls, and retrieved \
clauses from an approved knowledge base.

Rules:

1. Cite ONLY from the clauses shown. Copy `citation_key` and `quoted_text` \
verbatim. A citation you construct rather than copy is a fabrication, and it is \
the single most damaging error you can make here - it looks like evidence.

2. Topical similarity is NOT an obligation. A clause about record retention does \
not oblige a screening requirement, however related they seem. If the clause \
would not convince a regulator that this requirement is mandatory, do not map it.

3. Returning NO mappings is a correct and useful answer. An unsupported mapping \
is worse than a missing one, because it will be relied upon.

4. If a clause shown means the requirement would BREACH the regulation, report \
it under `conflicts` rather than mapping it.
"""


@dataclass(slots=True)
class ValidatedMapping:
    """A proposed mapping after deterministic checking."""

    control_id: str
    citation_key: str
    quoted_text: str
    reasoning: str

    resolved: bool = False
    """Whether `citation_key` matched a real clause in the versioned KB."""

    quote_verified: bool = False
    """Whether `quoted_text` actually appears in that clause."""

    relation: EvidenceRelation = EvidenceRelation.NEUTRAL
    entailment_score: float = 0.0
    relevance_score: float = 0.0
    tier: obligation.ObligationTier = obligation.ObligationTier.UNCONFIRMED
    entailment_verified: bool = False
    retrieval_score: float = 0.0
    rule_seeded: bool = False
    """Whether the deterministic rule engine independently proposed this control."""

    confidence: Confidence | None = None
    review_note: str | None = None
    """An advisory opinion for whoever reviews this citation. Never a verdict:
    the judge that produces it was measured at precision 0.786 and cannot
    auto-confirm a compliance mapping."""

    rejections: list[str] = field(default_factory=list)
    """**Objective** failures only: the citation does not resolve, or the quote
    was composed rather than copied. These are facts, not judgements."""

    review_reasons: list[str] = field(default_factory=list)
    """Probabilistic concerns. The mapping may well be correct; it has not been
    machine-confirmed and needs a human."""

    @property
    def status(self) -> str:
        """`rejected` | `needs_review` | `confirmed`.

        The three-way split exists because the checks are not of one kind.
        Citation resolution and quote verification are **objective** - a key
        either resolves or it does not - so failing them is grounds for
        rejection. Entailment is a **probabilistic judgement** by a
        general-purpose model, measured on the labelled set at precision 0.909
        but recall 0.588: it rejects roughly two in five correct citations.

        Treating that as rejection would discard correct compliance mappings and
        train reviewers to override the validator. So an unconfirmed citation is
        routed to a human rather than thrown away. Only what can be checked
        objectively is refused outright.
        """
        if self.rejections:
            return "rejected"
        if self.review_reasons:
            return "needs_review"
        return "confirmed"

    @property
    def accepted(self) -> bool:
        """Whether the mapping may be relied on without human confirmation."""
        return self.status == "confirmed"

    @property
    def discarded(self) -> bool:
        """Whether the mapping failed an objective check."""
        return bool(self.rejections)


@dataclass(slots=True)
class ComplianceResult:
    requirement_statement: str
    mappings: list[ValidatedMapping] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    evidence: list[Retrieved] = field(default_factory=list)
    rule_seeded_controls: list[str] = field(default_factory=list)
    model: str = ""
    usage: Usage = field(default_factory=Usage)

    @property
    def confirmed(self) -> list[ValidatedMapping]:
        return [m for m in self.mappings if m.status == "confirmed"]

    @property
    def needs_review(self) -> list[ValidatedMapping]:
        return [m for m in self.mappings if m.status == "needs_review"]

    @property
    def rejected(self) -> list[ValidatedMapping]:
        return [m for m in self.mappings if m.status == "rejected"]

    @property
    def accepted(self) -> list[ValidatedMapping]:
        return self.confirmed

    @property
    def rejection_rate(self) -> float:
        """Share of proposals failing an *objective* check.

        The direct measure of how much fabrication the grounding layer catches:
        a citation that does not resolve, or a quotation that was composed
        rather than copied.
        """
        if not self.mappings:
            return 0.0
        return len(self.rejected) / len(self.mappings)


def _render_evidence(clauses: list[Retrieved]) -> str:
    # `contextual` rather than `display`: a sub-clause shown without its parent
    # invites the model to cite an obligation whose subject it cannot see.
    return "\n\n".join(f"[{c.citation_key}] {c.contextual}".strip() for c in clauses)


def _render_controls(controls: list[Control]) -> str:
    if not controls:
        return "(none matched deterministically - judge from the evidence alone)"
    return "\n".join(
        f"- {c.control_id}: {c.title} (authority: {', '.join(c.citations)})" for c in controls
    )


async def map_requirement(
    session: AsyncSession,
    requirement: ExtractedRequirement,
    *,
    domain: str = "ekyc_onboarding",
    jurisdictions: list[str] | None = None,
    role: ModelRole = ModelRole.REASONING,
    top_k: int = 8,
    annotate_reviews: bool = False,
) -> ComplianceResult:
    """Map one requirement to its governing controls, with verified citations.

    `annotate_reviews` asks an LLM judge for an advisory opinion on citations
    the NLI could not confirm. Off by default because it costs a model call per
    citation (~19 s measured) and adds no authority - only context for the human
    who will decide.
    """
    jurisdictions = jurisdictions or ["IN"]

    facts = requirement_facts(
        statement=requirement.statement,
        categories=[c.value for c in requirement.categories],
        risk_level=requirement.risk_level.value,
        jurisdictions=jurisdictions,
        domain=domain,
    )
    seeded = controls_for_requirement(facts)

    retrieved = await search(
        session,
        requirement.statement,
        options=SearchOptions(top_k=top_k, jurisdictions=jurisdictions),
    )

    provider = get_provider(role)
    prompt = (
        f"REQUIREMENT:\n{requirement.statement}\n\n"
        f"CANDIDATE CONTROLS:\n{_render_controls(seeded)}\n\n"
        f"RETRIEVED CLAUSES:\n{_render_evidence(retrieved.results)}"
    )
    completion = await provider.complete_structured(
        [
            Message(role="system", content=COMPLIANCE_SYSTEM),
            Message(role="user", content=prompt),
        ],
        ComplianceOutput,
    )

    seeded_ids = {c.control_id for c in seeded}
    retrieved_by_key = {r.citation_key: r for r in retrieved.results}

    validated: list[ValidatedMapping] = []
    for proposal in completion.value.mappings:
        validated.append(
            await _validate(session, requirement, proposal, seeded_ids, retrieved_by_key)
        )

    usage = Usage(
        prompt_tokens=completion.completion.usage.prompt_tokens,
        completion_tokens=completion.completion.usage.completion_tokens,
        model=f"{provider.name}:{provider.model}",
        role=role.value,
    )

    return ComplianceResult(
        requirement_statement=requirement.statement,
        mappings=validated,
        conflicts=completion.value.conflicts,
        evidence=retrieved.results,
        rule_seeded_controls=sorted(seeded_ids),
        model=f"{provider.name}:{provider.model}",
        usage=usage,
    )


async def _validate(
    session: AsyncSession,
    requirement: ExtractedRequirement,
    proposal: ProposedMapping,
    seeded_ids: set[str],
    retrieved_by_key: dict[str, Retrieved],
) -> ValidatedMapping:
    """Run every deterministic check over one proposed mapping."""
    mapping = ValidatedMapping(
        control_id=proposal.control_id,
        citation_key=proposal.citation_key,
        quoted_text=proposal.quoted_text,
        reasoning=proposal.reasoning,
        rule_seeded=proposal.control_id in seeded_ids,
    )

    # (a) Does the cited key resolve to a real clause in the versioned KB?
    clause = retrieved_by_key.get(proposal.citation_key)
    if clause is None:
        clause = await resolve_citation(session, proposal.citation_key)
        if clause is not None:
            await load_context(session, [clause])
    mapping.resolved = clause is not None

    if clause is None:
        mapping.rejections.append(
            f"citation {proposal.citation_key!r} does not resolve to any clause "
            f"in the knowledge base"
        )
        mapping.confidence = fuse(ConfidenceComponents())
        return mapping

    mapping.retrieval_score = clause.rerank_score or clause.fused_score or 0.0

    # (b) Does the quoted text actually appear in that clause?
    quoted = " ".join(proposal.quoted_text.split()).lower()
    # Checked against the contextual text, since that is what the model was
    # shown; quoting a parent clause is legitimate, inventing text is not.
    haystack = " ".join(clause.contextual.split()).lower()
    mapping.quote_verified = bool(quoted) and quoted in haystack
    if not mapping.quote_verified:
        mapping.rejections.append(
            "quoted text does not appear in the cited clause; it was composed rather than copied"
        )

    # (c) Does the clause oblige the requirement?
    #
    # Two independent models, and only their *agreement* licenses acceptance.
    # Measured on the labelled set, agreement gives precision 1.000 with zero
    # false confirmations, where either signal alone admits one.
    check = await obligation.check(clause, requirement.statement)
    mapping.entailment_score = check.entailment
    mapping.relevance_score = check.relevance
    mapping.tier = check.tier
    mapping.entailment_verified = check.verified
    mapping.relation = (
        EvidenceRelation.CONTRADICTS
        if check.tier is obligation.ObligationTier.CONFLICTING
        else EvidenceRelation.SUPPORTS
        if check.tier is obligation.ObligationTier.CONFIRMED
        else EvidenceRelation.NEUTRAL
    )

    if check.tier is obligation.ObligationTier.CONFLICTING:
        # A confident contradiction is a substantive finding, not mere doubt.
        mapping.rejections.append(check.explain())
    elif not check.auto_acceptable:
        mapping.review_reasons.append(check.explain())

    mapping.confidence = fuse(
        ConfidenceComponents(
            retrieval=max(_normalise(mapping.retrieval_score), mapping.relevance_score),
            # The evidence signal is the agreed one: a citation only one model
            # supports must not inherit that model's confidence alone.
            entailment=(
                min(mapping.entailment_score, mapping.relevance_score)
                if mapping.tier is obligation.ObligationTier.CONFIRMED
                else mapping.entailment_score * mapping.relevance_score
            ),
            # Objective checks passed in full; unconfirmed entailment reduces
            # confidence through its own component rather than zeroing this one.
            validation=1.0 if not mapping.rejections else 0.0,
            consistency=1.0 if mapping.rule_seeded else 0.5,
        )
    )
    return mapping


def _normalise(score: float) -> float:
    """Clamp a retrieval score to [0,1].

    `bge-reranker` applies a sigmoid internally, so its output is already a
    probability; an earlier version squashed it a second time, which collapsed
    the range to [0.50, 0.73] and let a false confirmation into the auto-accept
    tier. RRF fused scores are small positives on a different scale, so they are
    clamped rather than transformed - no rescaling would make the two
    commensurable, and pretending otherwise would put a made-up number into the
    confidence calculation.
    """
    return max(0.0, min(1.0, score))


__all__ = [
    "COMPLIANCE_SYSTEM",
    "ComplianceOutput",
    "ComplianceResult",
    "ProposedMapping",
    "ValidatedMapping",
    "map_requirement",
]
