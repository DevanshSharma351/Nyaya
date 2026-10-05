"""Projects and their requirements.

Includes project-based generate endpoints that reuse persisted extraction
results instead of re-running the LLM. The Artefact, SDLC, and Coverage
modules are deterministic — they need only the requirements already in the
database, not a new extraction call.
"""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nyaya.api.deps import db_session
from nyaya.api.schemas import (
    ActivityOut,
    AgentUsageOut,
    ApprovalOut,
    ArtefactsOut,
    ControlCoverageOut,
    CoverageOut,
    DefectOut,
    EvidenceOut,
    GateDecisionIn,
    GateSpecOut,
    LLMCallEventOut,
    ModelUsageOut,
    PhaseOut,
    ProjectIn,
    ProjectOut,
    ProjectUsageOut,
    RequirementOut,
    RequirementUpdateIn,
    RiskEntryOut,
    SDLCFromBriefOut,
    SDLCOut,
    SDLCRankOut,
    TraceRowOut,
    UseCaseOut,
    UserStoryOut,
    WorkflowOut,
    WorkflowStartIn,
    WorkflowStatusOut,
)
from nyaya.artefacts import build as build_artefacts
from nyaya.core.enums import Priority, RequirementCategory, RiskLevel, StakeholderRole
from nyaya.db.models import (
    Approval,
    AuditEvent,
    Conflict,
    ControlMapping,
    Defect,
    Evidence,
    Interview,
    Project,
    Requirement,
    SDLCAssessment,
    SDLCWorkflow,
    Stakeholder,
    TraceLink,
    Utterance,
)
from nyaya.graph.gates import GATES, UnauthorisedApproverError
from nyaya.graph.runner import get_workflow_runner
from nyaya.mcda.derive import derive
from nyaya.mcda.sdlc import recommend
from nyaya.mcda.workflow import generate as generate_workflow
from nyaya.rules.engine import evaluate, requirement_facts

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(session: AsyncSession = Depends(db_session)):
    rows = (
        await session.execute(
            select(Project, func.count(Requirement.id))
            .outerjoin(Requirement, Requirement.project_id == Project.id)
            .group_by(Project.id)
            .order_by(Project.created_at.desc())
        )
    ).all()
    return [
        ProjectOut(
            id=p.id, name=p.name, description=p.description,
            domain=p.domain, jurisdictions=p.jurisdictions,
            status=p.status, created_at=p.created_at, requirement_count=count,
        )
        for p, count in rows
    ]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(payload: ProjectIn, session: AsyncSession = Depends(db_session)):
    project = Project(
        name=payload.name, domain=payload.domain,
        description=payload.description, jurisdictions=payload.jurisdictions,
    )
    session.add(project)
    await session.flush()
    return ProjectOut(
        id=project.id, name=project.name, description=project.description,
        domain=project.domain, jurisdictions=project.jurisdictions,
        status=project.status, created_at=project.created_at,
    )


@router.get("/{project_id}/requirements", response_model=list[RequirementOut])
async def list_requirements(
    project_id: uuid.UUID, session: AsyncSession = Depends(db_session)
):
    """Requirements with their defects and evidence.

    Evidence is included rather than fetched separately because a requirement
    shown without its citations invites exactly the trust the design is built to
    avoid.
    """
    rows = (
        await session.execute(
            select(Requirement)
            .options(
                selectinload(Requirement.defects),
                selectinload(Requirement.evidence),
            )
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.ref)
        )
    ).scalars().all()

    return [
        RequirementOut(
            id=r.id, ref=r.ref, statement=r.statement,
            categories=r.categories, priority=r.priority, risk_level=r.risk_level,
            approval_status=str(r.approval_status), confidence=r.confidence,
            acceptance_criteria=r.acceptance_criteria,
            defects=[
                DefectOut(
                    defect_type=str(d.defect_type), severity=str(d.severity),
                    detail=d.detail, detector=d.detector,
                )
                for d in r.defects
            ],
            evidence=[
                EvidenceOut(
                    cited_key=e.cited_key, quoted_text=e.quoted_text,
                    relation=str(e.relation), entailment_score=e.entailment_score,
                    rerank_score=e.rerank_score, resolved=e.resolved,
                )
                for e in r.evidence
            ],
        )
        for r in rows
    ]


