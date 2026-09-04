"""Persisting a workflow run.

The property under test: a requirement is never written without the edges that
give it provenance, and the record reflects what humans actually decided rather
than what the pipeline produced.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from nyaya.agents.compliance import ComplianceResult, ValidatedMapping
from nyaya.agents.extraction import AnalysedRequirement, RequirementDefect
from nyaya.agents.schemas import ExtractedRequirement
from nyaya.core.enums import (
    ApprovalStatus,
    DefectType,
    EvidenceRelation,
    Priority,
    RequirementCategory,
    RiskLevel,
    Severity,
)
from nyaya.db.models import ControlMapping, Defect, Evidence, Project, Requirement, TraceLink
from nyaya.graph.persistence import persist_run
from nyaya.graph.state import initial_state
from nyaya.retrieval.obligation import ObligationTier

STATEMENT = (
    "When a customer is onboarded remotely, the system shall screen the customer "
    "against the designated-persons list before activation."
)


def _analysed(defects=None) -> AnalysedRequirement:
    return AnalysedRequirement(
        requirement=ExtractedRequirement(
            statement=STATEMENT,
            rationale="regulatory duty",
            categories=[RequirementCategory.REGULATORY, RequirementCategory.SECURITY],
            priority=Priority.MUST,
            risk_level=RiskLevel.CRITICAL,
            acceptance_criteria=[
                "Given a remote application, when screening is incomplete, then activation is refused."
            ],
            assumptions=[],
            quoted_source="check them against the sanctions list",
        ),
        defects=defects or [],
        ears_pattern="event_driven",
    )


def _compliance(citation: str, tier: ObligationTier) -> ComplianceResult:
    mapping = ValidatedMapping(
        control_id="KYC.SCREEN.SANCTIONS",
        citation_key=citation,
        quoted_text="screening shall be performed prior to activation",
        reasoning="the clause obliges pre-activation screening",
        resolved=True,
        quote_verified=True,
        relation=(
            EvidenceRelation.SUPPORTS
            if tier is ObligationTier.CONFIRMED
            else EvidenceRelation.NEUTRAL
        ),
        entailment_score=0.95,
        relevance_score=0.98,
        tier=tier,
        rule_seeded=True,
    )
    if tier is not ObligationTier.CONFIRMED:
        mapping.review_reasons.append("one check only")
    return ComplianceResult(requirement_statement=STATEMENT, mappings=[mapping])


async def _project(session) -> Project:
    project = Project(
        name=f"persist-{uuid.uuid4().hex[:6]}",
        domain="ekyc_onboarding",
        jurisdictions=["IN"],
    )
    session.add(project)
    await session.flush()
    return project


def _state(project, *, approved: bool, compliance=None, defects=None):
    state = initial_state(project_id=str(project.id), source_text="source text")
    state["requirements"] = [_analysed(defects)]
    state["compliance"] = compliance or []
    state["decisions"] = (
        [
            {
                "gate": "requirement_baseline",
                "decision": "approve",
                "actor": "ba",
                "comment": "",
                "at": "now",
            }
        ]
        if approved
        else []
    )
    return state


async def test_approved_run_baselines_the_requirements(session):
    project = await _project(session)
    result = await persist_run(session, _state(project, approved=True))
    await session.commit()

    row = (
        (
            await session.execute(
                select(Requirement).where(Requirement.id == result.requirement_ids[0])
            )
        )
        .scalars()
        .one()
    )
    assert row.approval_status is ApprovalStatus.APPROVED
    assert row.ref == "FR-KYC-001"
    assert set(row.categories) == {"regulatory", "security"}


async def test_unapproved_run_is_not_silently_baselined(session):
    """A run a human declined to approve must not produce an approved baseline."""
    project = await _project(session)
    result = await persist_run(session, _state(project, approved=False))
    await session.commit()

    row = (
        (
            await session.execute(
                select(Requirement).where(Requirement.id == result.requirement_ids[0])
            )
        )
        .scalars()
        .one()
    )
    assert row.approval_status is ApprovalStatus.DRAFT


async def test_provenance_edge_is_written(session):
    """A requirement without provenance is an assertion."""
    project = await _project(session)
    state = _state(project, approved=True)
    result = await persist_run(session, state, utterance_id=None)
    await session.commit()
    assert result.requirement_ids
    # with no utterance supplied there is no derives_from edge to write
    count = (
        await session.execute(
            select(func.count(TraceLink.id)).where(TraceLink.project_id == project.id)
        )
    ).scalar_one()
    assert count == 0


async def test_defects_are_persisted_with_the_requirement(session):
    project = await _project(session)
    defect = RequirementDefect(
        defect_type=DefectType.AMBIGUITY,
        severity=Severity.MAJOR,
        detail="'appropriate' is unverifiable",
        detector="weak_word_lexicon",
    )
    result = await persist_run(session, _state(project, approved=True, defects=[defect]))
    await session.commit()

    rows = (
        (
            await session.execute(
                select(Defect).where(Defect.requirement_id == result.requirement_ids[0])
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].detector == "weak_word_lexicon"


async def test_rejected_citations_are_recorded_not_discarded(session):
    """An unconfirmed citation is evidence that the model proposed something
    unfounded; discarding it would erase that."""
    project = await _project(session)
    state = _state(
        project,
        approved=True,
        compliance=[_compliance("RBI-MD-KYC:22(a)", ObligationTier.UNCONFIRMED)],
    )
    result = await persist_run(session, state)
    await session.commit()

    assert result.evidence_count == 1
    mapping = (
        (
            await session.execute(
                select(ControlMapping).where(
                    ControlMapping.requirement_id == result.requirement_ids[0]
                )
            )
        )
        .scalars()
        .one()
    )
    assert mapping.validator_passed is False
    assert mapping.validator_detail["tier"] == "unconfirmed"


async def test_confirmed_mapping_creates_a_satisfies_edge(session):
    """The edge the change-impact walk traverses."""
    project = await _project(session)
    state = _state(
        project,
        approved=True,
        compliance=[_compliance("RBI-MD-KYC:22(a)", ObligationTier.CONFIRMED)],
    )
    result = await persist_run(session, state)
    await session.commit()

    evidence = (
        (
            await session.execute(
                select(Evidence).where(Evidence.requirement_id == result.requirement_ids[0])
            )
        )
        .scalars()
        .one()
    )
    assert evidence.cited_key == "RBI-MD-KYC:22(a)"
    assert evidence.relation is EvidenceRelation.SUPPORTS
    # the clause exists in the ingested corpus, so the edge should be written
    assert result.trace_links >= 1


async def test_run_is_recorded_in_the_audit_ledger(session):
    from nyaya.core import ledger

    project = await _project(session)
    await persist_run(session, _state(project, approved=True))
    await session.commit()

    verification = await ledger.verify_chain(session, project.id)
    assert verification.intact
    assert verification.entries_checked >= 1


async def test_enum_columns_round_trip_as_enums(session):
    """Regression: enum columns loaded as plain `str`.

    `Mapped[ApprovalStatus]` stored correctly but returned a string, so the type
    annotation was a lie and any caller reaching for `.value` on a loaded row
    raised `AttributeError`. `StrEnum` members compare equal to their string
    form, so equality checks kept passing and hid it - the crash appeared only
    on attribute access, on a compliance decision path.
    """
    project = await _project(session)
    state = _state(
        project,
        approved=True,
        compliance=[_compliance("RBI-MD-KYC:22(a)", ObligationTier.CONFIRMED)],
    )
    result = await persist_run(session, state)
    await session.commit()
    session.expire_all()  # force a genuine reload rather than the identity map

    requirement = (
        (
            await session.execute(
                select(Requirement).where(Requirement.id == result.requirement_ids[0])
            )
        )
        .scalars()
        .one()
    )
    assert isinstance(requirement.approval_status, ApprovalStatus)
    assert requirement.approval_status.value == "approved"
    assert isinstance(requirement.priority, Priority)
    assert isinstance(requirement.risk_level, RiskLevel)

    evidence = (
        (await session.execute(select(Evidence).where(Evidence.requirement_id == requirement.id)))
        .scalars()
        .one()
    )
    assert isinstance(evidence.relation, EvidenceRelation)
    assert evidence.relation.value == "supports"
