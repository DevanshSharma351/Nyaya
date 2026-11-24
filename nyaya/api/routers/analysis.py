"""Extraction, compliance coverage, SDLC recommendation and change impact."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from nyaya.agents.extraction import extract
from nyaya.agents.schemas import ExtractionContext
from nyaya.api.deps import db_session
from nyaya.api.schemas import (
    ActivityOut,
    AffectedOut,
    ArtefactsOut,
    BriefIn,
    ControlCoverageOut,
    CoverageOut,
    ExtractIn,
    FactorsIn,
    ImpactIn,
    ImpactOut,
    PhaseOut,
    RiskEntryOut,
    SDLCFromBriefOut,
    SDLCOut,
    SDLCRankOut,
    TraceRowOut,
    UseCaseOut,
    UserStoryOut,
    WorkflowIn,
    WorkflowOut,
)
from nyaya.artefacts import build as build_artefacts
from nyaya.core import ledger
from nyaya.core.enums import ApprovalStatus, RiskLevel, SDLCModel
from nyaya.db.models import Project, Requirement, SDLCAssessment, SDLCWorkflow
from nyaya.graph.impact import analyse_change
from nyaya.graph.persistence import save_extraction
from nyaya.ingestion.parsers import parse
from nyaya.ingestion.pii import redact_intake
from nyaya.mcda.derive import derive
from nyaya.mcda.sdlc import default_factors, recommend
from nyaya.mcda.workflow import Workflow
from nyaya.mcda.workflow import generate as generate_workflow
from nyaya.rules.engine import evaluate, requirement_facts

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _read_brief(data: bytes, suffix: str) -> str:
    with NamedTemporaryFile(suffix=suffix) as source:
        source.write(data)
        source.flush()
        if suffix == ".docx":
            with ZipFile(source.name) as archive:
                if sum(item.file_size for item in archive.infolist()) > 24 * 1024 * 1024:
                    raise ValueError("Word document exceeds the decompressed size limit")
        return parse(source.name).strip()


@router.post("/brief/text")
async def import_brief(upload: UploadFile) -> dict[str, str]:
    """Extract a redacted, editable brief from a stakeholder document."""
    suffix = Path(upload.filename or "").suffix.lower()
    size_limit = 5 * 1024 * 1024
    try:
        if suffix not in {".pdf", ".docx", ".txt", ".md"}:
            raise HTTPException(415, "Choose a PDF, Word, text, or Markdown file.")
        data = await upload.read(size_limit + 1)
    finally:
        await upload.close()
    if len(data) > size_limit:
        raise HTTPException(413, "The file exceeds the 5 MB upload limit.")
    try:
        text = await run_in_threadpool(_read_brief, data, suffix)
    except Exception as exc:
        raise HTTPException(422, "Could not read this document as text.") from exc
    if not text:
        raise HTTPException(422, "No selectable text was found in this document.")
    if len(text) > 50_000:
        raise HTTPException(413, "Import a section with at most 50,000 characters.")
    return {"text": redact_intake(text)}


def _with_clarifications(payload: ExtractIn | BriefIn) -> str:
    """Fold answered questions back into the source text.

    Appended as stated input, attributed to the stakeholder, so extraction and
    every downstream check treat them exactly as they treat the original brief.
    """
    clarifications = getattr(payload, "clarifications", [])
    if not clarifications:
        return payload.text
    answered = "\n".join(
        f"Clarification — {c.question.rstrip('?')}? {c.answer}" for c in clarifications
    )
    return f"{payload.text}\n\n{answered}"


@router.post("/extract")
async def extract_requirements(
    payload: ExtractIn, session: AsyncSession = Depends(db_session)
):
    """Turn stakeholder text into structured, quality-checked requirements.

    Defects are returned alongside each requirement rather than filtered out:
    the point of the quality layer is that a reviewer sees what is wrong with a
    statement, not that weak statements are quietly dropped.

    The extraction result is persisted as a Project with Requirements so that
    downstream modules (SDLC, Artefacts, Coverage) can operate on the
    project_id without re-running the LLM.
    """
    project = None
    previous = []
    if payload.project_id:
        project = await session.get(Project, payload.project_id, with_for_update=True)
        if project is None:
            raise HTTPException(404, "project not found")
        if not payload.clarifications:
            raise HTTPException(422, "Provide clarification answers to update this brief.")
        previous = list((await session.scalars(
            select(Requirement).where(Requirement.project_id == project.id)
        )).all())
        if any(row.approval_status == ApprovalStatus.APPROVED for row in previous):
            raise HTTPException(409, "Edit the approved requirements to propose a new version.")
        payload = payload.model_copy(update={
            "text": project.description or payload.text,
            "domain": project.domain,
            "jurisdictions": project.jurisdictions,
        })

    try:
        result = await extract(
            _with_clarifications(payload),
            context=ExtractionContext(
                domain=payload.domain, jurisdictions=payload.jurisdictions,
                stakeholder_role=payload.stakeholder_role,
            ),
        )
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "rate limit" in str(e).lower():
            raise HTTPException(429, "LLM rate limit exceeded. Please wait a minute and try again.") from e
        raise

    # Persist project + requirements so downstream endpoints can reuse them
    source_text = result.source_text or redact_intake(_with_clarifications(payload))
    title = (redact_intake(payload.title) if payload.title else source_text.split("\n")[0][:100]).strip()
    if len(title) < 5:
        title = "Requirement Analysis"

    if project is None:
        project = Project(name=title, domain=payload.domain, jurisdictions=payload.jurisdictions)
        session.add(project)
    project.description = source_text
    await session.flush()

    save_extraction(
        session, project, source_text, result.requirements, result.unclear, result.model,
        previous=previous,
    )

    await session.flush()

    # Record LLM token/cost usage in the audit ledger
    await ledger.record(
        session,
        project_id=project.id,
        event_type="llm_call",
        actor=result.model,
        actor_kind="agent",
        payload={
            "agent": "extraction",
            "model": result.model,
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
            "cost_usd": result.usage.cost_usd,
            "repair_rounds": result.repair_rounds,
        },
        subject_kind="project",
        subject_id=project.id,
    )

    return {
        "project_id": str(project.id),
        "model": result.model,
        "repair_rounds": result.repair_rounds,
        "usage": {
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
            "cost_usd": result.usage.cost_usd,
        },
        "notes": result.notes,
        "testable_fraction": result.testable_fraction,
        "unclear": result.unclear,
        "requirements": [
            {
                "statement": item.requirement.statement,
                "rationale": item.requirement.rationale,
                "categories": [c.value for c in item.requirement.categories],
                "priority": item.requirement.priority.value,
                "risk_level": item.requirement.risk_level.value,
                "acceptance_criteria": item.requirement.acceptance_criteria,
                "assumptions": item.requirement.assumptions,
                "quoted_source": item.requirement.quoted_source,
                "ears_pattern": item.ears_pattern,
                "is_testable": item.is_testable,
                "defects": [
                    {
                        "type": d.defect_type.value,
                        "severity": d.severity.value,
                        "detail": d.detail,
                        "detector": d.detector,
                    }
                    for d in item.defects
                ],
            }
            for item in result.requirements
        ],
    }


@router.post("/coverage", response_model=list[CoverageOut])
async def control_coverage(payload: ExtractIn):
    """Which mandatory controls a set of requirement statements covers.

    Accepts statements directly so the panel can be driven without persisting a
    project first - exploring coverage is a normal thing to do before committing
    to a baseline.
    """
    statements = [s.strip() for s in payload.text.split("\n") if s.strip()]
    facts = [
        (
            f"R{i:03d}",
            requirement_facts(
                statement=s, categories=["regulatory", "security", "functional"],
                jurisdictions=payload.jurisdictions, domain=payload.domain,
            ),
        )
        for i, s in enumerate(statements, start=1)
    ]
    reports = evaluate(facts, domain=payload.domain, jurisdictions=payload.jurisdictions)
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


def _to_sdlc_out(result) -> SDLCOut:
    """Shape a ranking result for the wire."""
    return SDLCOut(
        recommended=result.recommended.value,
        ranked=[
            SDLCRankOut(
                model=r.name, percentage=r.percentage,
                closeness=round(r.closeness, 4),
                drivers=dict(
                    sorted(r.contributions.items(), key=lambda kv: -kv[1])[:5]
                ),
            )
            for r in result.ranking.rankings
        ],
        close_call=result.close_call,
        consistency_ratio=round(result.weights.consistency_ratio, 4),
        notes=result.notes,
        explanation=result.ranking.explain(),
    )


@router.post("/sdlc", response_model=SDLCOut)
async def recommend_sdlc(payload: FactorsIn):
    """Rank lifecycle models against a factor profile supplied directly."""
    unknown = set(payload.overrides) - set(default_factors())
    if unknown:
        raise HTTPException(422, f"unknown factors: {sorted(unknown)}")
    return _to_sdlc_out(recommend(default_factors(**payload.overrides)))


@router.post("/sdlc/from-brief", response_model=SDLCFromBriefOut)
async def recommend_sdlc_from_brief(
    payload: BriefIn, session: AsyncSession = Depends(db_session)
):
    """Recommend a lifecycle for a project described in plain language."""
    if not payload.text.strip():
        raise HTTPException(422, "a brief is required")

    try:
        result = await extract(
            _with_clarifications(payload),
            context=ExtractionContext(
                domain=payload.domain, jurisdictions=payload.jurisdictions
            ),
        )
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "rate limit" in str(e).lower():
            raise HTTPException(429, "LLM rate limit exceeded. Please wait a minute and try again.") from e
        raise
    source_text = result.source_text or redact_intake(_with_clarifications(payload))
    derivation = derive(result.requirements, result.unclear, brief=source_text)
    ranking = recommend(derivation.factors)
    critical = sum(
        1
        for item in result.requirements
        if item.requirement.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    )
    workflow = generate_workflow(
        ranking.recommended,
        critical_requirements=critical,
        open_questions=len(result.unclear),
    )
    
    title = redact_intake(payload.title) if payload.title else source_text.split("\n")[0][:100]
    if len(title) < 5:
        title = "SDLC Assessment"
        
    project = Project(
        name=title,
        domain=payload.domain,
        description=source_text,
        jurisdictions=payload.jurisdictions,
    )
    session.add(project)
    await session.flush()
    
    save_extraction(session, project, source_text, result.requirements, result.unclear, result.model)
        
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
                "name": p.name,
                "purpose": p.purpose,
                "entry_criteria": p.entry_criteria,
                "exit_criteria": p.exit_criteria,
                "activities": [
                    {
                        "name": a.name,
                        "role": a.role,
                        "because": a.because,
                        "security": a.security,
                        "compliance": a.compliance,
                    } for a in p.activities
                ],
                "deliverables": p.deliverables,
                "roles": p.roles,
                "gate": p.gate,
            } for p in workflow.phases
        ],
        gates=[],
    )
    session.add(wf)
    await session.flush()

    await ledger.record(
        session,
        project_id=project.id,
        event_type="llm_call",
        actor=result.model,
        actor_kind="agent",
        payload={
            "agent": "extraction",
            "model": result.model,
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
            "cost_usd": result.usage.cost_usd,
            "repair_rounds": result.repair_rounds,
        },
        subject_kind="project",
        subject_id=project.id,
    )

    response = SDLCFromBriefOut(
        project_id=project.id,
        recommendation=_to_sdlc_out(ranking),
        workflow=_to_workflow_out(workflow),
        factors=derivation.factors,
        observations=derivation.observations,
        requirements_extracted=len(result.requirements),
        unclear=result.unclear,
    )
    await record_sdlc_snapshot(session, assessment, response)
    return response


async def record_sdlc_snapshot(
    session: AsyncSession, assessment: SDLCAssessment, response: SDLCFromBriefOut,
) -> None:
    """Keep the presented rationale and workflow with the persisted assessment."""
    await ledger.record(
        session, project_id=assessment.project_id, event_type="sdlc_assessment",
        actor="sdlc_engine", actor_kind="system", subject_kind="sdlc_assessment",
        subject_id=assessment.id, payload=response.model_dump(mode="json"),
    )


def _to_workflow_out(workflow: Workflow) -> WorkflowOut:
    return WorkflowOut(
        model=workflow.model.value,
        cadence=workflow.cadence,
        phases=[
            PhaseOut(
                name=phase.name,
                purpose=phase.purpose,
                entry_criteria=phase.entry_criteria,
                exit_criteria=phase.exit_criteria,
                activities=[
                    ActivityOut(
                        name=a.name, role=a.role, because=a.because,
                        security=a.security, compliance=a.compliance,
                    )
                    for a in phase.activities
                ],
                deliverables=phase.deliverables,
                roles=phase.roles,
                gate=phase.gate,
            )
            for phase in workflow.phases
        ],
        traceability=workflow.traceability,
        notes=workflow.notes,
    )


@router.post("/sdlc/workflow", response_model=WorkflowOut)
async def sdlc_workflow(payload: WorkflowIn):
    """Generate the project-specific workflow for a chosen lifecycle.

    Separate from the recommendation because the two are different decisions: a
    team may reject the ranking and still want the workflow for the model they
    chose instead.
    """
    try:
        model = SDLCModel(payload.model)
    except ValueError:
        raise HTTPException(
            422, f"unknown lifecycle model {payload.model!r}"
        ) from None
    return _to_workflow_out(
        generate_workflow(
            model,
            blocking_gaps=payload.blocking_gaps,
            critical_requirements=payload.critical_requirements,
            open_questions=payload.open_questions,
            legacy_integration=payload.legacy_integration,
        )
    )


@router.post("/artefacts", response_model=ArtefactsOut)
async def generate_artefacts(payload: ExtractIn):
    """Produce the artefact set the brief lists as expected outputs.

    Derived from an extraction rather than written by a model: the statements
    are the ones that passed the quality checks, the acceptance criteria are the
    extracted ones, and the traceability matrix is the join the system has been
    maintaining all along. A generated SRS containing requirements nobody
    approved would be indistinguishable from one containing requirements they
    did, which is the whole problem this system exists to avoid.
    """
    try:
        result = await extract(
            _with_clarifications(payload),
            context=ExtractionContext(
                domain=payload.domain, jurisdictions=payload.jurisdictions
            ),
        )
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "rate limit" in str(e).lower():
            raise HTTPException(429, "LLM rate limit exceeded. Please wait a minute and try again.") from e
        raise
    artefacts = build_artefacts(
        result.requirements, project=payload.domain, unclear=result.unclear
    )
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


@router.post("/impact", response_model=ImpactOut)
async def regulatory_impact(
    payload: ImpactIn, session: AsyncSession = Depends(db_session)
):
    """Which requirements an amendment invalidates."""
    try:
        report = await analyse_change(
            session,
            short_code=payload.short_code,
            from_version=payload.from_version,
            to_version=payload.to_version,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    return ImpactOut(
        summary=report.summary(),
        changed_clauses=report.changed_clauses,
        removed_clauses=report.removed_clauses,
        added_clauses=report.added_clauses,
        affected=[
            AffectedOut(
                ref=a.ref, statement=a.statement, severity=a.severity,
                citation_key=a.citation_key, detail=a.detail,
            )
            for a in report.affected
        ],
    )


__all__ = ["router"]