@router.patch("/{project_id}/requirements/{requirement_id}", response_model=RequirementOut)
async def update_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    payload: RequirementUpdateIn,
    session: AsyncSession = Depends(db_session),
):
    """Edit an individual requirement.

    Marks downstream SDLC and artefacts stale, and records a human_edit audit event.
    """
    req = (
        await session.execute(
            select(Requirement)
            .options(
                selectinload(Requirement.defects),
                selectinload(Requirement.evidence),
            )
            .where(
                Requirement.id == requirement_id,
                Requirement.project_id == project_id,
            )
        )
    ).scalars().first()

    if req is None:
        raise HTTPException(404, "requirement not found")

    changes: dict[str, Any] = {}
    if payload.statement is not None:
        req.statement = payload.statement
        changes["statement"] = payload.statement
    if payload.priority is not None:
        req.priority = payload.priority
        changes["priority"] = payload.priority.value
    if payload.risk_level is not None:
        req.risk_level = payload.risk_level
        changes["risk_level"] = payload.risk_level.value
    if payload.categories is not None:
        req.categories = [c.value for c in payload.categories]
        changes["categories"] = req.categories
    if payload.acceptance_criteria is not None:
        req.acceptance_criteria = payload.acceptance_criteria
        changes["acceptance_criteria"] = payload.acceptance_criteria
    if payload.business_justification is not None:
        req.business_justification = payload.business_justification
        changes["business_justification"] = payload.business_justification

    req.updated_at = datetime.now(UTC)
    await session.flush()

    from nyaya.core import ledger
    await ledger.record(
        session,
        project_id=project_id,
        event_type="human_edit",
        actor="user",
        actor_kind="human",
        payload={
            "requirement_id": str(req.id),
            "ref": req.ref,
            "changes": changes,
        },
        subject_kind="requirement",
        subject_id=req.id,
    )

    return RequirementOut(
        id=req.id,
        ref=req.ref,
        statement=req.statement,
        categories=req.categories,
        priority=req.priority,
        risk_level=req.risk_level,
        approval_status=str(req.approval_status),
        confidence=req.confidence,
        acceptance_criteria=req.acceptance_criteria,
        defects=[
            DefectOut(
                defect_type=str(d.defect_type),
                severity=str(d.severity),
                detail=d.detail,
                detector=d.detector,
            )
            for d in req.defects
        ],
        evidence=[
            EvidenceOut(
                cited_key=e.cited_key,
                quoted_text=e.quoted_text,
                relation=str(e.relation),
                entailment_score=e.entailment_score,
                rerank_score=e.rerank_score,
                resolved=e.resolved,
            )
            for e in req.evidence
        ],
    )


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, session: AsyncSession = Depends(db_session)):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    count = (
        await session.execute(
            select(func.count(Requirement.id)).where(Requirement.project_id == project_id)
        )
    ).scalar_one()
    return ProjectOut(
        id=project.id, name=project.name, description=project.description,
        domain=project.domain, jurisdictions=project.jurisdictions,
        status=project.status, created_at=project.created_at,
        requirement_count=count,
    )


