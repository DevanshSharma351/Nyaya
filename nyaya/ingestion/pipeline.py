"""Ingest a source document into the clause knowledge base.

Parse -> split into clauses -> embed -> persist, with provenance recorded on
every unit. Ingestion is **idempotent by content hash**: re-ingesting an
unchanged file is a no-op, and a changed file creates a *new version* rather
than mutating the existing one, because a clause that has already been cited
must never change underneath the citation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.core import ledger
from nyaya.db.models import Clause, SourceDocument
from nyaya.ingestion.clause_splitter import ClauseNode, flatten, split_clauses
from nyaya.ingestion.parsers import content_hash, parse
from nyaya.retrieval.embedder import embed_texts


@dataclass(slots=True)
class IngestionReport:
    document_id: uuid.UUID
    short_code: str
    version: str
    clauses_created: int
    skipped: bool = False
    superseded_id: uuid.UUID | None = None

    def __str__(self) -> str:  # pragma: no cover
        if self.skipped:
            return f"{self.short_code} v{self.version}: unchanged, skipped"
        return f"{self.short_code} v{self.version}: {self.clauses_created} clauses"


async def ingest_document(
    session: AsyncSession,
    path: str | Path,
    *,
    short_code: str,
    title: str,
    issuer: str,
    jurisdiction: str,
    doc_type: str = "regulation",
    version: str = "1",
    effective_from: date | None = None,
    embed: bool = True,
    project_id: uuid.UUID | None = None,
) -> IngestionReport:
    """Ingest one document, or skip it if an identical version already exists."""
    path = Path(path)
    digest = content_hash(path)

    existing = (
        (
            await session.execute(
                select(SourceDocument)
                .where(SourceDocument.short_code == short_code)
                .order_by(SourceDocument.created_at.desc())
            )
        )
        .scalars()
        .first()
    )

    if existing is not None and existing.content_hash == digest:
        return IngestionReport(
            document_id=existing.id,
            short_code=short_code,
            version=existing.version,
            clauses_created=0,
            skipped=True,
        )

    raw_text = parse(path)
    roots = split_clauses(raw_text, short_code=short_code)
    nodes = flatten(roots)

    document = SourceDocument(
        title=title,
        short_code=short_code,
        issuer=issuer,
        jurisdiction=jurisdiction,
        doc_type=doc_type,
        version=version,
        effective_from=effective_from,
        content_hash=digest,
        source_uri=str(path),
        supersedes_id=existing.id if existing else None,
    )
    session.add(document)
    await session.flush()

    # The previous version stays in the database - superseded, not deleted - so
    # that citations made against it remain resolvable and change-impact
    # analysis can compare the two.
    if existing is not None:
        existing.effective_to = effective_from or date.today()

    vectors: list[list[float]] = []
    if embed and nodes:
        vectors = await embed_texts([_embedding_text(n) for n in nodes])

    by_node: dict[int, Clause] = {}
    for index, node in enumerate(nodes):
        clause = Clause(
            document_id=document.id,
            citation_key=node.citation_key,
            clause_number=node.number,
            # Only record a heading when it is distinct from the body, so
            # `Clause.display` cannot repeat it.
            heading=node.heading
            if not (node.text or "").startswith(node.heading or "\x00")
            else None,
            text=_clause_text(node) or (node.heading or ""),
            depth=node.depth,
            ordinal=node.ordinal,
            char_start=node.char_start,
            char_end=node.char_end,
            embedding=vectors[index] if vectors else None,
        )
        by_node[id(node)] = clause
        session.add(clause)

    await session.flush()

    # Parent links are set in a second pass, because a child may be flushed
    # before its parent has an assigned primary key.
    for node in nodes:
        for child in node.children:
            by_node[id(child)].parent_id = by_node[id(node)].id

    await session.flush()

    await ledger.record(
        session,
        project_id=project_id,
        event_type="ingestion",
        actor="ingestion_pipeline",
        actor_kind="system",
        subject_kind="source_document",
        subject_id=document.id,
        payload={
            "short_code": short_code,
            "version": version,
            "clauses": len(nodes),
            "content_hash": digest,
            "supersedes": str(existing.id) if existing else None,
        },
    )

    return IngestionReport(
        document_id=document.id,
        short_code=short_code,
        version=version,
        clauses_created=len(nodes),
        superseded_id=existing.id if existing else None,
    )


def _embedding_text(node: ClauseNode) -> str:
    """The text a clause is embedded as.

    The heading is prepended only when it is genuinely a heading. For a
    sub-clause the splitter records the remainder of the marker line as
    `heading`, and that same text also opens `text` - so concatenating them
    duplicated the sentence, wasting tokens and skewing both the embedding and
    the entailment premise.
    """
    return _clause_text(node) or (node.number or "")


def _clause_text(node: ClauseNode) -> str:
    """The clause body, de-duplicated and unwrapped.

    Source documents are hard-wrapped, so a clause arrives with newlines mid
    sentence. Unwrapping matters because the text becomes an NLI premise and a
    retrieval unit, and both read it as prose.
    """
    text = " ".join((node.text or "").split())
    heading = " ".join((node.heading or "").split())
    if heading and text.startswith(heading):
        return text  # heading is the opening of the body, not a separate line
    return f"{heading} {text}".strip() if heading else text


__all__ = ["IngestionReport", "ingest_document"]
