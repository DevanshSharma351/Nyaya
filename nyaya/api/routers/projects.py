"""Projects and their requirements."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nyaya.api.deps import db_session
from nyaya.api.schemas import (
    DefectOut,
    EvidenceOut,
    ProjectIn,
    ProjectOut,
    RequirementOut,
)
from nyaya.db.models import Project, Requirement

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
            id=p.id, name=p.name, domain=p.domain, jurisdictions=p.jurisdictions,
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
        id=project.id, name=project.name, domain=project.domain,
        jurisdictions=project.jurisdictions, status=project.status,
        created_at=project.created_at,
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
        id=project.id, name=project.name, domain=project.domain,
        jurisdictions=project.jurisdictions, status=project.status,
        created_at=project.created_at, requirement_count=count,
    )


__all__ = ["router"]