@router.delete("/{project_id}", status_code=200)
async def delete_project(project_id: uuid.UUID, session: AsyncSession = Depends(db_session)):
    """Delete a project and all associated requirements, assessments, approvals, and trace links."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    # 1. Gather all requirement IDs for this project
    req_ids = (
        await session.execute(
            select(Requirement.id).where(Requirement.project_id == project_id)
        )
    ).scalars().all()

    if req_ids:
        await session.execute(
            delete(ControlMapping).where(ControlMapping.requirement_id.in_(req_ids))
        )
        await session.execute(
            delete(Conflict).where(
                (Conflict.left_id.in_(req_ids)) | (Conflict.right_id.in_(req_ids))
            )
        )
        await session.execute(
            delete(Defect).where(Defect.requirement_id.in_(req_ids))
        )
        await session.execute(
            delete(Evidence).where(Evidence.requirement_id.in_(req_ids))
        )
        await session.execute(
            delete(Requirement).where(Requirement.project_id == project_id)
        )

    # 2. SDLC assessments and workflows
    assessment_ids = (
        await session.execute(
            select(SDLCAssessment.id).where(SDLCAssessment.project_id == project_id)
        )
    ).scalars().all()
    if assessment_ids:
        await session.execute(
            delete(SDLCWorkflow).where(SDLCWorkflow.assessment_id.in_(assessment_ids))
        )
        await session.execute(
            delete(SDLCAssessment).where(SDLCAssessment.project_id == project_id)
        )

    # 3. Trace links, approvals, audit events
    await session.execute(
        delete(TraceLink).where(TraceLink.project_id == project_id)
    )
    await session.execute(
        delete(Approval).where(Approval.project_id == project_id)
    )
    await session.execute(
        delete(AuditEvent).where(AuditEvent.project_id == project_id)
    )

    # 4. Stakeholders, interviews, utterances
    stakeholder_ids = (
        await session.execute(
            select(Stakeholder.id).where(Stakeholder.project_id == project_id)
        )
    ).scalars().all()
    interview_ids = (
        await session.execute(
            select(Interview.id).where(Interview.project_id == project_id)
        )
    ).scalars().all()
    if stakeholder_ids or interview_ids:
        conditions = []
        if stakeholder_ids:
            conditions.append(Utterance.stakeholder_id.in_(stakeholder_ids))
        if interview_ids:
            conditions.append(Utterance.interview_id.in_(interview_ids))
        await session.execute(delete(Utterance).where(or_(*conditions)))

    if interview_ids:
        await session.execute(delete(Interview).where(Interview.id.in_(interview_ids)))
    if stakeholder_ids:
        await session.execute(delete(Stakeholder).where(Stakeholder.id.in_(stakeholder_ids)))

    # 5. Delete project row and commit
    await session.delete(project)
    await session.commit()
    return {"ok": True, "id": str(project_id)}


@router.get("/{project_id}/usage", response_model=ProjectUsageOut)
async def get_project_usage(
    project_id: uuid.UUID, session: AsyncSession = Depends(db_session)
):
    """Aggregate token and cost observability metrics from the audit ledger."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    events = (
        await session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.project_id == project_id,
                AuditEvent.event_type == "llm_call",
            )
            .order_by(AuditEvent.occurred_at.asc())
        )
    ).scalars().all()

    call_events: list[LLMCallEventOut] = []
    by_agent_map: dict[str, dict] = {}
    by_model_map: dict[str, dict] = {}
    total_prompt = 0
    total_completion = 0
    total_cost = 0.0

    for ev in events:
        p = ev.payload or {}
        agent = p.get("agent", "unknown")
        model = p.get("model", ev.actor or "unknown")
        prompt = p.get("prompt_tokens", 0)
        completion = p.get("completion_tokens", 0)
        tot = p.get("total_tokens", prompt + completion)
        cost = p.get("cost_usd", 0.0)
        repair = p.get("repair_rounds", 0)

        total_prompt += prompt
        total_completion += completion
        total_cost += cost

        if agent not in by_agent_map:
            by_agent_map[agent] = {
                "agent": agent,
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
            }
        by_agent_map[agent]["calls"] += 1
        by_agent_map[agent]["prompt_tokens"] += prompt
        by_agent_map[agent]["completion_tokens"] += completion
        by_agent_map[agent]["total_tokens"] += tot
        by_agent_map[agent]["cost_usd"] = round(by_agent_map[agent]["cost_usd"] + cost, 6)

        if model not in by_model_map:
            by_model_map[model] = {
                "model": model,
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
            }
        by_model_map[model]["calls"] += 1
        by_model_map[model]["prompt_tokens"] += prompt
        by_model_map[model]["completion_tokens"] += completion
        by_model_map[model]["total_tokens"] += tot
        by_model_map[model]["cost_usd"] = round(by_model_map[model]["cost_usd"] + cost, 6)

        call_events.append(
            LLMCallEventOut(
                occurred_at=ev.occurred_at,
                actor=ev.actor,
                agent=agent,
                model=model,
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=tot,
                cost_usd=cost,
                repair_rounds=repair,
            )
        )

    return ProjectUsageOut(
        project_id=project_id,
        total_calls=len(events),
        prompt_tokens=total_prompt,
        completion_tokens=total_completion,
        total_tokens=total_prompt + total_completion,
        total_cost_usd=round(total_cost, 6),
        by_agent=[AgentUsageOut(**v) for v in by_agent_map.values()],
        by_model=[ModelUsageOut(**v) for v in by_model_map.values()],
        events=call_events,
    )


