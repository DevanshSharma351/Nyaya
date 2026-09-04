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
from nyaya.llm import Message, get_provider
from nyaya.retrieval import nli
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
    entailment_verified: bool = False
    retrieval_score: float = 0.0
    rule_seeded: bool = False
    """Whether the deterministic rule engine independently proposed this control."""

    confidence: Confidence | None = None
    rejections: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        """Whether the mapping survived every deterministic check."""
        return not self.rejections


@dataclass(slots=True)
class ComplianceResult:
    requirement_statement: str
    mappings: list[ValidatedMapping] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    evidence: list[Retrieved] = field(default_factory=list)
    rule_seeded_controls: list[str] = field(default_factory=list)
    model: str = ""

    @property
    def accepted(self) -> list[ValidatedMapping]:
        return [m for m in self.mappings if m.accepted]

    @property
    def rejected(self) -> list[ValidatedMapping]:
        return [m for m in self.mappings if not m.accepted]

    @property
    def acceptance_rate(self) -> float:
        """Share of proposals the validator accepted.

        The headline measure of how much work the grounding layer is doing: a
        rate near 1.0 means the validator is redundant, near 0.0 means the model
        is fabricating freely.
        """
        if not self.mappings:
            return 1.0
        return len(self.accepted) / len(self.mappings)


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
) -> ComplianceResult:
    """Map one requirement to its governing controls, with verified citations."""
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

    return ComplianceResult(
        requirement_statement=requirement.statement,
        mappings=validated,
        conflicts=completion.value.conflicts,
        evidence=retrieved.results,
        rule_seeded_controls=sorted(seeded_ids),
        model=f"{provider.name}:{provider.model}",
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

    # (c) Does the clause entail the requirement?
    verdict = await nli.check(clause.contextual, requirement.statement)
    mapping.relation = verdict.relation
    mapping.entailment_score = verdict.entailment_score
    mapping.entailment_verified = verdict.verified

    if verdict.verified and not verdict.supports:
        mapping.rejections.append(
            f"the cited clause does not entail the requirement "
            f"(relation={verdict.relation.value}, entailment={verdict.entailment_score:.2f})"
        )

    mapping.confidence = fuse(
        ConfidenceComponents(
            retrieval=_normalise(mapping.retrieval_score),
            entailment=mapping.entailment_score,
            validation=1.0 if not mapping.rejections else 0.0,
            consistency=1.0 if mapping.rule_seeded else 0.5,
        )
    )
    return mapping


def _normalise(score: float) -> float:
    """Map a reranker logit onto [0,1].

    Cross-encoder scores are unbounded logits, so they are squashed rather than
    clipped - clipping would collapse every confident score to 1.0 and destroy
    the gradient that confidence fusion needs.
    """
    import math

    return 1.0 / (1.0 + math.exp(-score)) if score else 0.0


__all__ = [
    "COMPLIANCE_SYSTEM",
    "ComplianceOutput",
    "ComplianceResult",
    "ProposedMapping",
    "ValidatedMapping",
    "map_requirement",
]
