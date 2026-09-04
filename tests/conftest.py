"""Shared test fixtures.

Integration tests run against the real Postgres from docker-compose rather than
SQLite: the schema depends on pgvector, generated tsvector columns, GIN/HNSW
indexes and advisory locks, none of which SQLite can emulate. A test that
passed against a substitute engine would not be evidence about the real one.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import nyaya.db.models  # noqa: F401  - registers all mappers
from nyaya.config import get_settings
from nyaya.db import Base
from nyaya.db.models import Project


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(get_settings().database_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def project(session: AsyncSession) -> Project:
    p = Project(
        name=f"test-{uuid.uuid4().hex[:8]}",
        domain="ekyc_onboarding",
        jurisdictions=["IN", "EU"],
    )
    session.add(p)
    await session.commit()
    return p