@router.get("/{project_id}/sdlc", response_model=SDLCFromBriefOut)
async def get_project_sdlc(project_id: uuid.UUID, session: AsyncSession = Depends(db_session)):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    assessment = (
        await session.execute(
            select(SDLCAssessment)
            .options(selectinload(SDLCAssessment.workflow))
            .where(SDLCAssessment.project_id == project_id)
            .order_by(SDLCAssessment.created_at.desc())
        )
    ).scalars().first()

    if not assessment:
        return await generate_project_sdlc(project_id=project_id, session=session)

    count = (
        await session.execute(
            select(func.count(Requirement.id)).where(Requirement.project_id == project_id)
        )
    ).scalar_one()

    # Reconstruct SDLCOut
    # Note: We simulate the 'rankings' from scores
    rankings = []
    for model_name, closeness in assessment.scores.items():
        rankings.append(
            SDLCRankOut(
                model=model_name,
                percentage=int(closeness * 100),
                closeness=closeness,
                drivers={},
            )
        )
    rankings.sort(key=lambda r: r.closeness, reverse=True)

    recommendation = SDLCOut(
        recommended=assessment.recommended.value,
        ranked=rankings,
        close_call=False,
        consistency_ratio=assessment.consistency_ratio,
        notes=[],
        explanation=assessment.justification.split("\n") if assessment.justification else [],
    )

    wf = assessment.workflow
    if not wf:
        raise HTTPException(404, "no SDLC workflow found for this assessment")

    workflow = WorkflowOut(
        model=wf.model.value,
        cadence="iterative",
        phases=[
            PhaseOut(
                name=p.get("name", ""),
                purpose=p.get("purpose", ""),
                entry_criteria=p.get("entry_criteria", []),
                exit_criteria=p.get("exit_criteria", []),
                activities=[
                    ActivityOut(**a) for a in p.get("activities", [])
                ],
                deliverables=p.get("deliverables", []),
                roles=p.get("roles", []),
                gate=p.get("gate"),
            )
            for p in wf.phases
        ],
        traceability=[],
        notes=[],
    )

    max_updated = (
        await session.execute(
            select(func.max(Requirement.updated_at)).where(Requirement.project_id == project_id)
        )
    ).scalar_one_or_none()

    is_stale = bool(max_updated and assessment.created_at and max_updated > assessment.created_at)

    return SDLCFromBriefOut(
        project_id=project_id,
        recommendation=recommendation,
        workflow=workflow,
        factors=assessment.factors,
        observations=[],
        requirements_extracted=count,
        unclear=[],
        is_stale=is_stale,
    )


# ---------------------------------------------------------------------------
# DB-to-agent adapters
#
# The artefact builder and SDLC derive() function were written to consume
# AnalysedRequirement objects from the extraction agent. Rather than coupling
# those modules to the ORM, we construct lightweight duck-type-compatible
# wrappers that expose the same `.requirement.*` and `.defects` interface
# the downstream code reads.
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _FakeExtracted:
    """Quacks like an ExtractedRequirement for the artefact builder."""
    statement: str
    rationale: str
    categories: list[RequirementCategory]
    priority: Priority
    risk_level: RiskLevel
    acceptance_criteria: list[str]
    assumptions: list[str]
    quoted_source: str = ""


@dataclass(slots=True)
class _FakeDefect:
    detail: str
    defect_type: str = "unknown"
    severity: str = "minor"
    detector: str = "persisted"


