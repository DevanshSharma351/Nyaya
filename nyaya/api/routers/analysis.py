"""Extraction, compliance coverage, SDLC recommendation and change impact."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
from nyaya.core.enums import RiskLevel, SDLCModel
from nyaya.graph.impact import analyse_change
from nyaya.mcda.derive import derive
from nyaya.mcda.sdlc import default_factors, recommend
from nyaya.mcda.workflow import Workflow
from nyaya.mcda.workflow import generate as generate_workflow
from nyaya.rules.engine import evaluate, requirement_facts

router = APIRouter(prefix="/analysis", tags=["analysis"])


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
async def extract_requirements(payload: ExtractIn):
    """Turn stakeholder text into structured, quality-checked requirements.

    Defects are returned alongside each requirement rather than filtered out:
    the point of the quality layer is that a reviewer sees what is wrong with a
    statement, not that weak statements are quietly dropped.
    """
    result = await extract(
        _with_clarifications(payload),
        context=ExtractionContext(
            domain=payload.domain, jurisdictions=payload.jurisdictions
        ),
    )
    return {
        "model": result.model,
        "repair_rounds": result.repair_rounds,
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
async def recommend_sdlc_from_brief(payload: BriefIn):
    """Recommend a lifecycle for a project described in plain language.

    This is the path that makes the recommendation mean something. Setting the
    factor sliders by hand is choosing the answer and then computing it; here
    the brief is extracted into requirements first, and the factors are read off
    what was actually found - how much of it is regulatory, how much is high
    risk, how many questions the brief left open.

    It runs the extraction agent, so it is slow: a local model takes forty to a
    hundred seconds on a brief of a few sentences. That cost is the point. A
    recommendation produced instantly from a text box would be the model's
    opinion about the words, not a derivation from their content.
    """
    if not payload.text.strip():
        raise HTTPException(422, "a brief is required")

    result = await extract(
        _with_clarifications(payload),
        context=ExtractionContext(
            domain=payload.domain, jurisdictions=payload.jurisdictions
        ),
    )
    derivation = derive(result.requirements, result.unclear, brief=payload.text)
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
    return SDLCFromBriefOut(
        recommendation=_to_sdlc_out(ranking),
        workflow=_to_workflow_out(workflow),
        factors=derivation.factors,
        observations=derivation.observations,
        requirements_extracted=len(result.requirements),
        unclear=result.unclear,
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
    result = await extract(
        _with_clarifications(payload),
        context=ExtractionContext(
            domain=payload.domain, jurisdictions=payload.jurisdictions
        ),
    )
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
