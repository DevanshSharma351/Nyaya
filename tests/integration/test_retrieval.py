"""Retrieval against the real corpus in the real database.

The corpus is ingested into the test database by a session fixture, so these
run on a clean checkout without any manual setup. They used to guard on "does
the database contain any clauses at all", which passed on unrelated rows
committed by other fixtures and then failed on the assertions.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from nyaya.db.models import Clause, SourceDocument
from nyaya.retrieval.embedder import embed_query
from nyaya.retrieval.hybrid import (
    dense_search,
    lexical_search,
    resolve_citation,
)


@pytest.fixture
async def corpus(corpus_ingested):
    return corpus_ingested


async def test_dense_retrieval_finds_paraphrased_obligation(session, corpus):
    """The query shares almost no vocabulary with the clause it should find."""
    vector = await embed_query(
        "check every new customer against the sanctions list before the account goes live"
    )
    results = await dense_search(session, vector, limit=10)
    keys = [r.citation_key for r in results]
    assert any(k.startswith("RBI-MD-KYC:22") for k in keys), keys


async def test_lexical_retrieval_matches_terms_of_art(session, corpus):
    """Exact legal categories are what the lexical arm exists for."""
    results = await lexical_search(session, "beneficial owner ownership structure", limit=10)
    keys = [r.citation_key for r in results]
    assert any(k.startswith("RBI-MD-KYC:16") for k in keys), keys


async def test_lexical_query_is_disjunctive(session, corpus):
    """A long conversational query must still match.

    Regression: Postgres's query builders conjoin terms, so a fifteen-word
    question matched zero clauses and the whole lexical arm was inert.
    """
    long_query = (
        "we have to check every new customer against the sanctions list before "
        "their account goes live and keep a record of it"
    )
    assert await lexical_search(session, long_query, limit=10)


async def test_citation_resolution_is_exact(session, corpus):
    """The validator's lookup must resolve a real key and reject an invented one."""
    assert await resolve_citation(session, "RBI-MD-KYC:16(b)") is not None
    assert await resolve_citation(session, "RBI-MD-KYC:99(z)") is None


async def test_jurisdiction_scope_is_enforced(session, corpus):
    """Retrieval must not return a clause from an inapplicable jurisdiction."""
    vector = await embed_query("security of processing personal data")
    results = await dense_search(session, vector, limit=20, jurisdictions=["EU"])
    assert results
    assert {r.jurisdiction for r in results} == {"EU"}


async def test_superseded_documents_are_excluded(session, corpus):
    """A clause from a repealed source must never be citable as current.

    Citing a regulation no longer in force is a compliance failure wearing the
    costume of a citation.
    """
    doc = (await session.execute(select(SourceDocument).limit(1))).scalars().one()
    original_end = doc.effective_to
    try:
        from datetime import date

        doc.effective_to = date(2020, 1, 1)
        await session.flush()

        vector = await embed_query("customer due diligence")
        results = await dense_search(session, vector, limit=50)
        assert doc.short_code not in {r.document_code for r in results}
    finally:
        doc.effective_to = original_end
        await session.flush()


async def test_clause_hierarchy_is_persisted(session, corpus):
    """Sub-clauses must link to their parent, or upward context walking breaks."""
    child = (
        (await session.execute(select(Clause).where(Clause.citation_key == "RBI-MD-KYC:16(b)")))
        .scalars()
        .one()
    )
    assert child.parent_id is not None

    parent = (
        (await session.execute(select(Clause).where(Clause.id == child.parent_id))).scalars().one()
    )
    assert parent.citation_key == "RBI-MD-KYC:16"
