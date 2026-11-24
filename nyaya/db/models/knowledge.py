"""The regulatory knowledge base.

Every retrievable unit is a **clause**: an addressable span of an authorised
source document carrying full provenance. Citation correctness is only
measurable because clauses are addressable and immutable once published, so
this schema is the foundation of the whole evidence story.
"""

from __future__ import annotations

import uuid
from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nyaya.core.enums import SensitivityLabel
from nyaya.db.base import EMBEDDING_DIM, Base, StrEnumType, Timestamped, UUIDPrimaryKey


class SourceDocument(Base, UUIDPrimaryKey, Timestamped):
    """An authorised source: a regulation, standard, policy or internal procedure.

    Documents are **version-scoped, not mutated**. When a regulator amends a
    Master Direction, a new SourceDocument row is created and the previous one
    is superseded. This is what makes regulatory-change impact analysis possible:
    the traceability graph can distinguish "cited the old version" from "cited
    the current version".
    """

    __tablename__ = "source_document"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    short_code: Mapped[str] = mapped_column(String(64), nullable=False)
    """Stable citation prefix, e.g. 'RBI-MD-KYC', 'GDPR', 'DPDP-2023'."""

    issuer: Mapped[str] = mapped_column(String(256), nullable=False)
    """Who published it - 'Reserve Bank of India', 'European Parliament'."""

    jurisdiction: Mapped[str] = mapped_column(String(64), nullable=False)
    """ISO-3166 code, or 'EU' / 'GLOBAL'. Drives applicability rules."""

    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    """'regulation' | 'standard' | 'policy' | 'procedure' | 'guidance'."""

    version: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    """Null means currently in force. Set when superseded."""

    is_authoritative: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    """False for reference material that may inform but may not be cited as
    grounds for a compliance claim."""

    source_uri: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    """SHA-256 of the raw file. Detects silent substitution of a source."""

    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_document.id", ondelete="SET NULL")
    )

    doc_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    clauses: Mapped[list[Clause]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("short_code", "version", name="uq_source_document_code_version"),
        Index("ix_source_document_jurisdiction", "jurisdiction"),
        Index("ix_source_document_effective", "effective_from", "effective_to"),
    )

    @classmethod
    def effective_on(cls, on_date: date | None = None):
        """SQL predicate for sources active on the requested date."""
        day = on_date or date.today()
        return ((cls.effective_from.is_(None)) | (cls.effective_from <= day)) & (
            cls.effective_to.is_(None) | (cls.effective_to > day)
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SourceDocument {self.short_code} v{self.version}>"


class Clause(Base, UUIDPrimaryKey, Timestamped):
    """One addressable clause of a source document.

    `citation_key` is the human-facing anchor a generated requirement points at
    (e.g. `RBI-MD-KYC:16(a)`). The deterministic validator resolves this key back
    to this row and checks that the cited text genuinely entails the claim - which
    is the mechanism that turns "the model said so" into "the source says so".

    `char_start` / `char_end` preserve the span within the parent document so a
    citation can be highlighted in the original, not merely named.
    """

    __tablename__ = "clause"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_document.id", ondelete="CASCADE"), nullable=False
    )

    citation_key: Mapped[str] = mapped_column(String(256), nullable=False)
    """Fully-qualified reference, e.g. 'RBI-MD-KYC:16(a)' or 'GDPR:Art.32(1)(b)'."""

    clause_number: Mapped[str | None] = mapped_column(String(64))
    heading: Mapped[str | None] = mapped_column(Text)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Hierarchy: clauses nest (Part > Chapter > Section > sub-clause). Retrieval
    # returns leaves, but a leaf often needs its parent for interpretive context.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clause.id", ondelete="CASCADE")
    )
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    """Position among siblings; preserves document order for reconstruction."""

    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)

    sensitivity: Mapped[SensitivityLabel] = mapped_column(
        StrEnumType(SensitivityLabel, 32), default=SensitivityLabel.PUBLIC, nullable=False
    )

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    """Dense vector for the semantic half of hybrid retrieval."""

    # Lexical half of hybrid retrieval. Generated by Postgres rather than the
    # application so it can never drift out of sync with `text`.
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(heading, '') || ' ' || text)",
            persisted=True,
        ),
    )

    document: Mapped[SourceDocument] = relationship(back_populates="clauses")
    children: Mapped[list[Clause]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped[Clause | None] = relationship(
        back_populates="children", remote_side="Clause.id"
    )

    __table_args__ = (
        UniqueConstraint("document_id", "citation_key", name="uq_clause_doc_citation"),
        Index("ix_clause_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_clause_citation_key", "citation_key"),
        # HNSW over cosine distance: bge-m3 vectors are normalised, and HNSW
        # gives materially better recall-at-latency than IVFFlat for a corpus of
        # this size without requiring a training step.
        Index(
            "ix_clause_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Clause {self.citation_key}>"


__all__ = ["Clause", "SourceDocument"]