@dataclass(slots=True)
class _FakeAnalysed:
    """Quacks like an AnalysedRequirement for the artefact builder."""
    requirement: _FakeExtracted
    defects: list[_FakeDefect] = field(default_factory=list)
    ears_pattern: str = "none"

    @property
    def is_testable(self) -> bool:
        return not any(d.severity in {"major", "blocker"} for d in self.defects)


def _db_to_analysed(rows: list[Requirement]) -> list[_FakeAnalysed]:
    """Convert persisted Requirement rows into the shape build_artefacts expects.

    Defects must be eagerly loaded (selectinload) before calling this function,
    otherwise async SQLAlchemy will raise a MissingGreenlet error.
    """
    items = []
    for r in rows:
        cats = []
        for c in (r.categories or []):
            with contextlib.suppress(ValueError):
                cats.append(RequirementCategory(c))

        # Defects are eagerly loaded by _load_requirements; access is safe here.
        db_defects = list(r.defects) if r.defects else []

        items.append(_FakeAnalysed(
            requirement=_FakeExtracted(
                statement=r.statement,
                rationale=r.business_justification or "",
                categories=cats,
                priority=r.priority,
                risk_level=r.risk_level,
                acceptance_criteria=r.acceptance_criteria or [],
                assumptions=r.assumptions or [],
            ),
            defects=[
                _FakeDefect(detail=d.detail, defect_type=str(d.defect_type), severity=str(d.severity))
                for d in db_defects
            ],
        ))
    return items


async def _load_requirements(
    session: AsyncSession, project_id: uuid.UUID, required: bool = True
) -> list[Requirement]:
    """Load a project's requirements with defects eagerly loaded.

    Raises 404 if the project doesn't exist, or if required=True and has no requirements.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    rows = (
        await session.execute(
            select(Requirement)
            .options(selectinload(Requirement.defects))
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.ref)
        )
    ).scalars().all()
    if not rows and required:
        raise HTTPException(404, "no requirements found for this project — run extraction first")
    return list(rows)


# ---------------------------------------------------------------------------
# Generate endpoints — deterministic, zero LLM calls
# ---------------------------------------------------------------------------


@router.post("/{project_id}/artefacts/generate", response_model=ArtefactsOut)
async def generate_project_artefacts(
    project_id: uuid.UUID, session: AsyncSession = Depends(db_session)
):
    """Generate SRS artefacts from persisted requirements — no LLM call.

    Reads the extraction results already stored in the database and runs
    the deterministic artefact builder (user stories, use cases, traceability
    matrix, risk register). Instant.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    rows = await _load_requirements(session, project_id)
    items = _db_to_analysed(rows)
    artefacts = build_artefacts(items, project=project.name or project.domain)
    return ArtefactsOut(
        project=artefacts.project,
        generated_at=artefacts.generated_at,
        user_stories=[
            UserStoryOut(
                ref=s.ref, text=s.text, role=s.role, trigger=s.trigger,
                acceptance_criteria=s.acceptance_criteria,
            )
            for s in artefacts.user_stories
        ],
        use_cases=[
            UseCaseOut(
                ref=u.ref, name=u.name, actor=u.actor, precondition=u.precondition,
                main_flow=u.main_flow, postcondition=u.postcondition,
                exceptions=u.exceptions,
            )
            for u in artefacts.use_cases
        ],
        traceability=[
            TraceRowOut(
                ref=r.ref, statement=r.statement, source_quote=r.source_quote,
                citations=r.citations, controls=r.controls,
                verification=r.verification, approval_status=r.approval_status,
                confidence=r.confidence, gaps=r.gaps,
            )
            for r in artefacts.traceability
        ],
        traceability_coverage=round(artefacts.traceability_coverage, 4),
        risks=[
            RiskEntryOut(
                ref=r.ref, description=r.description, category=r.category,
                level=r.level, score=r.score, treatment=r.treatment, owner=r.owner,
            )
            for r in artefacts.risks
        ],
        open_issues=artefacts.open_issues,
        assumptions=artefacts.assumptions,
    )


