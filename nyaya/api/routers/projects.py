"""Projects and their requirements.

Includes project-based generate endpoints that reuse persisted extraction
results instead of re-running the LLM. The Artefact, SDLC, and Coverage
modules are deterministic — they need only the requirements already in the
database, not a new extraction call.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nyaya.api.deps import db_session
from nyaya.api.schemas import (
    ActivityOut,
    ArtefactsOut,
    ControlCoverageOut,
    CoverageOut,
    DefectOut,
    EvidenceOut,
    PhaseOut,
    ProjectIn,
    ProjectOut,
    RequirementOut,
    RiskEntryOut,
    SDLCFromBriefOut,
    SDLCOut,
    SDLCRankOut,
    TraceRowOut,
    UseCaseOut,
    UserStoryOut,
    WorkflowOut,
)
from nyaya.artefacts import build as build_artefacts
from nyaya.core.enums import Priority, RequirementCategory, RiskLevel
from nyaya.db.models import Project, Requirement, SDLCAssessment, SDLCWorkflow
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
    """Convert persisted Requirement rows into the shape build_artefacts expects."""
    items = []
    for r in rows:
        cats = []
        for c in (r.categories or []):
            try:
                cats.append(RequirementCategory(c))
            except ValueError:
                pass
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
                for d in (r.defects if hasattr(r, 'defects') and r.defects else [])
            ],
        ))
    return items


async def _load_requirements(session: AsyncSession, project_id: uuid.UUID) -> list[Requirement]:
    """Load a project's requirements, raising 404 if the project doesn't exist."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    rows = (
        await session.execute(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.ref)
        )
    ).scalars().all()
    if not rows:
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
    rows = await _load_requirements(session, project_id)
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


__all__ = ["router"]
