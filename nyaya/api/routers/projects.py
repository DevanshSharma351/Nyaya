"""Projects and their requirements."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nyaya.api.deps import db_session
from nyaya.api.schemas import (
    ActivityOut,
    DefectOut,
    EvidenceOut,
    PhaseOut,
    ProjectIn,
    ProjectOut,
    RequirementOut,
    SDLCFromBriefOut,
    SDLCOut,
    SDLCRankOut,
    WorkflowOut,
)
from nyaya.db.models import Project, Requirement, SDLCAssessment, SDLCWorkflow

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

@router.get("/{project_id}/sdlc", response_model=SDLCFromBriefOut)
async def get_project_sdlc(project_id: uuid.UUID, session: AsyncSession = Depends(db_session)):
    assessment = (
        await session.execute(
            select(SDLCAssessment)
            .options(selectinload(SDLCAssessment.workflow))
            .where(SDLCAssessment.project_id == project_id)
            .order_by(SDLCAssessment.created_at.desc())
        )
    ).scalars().first()

    if not assessment:
        raise HTTPException(404, "no SDLC assessment found for this project")

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

    return SDLCFromBriefOut(
        project_id=project_id,
        recommendation=recommendation,
        workflow=workflow,
        factors=assessment.factors,
        observations=[],
        requirements_extracted=count,
        unclear=[],
    )
__all__ = ["router"]
