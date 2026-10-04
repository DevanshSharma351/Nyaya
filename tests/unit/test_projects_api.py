"""Unit tests for project API management, deletion, and SDLC fallback."""

from __future__ import annotations

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from nyaya.api.app import create_app
from nyaya.api.deps import db_session
from nyaya.db.models import Project


@pytest.fixture
def app(session):
    application = create_app()
    application.dependency_overrides[db_session] = lambda: session
    return application


@pytest.mark.asyncio
async def test_project_crud_and_sdlc_fallback(app, session):
    project_id = uuid.uuid4()
    proj = Project(
        id=project_id,
        name="Test API Management Project",
        description="A project to test deletion and SDLC fallback",
        domain="fintech",
        jurisdictions=["IN", "EU"],
    )
    session.add(proj)
    await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Verify project appears in list
        resp = await client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert any(p["id"] == str(project_id) for p in data)

        # 2. Verify GET /api/projects/{id}
        resp = await client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test API Management Project"

        # 3. Verify GET /api/projects/{id}/sdlc generates on the fly when not pre-computed
        resp = await client.get(f"/api/projects/{project_id}/sdlc")
        assert resp.status_code == 200
        sdlc_data = resp.json()
        assert "recommendation" in sdlc_data
        assert "workflow" in sdlc_data
        assert sdlc_data["recommendation"]["recommended"] is not None

        # 4. Verify DELETE /api/projects/{id}
        resp = await client.delete(f"/api/projects/{project_id}")
        assert resp.status_code in (200, 204)

        # 5. Verify GET /api/projects/{id} returns 404 after deletion
        resp = await client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 404