@router.post("/{project_id}/sdlc/generate", response_model=SDLCFromBriefOut)
async def generate_project_sdlc(
    project_id: uuid.UUID, session: AsyncSession = Depends(db_session)
):
    """Generate SDLC recommendation from persisted requirements — no LLM call.

    Loads the requirements and the original brief text from the database,
    runs the deterministic derive() → recommend() → generate_workflow()
    pipeline, and persists the result. Instant.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    rows = await _load_requirements(session, project_id, required=False)
    items = _db_to_analysed(rows)

    # Derive SDLC factors from persisted requirements + brief text
    derivation = derive(items, unclear=[], brief=project.description)
    ranking = recommend(derivation.factors)
    critical = sum(
        1 for item in items
        if item.requirement.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    )
    workflow = generate_workflow(
        ranking.recommended,
        critical_requirements=critical,
        open_questions=0,
    )

    # Persist the assessment
    assessment = SDLCAssessment(
        project_id=project.id,
        factors=derivation.factors,
        weights=ranking.weights.criteria,
        consistency_ratio=ranking.weights.consistency_ratio,
        scores={r.name: r.closeness for r in ranking.ranking.rankings},
        recommended=ranking.recommended,
        justification="\n".join(ranking.ranking.explain()),
    )
    session.add(assessment)
    await session.flush()

    wf = SDLCWorkflow(
        assessment_id=assessment.id,
        model=ranking.recommended,
        phases=[
            {
                "name": p.name, "purpose": p.purpose,
                "entry_criteria": p.entry_criteria, "exit_criteria": p.exit_criteria,
                "activities": [
                    {"name": a.name, "role": a.role, "because": a.because,
                     "security": a.security, "compliance": a.compliance}
                    for a in p.activities
                ],
                "deliverables": p.deliverables, "roles": p.roles, "gate": p.gate,
            }
            for p in workflow.phases
        ],
        gates=[],
    )
    session.add(wf)
    await session.flush()

    return SDLCFromBriefOut(
        project_id=project.id,
        recommendation=SDLCOut(
            recommended=ranking.recommended.value,
            ranked=[
                SDLCRankOut(
                    model=r.name, percentage=r.percentage,
                    closeness=round(r.closeness, 4),
                    drivers=dict(sorted(r.contributions.items(), key=lambda kv: -kv[1])[:5]),
                )
                for r in ranking.ranking.rankings
            ],
            close_call=ranking.close_call,
            consistency_ratio=round(ranking.weights.consistency_ratio, 4),
            notes=ranking.notes,
            explanation=ranking.ranking.explain(),
        ),
        workflow=WorkflowOut(
            model=workflow.model.value,
            cadence=workflow.cadence,
            phases=[
                PhaseOut(
                    name=phase.name, purpose=phase.purpose,
                    entry_criteria=phase.entry_criteria, exit_criteria=phase.exit_criteria,
                    activities=[
                        ActivityOut(
                            name=a.name, role=a.role, because=a.because,
                            security=a.security, compliance=a.compliance,
                        )
                        for a in phase.activities
                    ],
                    deliverables=phase.deliverables, roles=phase.roles, gate=phase.gate,
                )
                for phase in workflow.phases
            ],
            traceability=workflow.traceability,
            notes=workflow.notes,
        ),
        factors=derivation.factors,
        observations=derivation.observations,
        requirements_extracted=len(rows),
        unclear=[],
        is_stale=False,
    )


@router.post("/{project_id}/coverage/generate", response_model=list[CoverageOut])
async def generate_project_coverage(
    project_id: uuid.UUID, session: AsyncSession = Depends(db_session)
):
    """Evaluate compliance coverage from persisted requirements — no LLM call.

    Loads the requirements from the database and runs the deterministic
    rule engine to find which mandatory controls are covered and which
    are gaps. Instant.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    rows = await _load_requirements(session, project_id)

    facts = [
        (
            r.ref,
            requirement_facts(
                statement=r.statement,
                categories=r.categories or [],
                risk_level=r.risk_level.value if hasattr(r.risk_level, 'value') else str(r.risk_level),
                jurisdictions=project.jurisdictions or ["IN"],
                domain=project.domain or "ekyc_onboarding",
            ),
        )
        for r in rows
    ]
    reports = evaluate(
        facts,
        domain=project.domain or "ekyc_onboarding",
        jurisdictions=project.jurisdictions or ["IN"],
    )
    return [
        CoverageOut(
            pack=r.pack, pack_version=r.pack_version,
            coverage_ratio=round(r.coverage_ratio, 4),
            controls=[
                ControlCoverageOut(
                    control_id=c.control_id, title=c.control.title,
                    severity=c.control.severity, citations=list(c.control.citations),
                    satisfied_by=c.satisfied_by, is_gap=c.is_gap,
                )
                for c in r.coverage
            ],
            blocking_gaps=[g.control_id for g in r.blocking_gaps],
        )
        for r in reports
    ]


