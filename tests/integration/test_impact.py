"""Regulatory-change impact analysis.

The scenario is the one a bank actually faces: a regulator amends a Master
Direction, and the question is which requirements are now wrong. The test
ingests a real amendment and checks the walk finds them.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pytest

from nyaya.core.enums import ApprovalStatus, EvidenceRelation, Priority, RiskLevel
from nyaya.db.models import Evidence, Project, Requirement
from nyaya.graph.impact import analyse_change, controls_losing_authority
from nyaya.ingestion import ingest_document

ORIGINAL = """\
22. Screening Against Designated Lists
The Regulated Entity shall screen the customer against notified lists.
(a) screening shall be performed prior to activation of the account;
(b) a match shall be reported to the competent authority without delay.

26. Maintenance of Records
The Regulated Entity shall maintain records of customer identification.
(a) records shall be preserved for five years from cessation of the relationship;
"""

AMENDED = """\
22. Screening Against Designated Lists
The Regulated Entity shall screen the customer against notified lists.
(a) screening shall be performed prior to activation of the account and repeated every ninety days thereafter;
(b) a match shall be reported to the competent authority without delay.

26. Maintenance of Records
The Regulated Entity shall maintain records of customer identification.
"""


@pytest.fixture
async def amendment(session, tmp_path: Path):
    """Ingest two versions of the same source, the second superseding the first."""
    code = f"TEST-MD-{uuid.uuid4().hex[:6].upper()}"

    first = tmp_path / "v1.txt"
    first.write_text(ORIGINAL)
    await ingest_document(
        session,
        first,
        short_code=code,
        title="Test Direction",
        issuer="Test Authority",
        jurisdiction="IN",
        version="1",
        effective_from=date(2023, 1, 1),
        embed=False,
    )
    await session.commit()

    second = tmp_path / "v2.txt"
    second.write_text(AMENDED)
    await ingest_document(
        session,
        second,
        short_code=code,
        title="Test Direction",
        issuer="Test Authority",
        jurisdiction="IN",
        version="2",
        effective_from=date(2025, 1, 1),
        embed=False,
    )
    await session.commit()
    return code


async def test_amended_clause_is_detected(session, amendment):
    report = await analyse_change(session, short_code=amendment, from_version="1", to_version="2")
    assert f"{amendment}:22(a)" in report.changed_clauses
    # 22(b) is untouched and must not be reported - noise trains reviewers to skim
    assert f"{amendment}:22(b)" not in report.changed_clauses


async def test_removed_clause_is_detected(session, amendment):
    report = await analyse_change(session, short_code=amendment, from_version="1", to_version="2")
    assert f"{amendment}:26(a)" in report.removed_clauses


async def test_requirements_citing_an_amended_clause_become_stale(session, amendment):
    """The requirement may still be correct, but it must be re-verified."""
    project = Project(
        name=f"impact-{uuid.uuid4().hex[:6]}", domain="ekyc_onboarding", jurisdictions=["IN"]
    )
    session.add(project)
    await session.flush()

    requirement = Requirement(
        project_id=project.id,
        ref="FR-KYC-001",
        statement="The system shall screen the customer before activation.",
        categories=["regulatory"],
        priority=Priority.MUST,
        risk_level=RiskLevel.HIGH,
        approval_status=ApprovalStatus.APPROVED,
    )
    session.add(requirement)
    await session.flush()

    session.add(
        Evidence(
            requirement_id=requirement.id,
            cited_key=f"{amendment}:22(a)",
            relation=EvidenceRelation.SUPPORTS,
            resolved=True,
        )
    )
    await session.commit()

    report = await analyse_change(session, short_code=amendment, from_version="1", to_version="2")
    stale = [a for a in report.stale if a.ref == "FR-KYC-001"]
    assert stale, [a.ref for a in report.affected]
    assert "re-verified" in stale[0].detail


async def test_requirements_citing_a_removed_clause_become_orphaned(session, amendment):
    """A requirement whose authority no longer exists is a stronger finding than
    one whose authority merely changed."""
    project = Project(
        name=f"impact-{uuid.uuid4().hex[:6]}", domain="ekyc_onboarding", jurisdictions=["IN"]
    )
    session.add(project)
    await session.flush()

    requirement = Requirement(
        project_id=project.id,
        ref="FR-KYC-002",
        statement="The system shall retain records for five years.",
        categories=["regulatory"],
        priority=Priority.MUST,
        risk_level=RiskLevel.HIGH,
        approval_status=ApprovalStatus.APPROVED,
    )
    session.add(requirement)
    await session.flush()
    session.add(
        Evidence(
            requirement_id=requirement.id,
            cited_key=f"{amendment}:26(a)",
            relation=EvidenceRelation.SUPPORTS,
            resolved=True,
        )
    )
    await session.commit()

    report = await analyse_change(session, short_code=amendment, from_version="1", to_version="2")
    orphaned = [a for a in report.orphaned if a.ref == "FR-KYC-002"]
    assert orphaned
    assert "lost its stated authority" in orphaned[0].detail


async def test_unaffected_requirements_are_not_reported(session, amendment):
    """Reporting untouched requirements would make the report unusable."""
    project = Project(
        name=f"impact-{uuid.uuid4().hex[:6]}", domain="ekyc_onboarding", jurisdictions=["IN"]
    )
    session.add(project)
    await session.flush()
    requirement = Requirement(
        project_id=project.id,
        ref="FR-KYC-999",
        statement="The system shall report matches to the authority.",
        categories=["regulatory"],
        priority=Priority.MUST,
        risk_level=RiskLevel.LOW,
    )
    session.add(requirement)
    await session.flush()
    session.add(
        Evidence(
            requirement_id=requirement.id,
            cited_key=f"{amendment}:22(b)",
            relation=EvidenceRelation.SUPPORTS,
            resolved=True,
        )
    )
    await session.commit()

    report = await analyse_change(session, short_code=amendment, from_version="1", to_version="2")
    assert "FR-KYC-999" not in {a.ref for a in report.affected}


async def test_reflowed_text_is_not_reported_as_an_amendment(session, tmp_path):
    """Re-wrapping is not a change; treating it as one floods the report."""
    code = f"TEST-WRAP-{uuid.uuid4().hex[:6].upper()}"
    original = tmp_path / "a.txt"
    original.write_text("5. Duty\nThe entity shall do the thing promptly and fully.\n")
    await ingest_document(
        session,
        original,
        short_code=code,
        title="t",
        issuer="i",
        jurisdiction="IN",
        version="1",
        embed=False,
    )
    await session.commit()

    rewrapped = tmp_path / "b.txt"
    rewrapped.write_text("5. Duty\nThe entity shall do the thing\npromptly and fully.\n")
    await ingest_document(
        session,
        rewrapped,
        short_code=code,
        title="t",
        issuer="i",
        jurisdiction="IN",
        version="2",
        embed=False,
    )
    await session.commit()

    report = await analyse_change(session, short_code=code, from_version="1", to_version="2")
    assert report.changed_clauses == []


async def test_missing_version_is_rejected(session, amendment):
    with pytest.raises(ValueError, match="must be ingested"):
        await analyse_change(session, short_code=amendment, from_version="1", to_version="99")


async def test_controls_losing_authority_handles_empty_input(session):
    assert await controls_losing_authority(session, []) == []


async def test_each_requirement_clause_pair_is_reported_once(session, amendment):
    """A requirement with several edges to one clause is one item of work.

    Regression: the walk emitted one entry per evidence row, so a requirement
    re-extracted a few times - each run adding an edge to the same clause -
    appeared once per edge. A review queue of three real items reported itself
    as eleven, and the count is what a reviewer plans against.
    """
    project = Project(
        name=f"impact-{uuid.uuid4().hex[:6]}", domain="ekyc_onboarding", jurisdictions=["IN"]
    )
    session.add(project)
    await session.flush()

    requirement = Requirement(
        project_id=project.id,
        ref="FR-DUP-001",
        statement="The system shall screen the customer before activation.",
        categories=["regulatory"],
        priority=Priority.MUST,
        risk_level=RiskLevel.HIGH,
        approval_status=ApprovalStatus.APPROVED,
    )
    session.add(requirement)
    await session.flush()

    # Three edges to the same clause, as repeated extraction runs would leave.
    for relation in (
        EvidenceRelation.SUPPORTS,
        EvidenceRelation.NEUTRAL,
        EvidenceRelation.SUPPORTS,
    ):
        session.add(
            Evidence(
                requirement_id=requirement.id,
                cited_key=f"{amendment}:22(a)",
                relation=relation,
                resolved=True,
            )
        )
    await session.commit()

    report = await analyse_change(
        session, short_code=amendment, from_version="1", to_version="2"
    )

    mine = [a for a in report.affected if a.ref == "FR-DUP-001"]
    assert len(mine) == 1, [f"{a.ref}/{a.citation_key}" for a in mine]
    assert mine[0].citation_key == f"{amendment}:22(a)"
    assert mine[0].severity == "stale"
