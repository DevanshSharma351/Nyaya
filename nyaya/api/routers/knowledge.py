"""Knowledge-base endpoints: retrieval and citation resolution."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.api.deps import db_session
from nyaya.api.schemas import ClauseOut, SearchIn
from nyaya.db.models import Clause, SourceDocument
from nyaya.retrieval import SearchOptions, search
from nyaya.retrieval.hybrid import resolve_citation

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/search", response_model=list[ClauseOut])
async def search_clauses(payload: SearchIn, session: AsyncSession = Depends(db_session)):
    """Retrieve the clauses most likely to govern a query."""
    result = await search(
        session,
        payload.query,
        options=SearchOptions(top_k=payload.top_k, jurisdictions=payload.jurisdictions),
    )
    return [
        ClauseOut(
            citation_key=r.citation_key,
            text=r.text,
            heading=r.heading,
            document_code=r.document_code,
            jurisdiction=r.jurisdiction,
            relevance=r.rerank_score,
        )
        for r in result.results
    ]


@router.get("/clause/{citation_key:path}", response_model=ClauseOut)
async def get_clause(citation_key: str, session: AsyncSession = Depends(db_session)):
    """Resolve a citation key to its clause.

    404 rather than an empty result: an unresolvable citation is a finding, and
    a client must be able to tell it apart from a clause with no text.
    """
    clause = await resolve_citation(session, citation_key)
    if clause is None:
        raise HTTPException(404, f"No clause with citation key {citation_key!r}")
    return ClauseOut(
        citation_key=clause.citation_key,
        text=clause.text,
        heading=clause.heading,
        document_code=clause.document_code,
        jurisdiction=clause.jurisdiction,
    )


@router.get("/documents")
async def list_documents(session: AsyncSession = Depends(db_session)):
    """Sources in the knowledge base, with clause counts and known versions.

    Only in-force sources are listed, but every version of each is reported.
    That is not bookkeeping: change-impact analysis needs two versions to
    compare, and without this the interface had no way to know which sources
    have a second one. It offered all of them, and picking a source with a
    single version returned a 404 the reader had done nothing to deserve.
    """
    rows = (
        await session.execute(
            select(
                SourceDocument.short_code,
                SourceDocument.title,
                SourceDocument.issuer,
                SourceDocument.jurisdiction,
                SourceDocument.version,
                SourceDocument.effective_from,
                func.count(Clause.id).label("clauses"),
            )
            .outerjoin(Clause, Clause.document_id == SourceDocument.id)
            .where(SourceDocument.effective_to.is_(None))
            .group_by(SourceDocument.id)
            .order_by(SourceDocument.short_code)
        )
    ).all()

    # Every version of every short code, current or superseded.
    version_rows = (
        await session.execute(
            select(SourceDocument.short_code, SourceDocument.version).order_by(
                SourceDocument.short_code, SourceDocument.version
            )
        )
    ).all()
    versions: dict[str, list[str]] = {}
    for code, version in version_rows:
        versions.setdefault(code, []).append(version)

    return [
        {
            "short_code": r.short_code,
            "title": r.title,
            "issuer": r.issuer,
            "jurisdiction": r.jurisdiction,
            "version": r.version,
            "versions": versions.get(r.short_code, [r.version]),
            "effective_from": r.effective_from,
            "clauses": r.clauses,
        }
        for r in rows
    ]


__all__ = ["router"]
