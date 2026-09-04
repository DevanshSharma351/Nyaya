"""Extraction, compliance coverage, SDLC recommendation and change impact."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.agents.extraction import extract
from nyaya.agents.schemas import ExtractionContext
from nyaya.api.deps import db_session
from nyaya.api.schemas import (
    AffectedOut,
    ControlCoverageOut,
    CoverageOut,
    ExtractIn,
    FactorsIn,
    ImpactIn,
    ImpactOut,
    SDLCOut,
    SDLCRankOut,
)
from nyaya.graph.impact import analyse_change
from nyaya.mcda.sdlc import default_factors, recommend
from nyaya.rules.engine import evaluate, requirement_facts

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/extract")
async def extract_requirements(payload: ExtractIn):
    """Turn stakeholder text into structured, quality-checked requirements.

    Defects are returned alongside each requirement rather than filtered out:
    the point of the quality layer is that a reviewer sees what is wrong with a
    statement, not that weak statements are quietly dropped.
    """
    result = await extract(
        payload.text,
        context=ExtractionContext(
            domain=payload.domain, jurisdictions=payload.jurisdictions
        ),
    )
    return {
        "model": result.model,
        "repair_rounds": result.repair_rounds,
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


@router.post("/sdlc", response_model=SDLCOut)
async def recommend_sdlc(payload: FactorsIn):
    """Rank lifecycle models against a project's factor profile."""
    unknown = set(payload.overrides) - set(default_factors())
    if unknown:
        raise HTTPException(422, f"unknown factors: {sorted(unknown)}")

    result = recommend(default_factors(**payload.overrides))
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
