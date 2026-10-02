"""Tests for Token & Cost Observability (Layer 8)."""

import pytest
from httpx import ASGITransport, AsyncClient

from nyaya.api.app import create_app
from nyaya.core import ledger
from nyaya.db.models import Project
from nyaya.llm.base import Usage, estimate_cost


def test_estimate_cost_rates():
    # Local models have zero API cost
    assert estimate_cost("ollama:qwen2.5-coder:7b", 1000, 500) == 0.0
    assert estimate_cost("local_model", 1000, 500) == 0.0

    # Gemini Flash
    cost_flash = estimate_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
    assert cost_flash == pytest.approx(0.375, rel=1e-3)

    # Claude Sonnet
    cost_sonnet = estimate_cost("claude-3-5-sonnet", 1_000_000, 1_000_000)
    assert cost_sonnet == pytest.approx(18.0, rel=1e-3)


def test_usage_properties():
    u = Usage(prompt_tokens=100, completion_tokens=50, model="gemini-2.5-flash", role="reasoning")
    assert u.total_tokens == 150
    assert u.cost_usd > 0.0


@pytest.mark.asyncio
async def test_project_usage_endpoint(session):
    project = Project(
        name="Observability Test Project",
        domain="ekyc_onboarding",
        description="A project for testing usage tracking",
        jurisdictions=["IN"],
    )
    session.add(project)
    await session.flush()

    # Record 2 LLM call events
    await ledger.record(
        session,
        project_id=project.id,
        event_type="llm_call",
        actor="gemini-2.5-flash",
        actor_kind="agent",
        payload={
            "agent": "extraction",
            "model": "gemini-2.5-flash",
            "prompt_tokens": 1200,
            "completion_tokens": 300,
            "total_tokens": 1500,
            "cost_usd": 0.00018,
            "repair_rounds": 1,
        },
        subject_kind="project",
        subject_id=project.id,
    )

    await ledger.record(
        session,
        project_id=project.id,
        event_type="llm_call",
        actor="gemini-2.5-flash",
        actor_kind="agent",
        payload={
            "agent": "compliance",
            "model": "gemini-2.5-flash",
            "prompt_tokens": 800,
            "completion_tokens": 200,
            "total_tokens": 1000,
            "cost_usd": 0.00012,
            "repair_rounds": 0,
        },
        subject_kind="project",
        subject_id=project.id,
    )
    await session.commit()

    # Test API endpoint
    from nyaya.api.deps import db_session

    app = create_app()
    app.dependency_overrides[db_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/projects/{project.id}/usage")
        assert resp.status_code == 200
        data = resp.json()

        assert data["project_id"] == str(project.id)
        assert data["total_calls"] == 2
        assert data["prompt_tokens"] == 2000
        assert data["completion_tokens"] == 500
        assert data["total_tokens"] == 2500
        assert data["total_cost_usd"] == pytest.approx(0.0003, rel=1e-3)
        assert len(data["by_agent"]) == 2
        assert len(data["events"]) == 2


@pytest.mark.asyncio
async def test_requirement_patch_and_delta_invalidation(session):
    import asyncio

    from nyaya.api.deps import db_session
    from nyaya.db.models import Requirement

    project = Project(
        name="Delta Test Project",
        domain="ekyc_onboarding",
        description="A project for testing delta invalidation",
        jurisdictions=["IN"],
    )
    session.add(project)
    await session.flush()

    req = Requirement(
        project_id=project.id,
        ref="REQ-001",
        statement="The system shall authenticate customers using biometrics.",
        categories=["security"],
    )
    session.add(req)
    await session.commit()

    app = create_app()
    app.dependency_overrides[db_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Generate SDLC
        sdlc_resp = await client.post(f"/api/projects/{project.id}/sdlc/generate")
        assert sdlc_resp.status_code == 200
        assert sdlc_resp.json()["is_stale"] is False

        # Wait a small slice so updated_at is strictly greater than assessment.created_at
        await asyncio.sleep(0.05)

        # 2. Patch requirement
        patch_resp = await client.patch(
            f"/api/projects/{project.id}/requirements/{req.id}",
            json={"priority": "must", "risk_level": "critical"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["priority"] == "must"
        assert patch_resp.json()["risk_level"] == "critical"

        # 3. Check SDLC is now stale
        get_sdlc = await client.get(f"/api/projects/{project.id}/sdlc")
        assert get_sdlc.status_code == 200
        assert get_sdlc.json()["is_stale"] is True

        # 4. Regenerate SDLC
        regen_sdlc = await client.post(f"/api/projects/{project.id}/sdlc/generate")
        assert regen_sdlc.status_code == 200
        assert regen_sdlc.json()["is_stale"] is False

