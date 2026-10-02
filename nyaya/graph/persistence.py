"""Persist a workflow run, and build its traceability graph.

Two jobs, done together because they are the same job: writing a requirement is
pointless unless the edges back to its source and forward to its controls are
written with it. A requirement without its provenance is an assertion.

The traceability graph is what makes regulatory-change impact analysis possible.
Every artefact is a node and every derivation an edge, so "which requirements
does this amended clause affect" is a graph walk rather than a search.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.agents.extraction import new_ref
from nyaya.core import ledger
from nyaya.core.enums import ApprovalStatus, EvidenceRelation
from nyaya.db.models import (
    Clause,
    ControlMapping,
    Defect,
    Evidence,
    Requirement,
    TraceLink,
)
from nyaya.graph.state import WorkflowState


@dataclass(slots=True)
class PersistResult:
    requirement_ids: list[uuid.UUID] = field(default_factory=list)
    evidence_count: int = 0
    mapping_count: int = 0
    trace_links: int = 0
    refs: list[str] = field(default_factory=list)


async def persist_run(
    session: AsyncSession,
    state: WorkflowState,
    *,
    utterance_id: uuid.UUID | None = None,
    stakeholder_id: uuid.UUID | None = None,
) -> PersistResult:
    """Write a completed run's requirements, evidence, mappings and trace edges.

    Approval status reflects what actually happened at the gates. A run that was
    halted persists its requirements as DRAFT rather than silently baselining
    work a human declined to approve.
    """
    project_id = uuid.UUID(state["project_id"])
    approved = _baseline_approved(state)
    status = ApprovalStatus.APPROVED if approved else ApprovalStatus.DRAFT

    result = PersistResult()
    by_statement: dict[str, Requirement] = {}

    for index, item in enumerate(state.get("requirements", []), start=1):
        ref = new_ref(state.get("domain", "ekyc_onboarding"), index)
        existing = (
            await session.execute(
                select(Requirement).where(
                    Requirement.project_id == project_id,
                    Requirement.ref == ref,
                    Requirement.version == 1,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.approval_status = status
            row = existing
        else:
            row = Requirement(
                project_id=project_id,
                ref=ref,
                statement=item.requirement.statement,
                categories=[c.value for c in item.requirement.categories],
                priority=item.requirement.priority,
                risk_level=item.requirement.risk_level,
                business_justification=item.requirement.rationale,
                acceptance_criteria=list(item.requirement.acceptance_criteria),
                assumptions=list(item.requirement.assumptions),
                source_utterance_id=utterance_id,
                source_stakeholder_id=stakeholder_id,
                approval_status=status,
                generated_by="extraction_agent",
            )
            session.add(row)
            await session.flush()

        by_statement[item.requirement.statement] = row
        result.requirement_ids.append(row.id)
        result.refs.append(ref)

        for defect in item.defects:
            session.add(
                Defect(
                    requirement_id=row.id,
                    defect_type=defect.defect_type,
                    severity=defect.severity,
                    detail=defect.detail,
                    detector=defect.detector,
                    span_start=defect.span_start,
                    span_end=defect.span_end,
                )
            )

        # The requirement derives from the stakeholder statement it was
        # extracted from. Without this edge the requirement has no provenance
        # and the quality agent's MISSING_SOURCE check has nothing to point at.
        if utterance_id is not None:
            session.add(
                TraceLink(
                    project_id=project_id,
                    source_kind="requirement", source_id=row.id,
                    target_kind="utterance", target_id=utterance_id,
                    relation="derives_from",
                )
            )
            result.trace_links += 1

    result_counts = await _persist_compliance(
        session, project_id, state, by_statement
    )
    result.evidence_count, result.mapping_count, links = result_counts
    result.trace_links += links

    await ledger.record(
        session,
        project_id=project_id,
        event_type="agent_decision",
        actor="persistence",
        actor_kind="system",
        payload={
            "requirements": len(result.requirement_ids),
            "evidence": result.evidence_count,
            "mappings": result.mapping_count,
            "trace_links": result.trace_links,
            "baseline_approved": approved,
            "decisions": state.get("decisions", []),
        },
    )
    return result


async def _persist_compliance(
    session: AsyncSession,
    project_id: uuid.UUID,
    state: WorkflowState,
    by_statement: dict[str, Requirement],
) -> tuple[int, int, int]:
    """Write evidence rows, control mappings and their trace edges."""
    evidence_count = mapping_count = link_count = 0

    for compliance in state.get("compliance", []):
        requirement = by_statement.get(compliance.requirement_statement)
        if requirement is None:
            continue

        for mapping in compliance.mappings:
            clause_id = await _clause_id(session, mapping.citation_key)

            # Rejected and unconfirmed mappings are recorded too. An unresolvable
            # citation is a finding, and discarding it would erase the evidence
            # that the model proposed something unfounded.
            session.add(
                Evidence(
                    requirement_id=requirement.id,
                    clause_id=clause_id,
                    cited_key=mapping.citation_key,
                    quoted_text=mapping.quoted_text,
                    relation=mapping.relation,
                    entailment_score=mapping.entailment_score,
                    rerank_score=mapping.relevance_score,
                    retrieval_score=mapping.retrieval_score,
                    resolved=mapping.resolved,
                )
            )
            evidence_count += 1

            existing_mapping = (
                await session.execute(
                    select(ControlMapping).where(
                        ControlMapping.requirement_id == requirement.id,
                        ControlMapping.control_id == mapping.control_id,
                    )
                )
            ).scalar_one_or_none()
            if existing_mapping is None:
                session.add(
                    ControlMapping(
                        requirement_id=requirement.id,
                        control_id=mapping.control_id,
                        clause_id=clause_id,
                        jurisdiction=(state.get("jurisdictions") or ["IN"])[0],
                        proposed_by="rule" if mapping.rule_seeded else "llm",
                        validator_passed=mapping.status == "confirmed",
                        validator_detail={
                            "tier": mapping.tier.value,
                            "status": mapping.status,
                            "entailment": mapping.entailment_score,
                            "relevance": mapping.relevance_score,
                            "quote_verified": mapping.quote_verified,
                            "rejections": mapping.rejections,
                            "review_reasons": mapping.review_reasons,
                            "confidence": (
                                mapping.confidence.as_dict() if mapping.confidence else None
                            ),
                        },
                    )
                )
                mapping_count += 1

            if clause_id is not None and mapping.relation is EvidenceRelation.SUPPORTS:
                session.add(
                    TraceLink(
                        project_id=project_id,
                        source_kind="requirement", source_id=requirement.id,
                        target_kind="clause", target_id=clause_id,
                        relation="satisfies",
                    )
                )
                link_count += 1

    await session.flush()
    return evidence_count, mapping_count, link_count


async def _clause_id(session: AsyncSession, citation_key: str) -> uuid.UUID | None:
    return (
        await session.execute(
            select(Clause.id).where(Clause.citation_key == citation_key).limit(1)
        )
    ).scalar_one_or_none()


def _baseline_approved(state: WorkflowState) -> bool:
    decisions = state.get("decisions", [])
    return any(
        d["gate"] == "requirement_baseline" and d["decision"] == "approve"
        for d in decisions
    )


__all__ = ["PersistResult", "persist_run"]