@router.get("/workflow/gates", response_model=list[GateSpecOut])
async def list_workflow_gates():
    """List all 6 mandatory human-in-the-loop approval gates and required roles."""
    return [
        GateSpecOut(
            name=gate.name,
            description=gate.description,
            required_roles=[r.value for r in gate.required_roles],
            blocking=gate.blocking,
        )
        for gate in GATES.values()
    ]


@router.post("/{project_id}/workflow/start", response_model=WorkflowStatusOut)
async def start_project_workflow(
    project_id: uuid.UUID,
    payload: WorkflowStartIn | None = None,
    session: AsyncSession = Depends(db_session),
):
    """Start or re-run the full LangGraph 5-stage verification workflow for a project.

    Reuses existing persisted requirements if already extracted, running the
    multi-agent workflow through human approval gates durably.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    body = payload or WorkflowStartIn()
    runner = get_workflow_runner()
    return await runner.start(
        session=session,
        project_id=project_id,
        source_text=body.source_text,
        domain=body.domain or project.domain,
        jurisdictions=body.jurisdictions or project.jurisdictions,
        stakeholder_role=body.stakeholder_role,
    )


@router.get("/{project_id}/workflow/status", response_model=WorkflowStatusOut)
async def get_project_workflow_status(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
):
    """Query current execution state and active approval interrupts."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    runner = get_workflow_runner()
    return await runner.get_status(session, project_id)


@router.post("/{project_id}/workflow/decide", response_model=WorkflowStatusOut)
async def decide_project_workflow_gate(
    project_id: uuid.UUID,
    decision_in: GateDecisionIn,
    session: AsyncSession = Depends(db_session),
):
    """Submit a human approval or rejection to clear an active gate interrupt.

    Enforces role competence. Unauthorized roles are rejected with 403 Forbidden.
    Resumes durable LangGraph execution.
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    try:
        role = StakeholderRole(decision_in.role)
    except ValueError:
        raise HTTPException(
            400,
            f"Invalid stakeholder role '{decision_in.role}'. Allowed: {[r.value for r in StakeholderRole]}",
        ) from None

    runner = get_workflow_runner()
    try:
        return await runner.decide(
            session=session,
            project_id=project_id,
            gate_name=decision_in.gate,
            decision=decision_in.decision,
            actor=decision_in.actor,
            role=role,
            comment=decision_in.comment,
        )
    except UnauthorisedApproverError as e:
        raise HTTPException(403, str(e)) from e
    except KeyError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/{project_id}/workflow/approvals", response_model=list[ApprovalOut])
async def list_project_approvals(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(db_session),
):
    """List all recorded human-in-the-loop approval gate decisions for this project."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    rows = (
        await session.execute(
            select(Approval)
            .where(Approval.project_id == project_id)
            .order_by(Approval.created_at.asc())
        )
    ).scalars().all()

    return [
        ApprovalOut(
            id=r.id,
            project_id=r.project_id,
            gate=r.gate,
            required_role=r.required_role,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            decided_by=r.decided_by,
            decided_at=r.decided_at,
            comment=r.comment,
            created_at=r.created_at,
        )
        for r in rows
    ]


__all__ = ["router"]
