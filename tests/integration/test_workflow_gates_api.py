"""Integration tests for the LangGraph workflow and human-approval gates API."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from nyaya.agents.extraction import AnalysedRequirement
from nyaya.agents.schemas import ExtractedRequirement
from nyaya.api.app import create_app
from nyaya.api.deps import db_session
from nyaya.core.enums import (
    ApprovalStatus,
    Priority,
    RequirementCategory,
    RiskLevel,
)
from nyaya.core.ledger import verify_chain
from nyaya.db.models import Project, Requirement


def _requirement(statement: str, risk: RiskLevel = RiskLevel.HIGH) -> AnalysedRequirement:
    return AnalysedRequirement(
        requirement=ExtractedRequirement(
            statement=statement,
            rationale="Automated test requirement",
            categories=[RequirementCategory.REGULATORY, RequirementCategory.SECURITY],
            priority=Priority.MUST,
            risk_level=risk,
            acceptance_criteria=["Given biometric token, when verified, then access granted."],
            assumptions=[],
            quoted_source="biometric screening",
        ),
        defects=[],
        ears_pattern="ubiquitous",
    )


@pytest.fixture
def app(session):
    application = create_app()
    application.dependency_overrides[db_session] = lambda: session
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_list_workflow_gates(client: AsyncClient):
    """Verify that all mandatory gates are returned with competent roles."""
    resp = await client.get("/api/projects/workflow/gates")
    assert resp.status_code == 200
    gates = resp.json()
    assert len(gates) >= 6
    names = {g["name"] for g in gates}
    assert "requirement_baseline" in names
    assert "regulatory_interpretation" in names
    assert "compliance_gap" in names
    assert "sdlc_selection" in names

    baseline = next(g for g in gates if g["name"] == "requirement_baseline")
    assert "business_analyst" in baseline["required_roles"]
    assert "product_owner" in baseline["required_roles"]


async def test_workflow_lifecycle_gates_and_ledger(session, client: AsyncClient):
    """Test start -> gate suspension -> DB Approval -> decision -> ledger verification."""
    # 1. Setup project and existing requirement
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        name=f"test-wf-{uuid.uuid4().hex[:6]}",
        domain="ekyc_onboarding",
        jurisdictions=["IN"],
    )
    session.add(project)

    req = Requirement(
        project_id=project_id,
        ref="FR-TEST-001",
        version=1,
        statement="The system shall screen all onboarded users against designated sanctions.",
        categories=["regulatory", "security"],
        priority=Priority.MUST,
        risk_level=RiskLevel.HIGH,
        acceptance_criteria=["Screening verified before activation."],
        assumptions=[],
        approval_status=ApprovalStatus.DRAFT,
    )
    session.add(req)
    await session.commit()

    # 2. Start the workflow
    resp = await client.post(
        f"/api/projects/{project_id}/workflow/start",
        json={"domain": "ekyc_onboarding", "jurisdictions": ["IN"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "waiting_approval"
    assert data["current_gate"] == "requirement_baseline"
    assert data["gate_payload"] is not None
    assert data["requirement_count"] >= 1

    # 3. Check that an Approval row was created in PENDING_REVIEW
    approvals_resp = await client.get(f"/api/projects/{project_id}/workflow/approvals")
    assert approvals_resp.status_code == 200
    approvals = approvals_resp.json()
    assert len(approvals) == 1
    assert approvals[0]["gate"] == "requirement_baseline"
    assert approvals[0]["status"] == "pending_review"

    # 4. Attempt unauthorized decision (e.g. role "customer" or invalid gate)
    unauth_resp = await client.post(
        f"/api/projects/{project_id}/workflow/decide",
        json={
            "gate": "requirement_baseline",
            "decision": "approve",
            "actor": "user@example.com",
            "role": "customer",
            "comment": "trying to approve without authority",
        },
    )
    assert unauth_resp.status_code == 403
    assert "cannot clear gate" in unauth_resp.json()["detail"]

    # 5. Submit authorized approval
    auth_resp = await client.post(
        f"/api/projects/{project_id}/workflow/decide",
        json={
            "gate": "requirement_baseline",
            "decision": "approve",
            "actor": "ba@bank.example",
            "role": "business_analyst",
            "comment": "Requirements verified against stakeholder brief.",
        },
    )
    assert auth_resp.status_code == 200
    after_data = auth_resp.json()
    assert len(after_data["decisions"]) >= 1
    assert after_data["decisions"][0]["actor"] == "ba@bank.example"
    assert after_data["decisions"][0]["decision"] == "approve"

    # 6. Verify that Approval table was updated
    approvals_after = (await client.get(f"/api/projects/{project_id}/workflow/approvals")).json()
    baseline_approval = next(a for a in approvals_after if a["gate"] == "requirement_baseline")
    assert baseline_approval["status"] == "approved"
    assert baseline_approval["decided_by"] == "ba@bank.example"

    # 7. Verify tamper-evident audit ledger chain
    audit = await verify_chain(session, project_id)
    assert audit.intact
    assert audit.entries_checked >= 1


async def test_workflow_rejection_halts(session, client: AsyncClient):
    """Verify that human rejection immediately halts the pipeline."""
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        name=f"test-halt-{uuid.uuid4().hex[:6]}",
        domain="ekyc_onboarding",
        jurisdictions=["IN"],
    )
    session.add(project)
    req = Requirement(
        project_id=project_id,
        ref="FR-HALT-001",
        version=1,
        statement="The system shall record biometric scans.",
        categories=["security"],
        priority=Priority.MUST,
        risk_level=RiskLevel.MEDIUM,
        acceptance_criteria=["Scans stored."],
        assumptions=[],
        approval_status=ApprovalStatus.DRAFT,
    )
    session.add(req)
    await session.commit()

    # Start
    await client.post(f"/api/projects/{project_id}/workflow/start")

    # Reject
    reject_resp = await client.post(
        f"/api/projects/{project_id}/workflow/decide",
        json={
            "gate": "requirement_baseline",
            "decision": "reject",
            "actor": "po@bank.example",
            "role": "product_owner",
            "comment": "Scope is not approved by leadership.",
        },
    )
    assert reject_resp.status_code == 200
    data = reject_resp.json()
    assert data["status"] == "halted"
    assert data["halted"] is True
    assert "rejected by po@bank.example" in data["halt_reason"]

    # Check status endpoint confirms halted
    status_resp = await client.get(f"/api/projects/{project_id}/workflow/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "halted"
