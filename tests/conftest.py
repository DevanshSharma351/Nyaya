"""Shared test fixtures.

Integration tests run against the real Postgres from docker-compose rather than
SQLite: the schema depends on pgvector, generated tsvector columns, GIN/HNSW
indexes and advisory locks, none of which SQLite can emulate. A test that
passed against a substitute engine would not be evidence about the real one.

They run against a *separate database* on that server, though, and that is not
a detail. Several fixtures commit - an amendment scenario is only meaningful if
both versions of the document are actually persisted - so the session fixture's
rollback does not undo them. Pointed at the development database, the suite
therefore left its fixtures behind: twenty `TEST-MD-*` documents accumulated in
the corpus, and the API served them to the frontend alongside the real ones.
The failure was invisible from the tests, which passed throughout, and only
showed up as junk in the corpus listing.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import nyaya.db.models  # noqa: F401  - registers all mappers
from nyaya.config import get_settings
from nyaya.db import Base
from nyaya.db.models import Clause, Project, SourceDocument


def test_database_url() -> str:
    """The development database URL with `_test` appended to the database name."""
    return get_settings().database_url.rsplit("/", 1)[0] + "/nyaya_test"


async def _ensure_test_database() -> None:
    """Create the test database and its extensions if they do not exist.

    Connects to the server's default database to do it, because `CREATE
    DATABASE` cannot run inside a transaction or from within the database being
    created. Autocommit is required for the same reason.
    """
    admin_url = get_settings().database_url.rsplit("/", 1)[0] + "/postgres"
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("select 1 from pg_database where datname = 'nyaya_test'")
            )
            if not exists:
                await conn.execute(text("create database nyaya_test"))
    finally:
        await admin.dispose()

    # The extensions are per-database, so a freshly created one has none of
    # them and every pgvector column would fail to build.
    setup = create_async_engine(test_database_url(), isolation_level="AUTOCOMMIT")
    try:
        async with setup.connect() as conn:
            for statement in (
                "create extension if not exists vector",
                "create extension if not exists pg_trgm",
                'create extension if not exists "uuid-ossp"',
                "alter database nyaya_test set default_text_search_config = "
                "'pg_catalog.english'",
            ):
                await conn.execute(text(statement))
    finally:
        await setup.dispose()


@pytest_asyncio.fixture(scope="session")
async def engine():
    await _ensure_test_database()
    eng = create_async_engine(test_database_url())
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


@pytest_asyncio.fixture(scope="session")
async def corpus_ingested(engine) -> int:
    """Ingest the bundled corpus into the test database, once.

    Retrieval tests used to guard on "are there any clauses?" and skip
    otherwise. Against a shared development database that worked, because the
    corpus happened to be there. Against a dedicated test database it is
    actively wrong: other fixtures commit clauses of their own, so the guard
    passed on fifty-six rows of unrelated test data and the assertions then
    failed looking for `RBI-MD-KYC:16(b)`.

    Ingesting it here makes the dependency explicit and the suite
    self-contained. It costs one embedding pass the first time a test database
    is created, and nothing on subsequent runs.
    """
    from pathlib import Path

    from nyaya.ingestion import ingest_document

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        present = await s.scalar(
            select(func.count(Clause.id))
            .select_from(Clause)
            .join(SourceDocument, SourceDocument.id == Clause.document_id)
            .where(SourceDocument.short_code == "RBI-MD-KYC")
        )
        if present:
            return int(present)

        root = Path(__file__).resolve().parents[1] / "knowledge_base" / "corpus"
        for spec in (
            ("RBI-MD-KYC.txt", "RBI-MD-KYC", "Master Direction on Know Your Customer",
             "Reserve Bank of India", "IN", date(2023, 1, 1)),
            ("DPDP-2023.txt", "DPDP-2023", "Digital Personal Data Protection Provisions",
             "Parliament of India", "IN", date(2023, 8, 11)),
            ("GDPR.txt", "GDPR", "General Data Protection Provisions",
             "European Parliament", "EU", date(2018, 5, 25)),
        ):
            filename, code, title, issuer, jurisdiction, effective = spec
            await ingest_document(
                s,
                root / filename,
                short_code=code,
                title=title,
                issuer=issuer,
                jurisdiction=jurisdiction,
                doc_type="regulation",
                effective_from=effective,
            )
        await s.commit()
        return int(
            await s.scalar(
                select(func.count(Clause.id))
                .select_from(Clause)
                .join(SourceDocument, SourceDocument.id == Clause.document_id)
                .where(SourceDocument.short_code == "RBI-MD-KYC")
            )
            or 0
        )


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
