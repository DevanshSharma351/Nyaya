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
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.agents.extraction import AnalysedRequirement, new_ref, verify_provenance
from nyaya.core import ledger
from nyaya.core.enums import ApprovalStatus
from nyaya.db.models import (
    ControlMapping,
    Defect,
    Evidence,
    Interview,
    Project,
    Requirement,
    TraceLink,
    Utterance,
)
from nyaya.graph.state import WorkflowState
from nyaya.retrieval.hybrid import resolve_citation


@dataclass(slots=True)
class PersistResult:
    requirement_ids: list[uuid.UUID] = field(default_factory=list)
    evidence_count: int = 0
    mapping_count: int = 0
    trace_links: int = 0
    refs: list[str] = field(default_factory=list)


def save_extraction(
    session: AsyncSession,
    project: Project,
    source_text: str,
    items: list[AnalysedRequirement],
    questions: list[str],
    model: str,
    *,
    previous: list[Requirement] | None = None,
) -> None:
    """Record a redacted brief and the verified source span for each requirement."""
    interview = Interview(
        project_id=project.id,
        title="Requirements brief",
        channel="brief",
        status="open" if questions else "complete",
        coverage={"open_questions": questions},
    )
    session.add(interview)
    interview.utterances.append(
        Utterance(sequence=0, speaker="stakeholder", raw_text=source_text, masked_text=source_text)
    )
    prior = previous or []
    used_refs = {row.ref for row in prior}
    by_statement: dict[str, list[Requirement]] = {}
    for row in prior:
        if row.approval_status != ApprovalStatus.SUPERSEDED:
            by_statement.setdefault(row.statement, []).append(row)
            row.approval_status = ApprovalStatus.SUPERSEDED
    next_ref = 1
    for index, item in enumerate(items, 1):
        extracted = item.requirement
        matches = by_statement.get(extracted.statement, [])
        old = matches.pop() if matches else None
        if old is None:
            ref = new_ref(project.domain, next_ref)
            while ref in used_refs:
                next_ref += 1
                ref = new_ref(project.domain, next_ref)
            used_refs.add(ref)
        else:
            ref = old.ref
        row = Requirement(
            project_id=project.id,
            ref=ref,
            version=old.version + 1 if old else 1,
            supersedes_id=old.id if old else None,
            statement=extracted.statement,
            categories=[c.value for c in extracted.categories],
            priority=extracted.priority,
            risk_level=extracted.risk_level,
            business_justification=extracted.rationale,
            acceptance_criteria=extracted.acceptance_criteria,
            assumptions=extracted.assumptions,
            generated_by=model[:128] or None,
        )
        if extracted.quoted_source and verify_provenance(extracted, source_text) is None:
            quote = extracted.quoted_source
            utterance = Utterance(
                sequence=index, speaker="stakeholder", raw_text=quote, masked_text=quote
            )
            interview.utterances.append(utterance)
            row.source_utterance = utterance
        row.defects = [
            Defect(
                defect_type=d.defect_type,
                severity=d.severity,
                detail=d.detail,
                detector=d.detector,
                span_start=d.span_start,
                span_end=d.span_end,
            )
            for d in item.defects
        ]
        session.add(row)


async def project_open_questions(session: AsyncSession, project_id: uuid.UUID) -> list[str]:
    coverage = await session.scalar(
        select(Interview.coverage)
        .where(Interview.project_id == project_id, Interview.channel == "brief")
        .order_by(Interview.created_at.desc())
        .limit(1)
    )
    return (coverage or {}).get("open_questions", [])


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
        existing = await session.get(Requirement, item.persisted_id) if item.persisted_id else None
        if item.persisted_id and (existing is None or existing.project_id != project_id):
            raise ValueError("The requirement no longer belongs to this project.")
        if existing is not None:
            existing.approval_status = status
            row = existing
            ref = row.ref
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

        for defect in item.defects if existing is None else []:
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
        source_id = row.source_utterance_id or utterance_id
        if source_id is not None and not await session.scalar(
            select(TraceLink.id).where(
                TraceLink.project_id == project_id,
                TraceLink.source_kind == "requirement",
                TraceLink.source_id == row.id,
                TraceLink.target_kind == "utterance",
                TraceLink.target_id == source_id,
                TraceLink.relation == "derives_from",
            )
        ):
            session.add(
                TraceLink(
                    project_id=project_id,
                    source_kind="requirement",
                    source_id=row.id,
                    target_kind="utterance",
                    target_id=source_id,
                    relation="derives_from",
                )
            )
            result.trace_links += 1

    result_counts = await _persist_compliance(session, project_id, state, by_statement)
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
            "run_id": state.get("run_id"),
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
            clause_id = mapping.clause_id
            if clause_id is None and mapping.resolved:
                clause = await resolve_citation(session, mapping.citation_key)
                clause_id = clause.clause_id if clause else None

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

            if clause_id is not None and mapping.status == "confirmed":
                inserted = await session.execute(
                    insert(TraceLink)
                    .values(
                        project_id=project_id,
                        source_kind="requirement",
                        source_id=requirement.id,
                        target_kind="clause",
                        target_id=clause_id,
                        relation="satisfies",
                    )
                    .on_conflict_do_nothing(constraint="uq_trace_link_edge")
                    .returning(TraceLink.id)
                )
                link_count += inserted.scalar_one_or_none() is not None

    await session.flush()
    return evidence_count, mapping_count, link_count


def _baseline_approved(state: WorkflowState) -> bool:
    decisions = state.get("decisions", [])
    return any(
        d["gate"] == "requirement_baseline" and d["decision"] == "approve" for d in decisions
    )


__all__ = ["PersistResult", "persist_run"]
