"""Engagement-side entities: the project, its stakeholders, and what they said.

`Utterance` is the anchor of the entire traceability chain. Every requirement
must trace back to an utterance or a source document; a requirement that traces
to neither is flagged `MISSING_SOURCE` by the quality agent. This is what makes
"each generated item remains linked to its original stakeholder statement"
enforceable rather than aspirational.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nyaya.core.enums import SensitivityLabel, StakeholderRole
from nyaya.db.base import Base, StrEnumType, Timestamped, UUIDPrimaryKey


class Project(Base, UUIDPrimaryKey, Timestamped):
    """A requirements-engineering engagement for one financial system."""

    __tablename__ = "project"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    """'ekyc_onboarding' | 'loan_origination' | ... - selects the applicable
    regulatory profile and interview templates."""

    description: Mapped[str | None] = mapped_column(Text)
    jurisdictions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    """Jurisdiction codes in scope. Constrains which clauses are retrievable."""

    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    stakeholders: Mapped[list[Stakeholder]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    interviews: Mapped[list[Interview]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Project {self.name}>"


class Stakeholder(Base, UUIDPrimaryKey, Timestamped):
    """A person or role that supplies requirements.

    `role` is load-bearing: it selects the interview template, weights the
    stakeholder's authority during conflict adjudication (a compliance officer
    overrides a product owner on a regulatory point), and determines which
    approvals they are competent to give.
    """

    __tablename__ = "stakeholder"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[StakeholderRole] = mapped_column(StrEnumType(StakeholderRole, 32), nullable=False)
    organisation: Mapped[str | None] = mapped_column(String(256))
    external_subject_id: Mapped[str | None] = mapped_column(String(256))
    """Identity-provider subject, linking this record to an authenticated user."""

    project: Mapped[Project] = relationship(back_populates="stakeholders")
    utterances: Mapped[list[Utterance]] = relationship(back_populates="stakeholder")

    __table_args__ = (Index("ix_stakeholder_project_role", "project_id", "role"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Stakeholder {self.name} ({self.role})>"


class Interview(Base, UUIDPrimaryKey, Timestamped):
    """One elicitation session - an adaptive interview, or an ingested transcript."""

    __tablename__ = "interview"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    stakeholder_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("stakeholder.id", ondelete="SET NULL")
    )

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="chat", nullable=False)
    """'chat' | 'transcript' | 'questionnaire' | 'email' | 'document'."""

    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)

    coverage: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    """Which topics from the interview template have been adequately covered.
    Drives the elicitation agent's decision to probe further or close - this is
    the mechanism behind "ask follow-up questions when an answer is incomplete"."""

    project: Mapped[Project] = relationship(back_populates="interviews")
    utterances: Mapped[list[Utterance]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Interview {self.title}>"


class Utterance(Base, UUIDPrimaryKey, Timestamped):
    """A single stakeholder statement - the atomic unit of provenance.

    Both `raw_text` and `masked_text` are retained: `masked_text` is what is sent
    to a model, `raw_text` never leaves the database. Requirements cite the
    utterance, so an auditor can always reconstruct exactly what a human said
    versus what the system inferred.
    """

    __tablename__ = "utterance"

    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview.id", ondelete="CASCADE"), nullable=False
    )
    stakeholder_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("stakeholder.id", ondelete="SET NULL")
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(32), nullable=False)
    """'stakeholder' | 'agent' - agent turns are retained so the question that
    elicited an answer is part of the audit record."""

    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    masked_text: Mapped[str | None] = mapped_column(Text)
    sensitivity: Mapped[SensitivityLabel] = mapped_column(
        StrEnumType(SensitivityLabel, 32), default=SensitivityLabel.INTERNAL, nullable=False
    )

    interview: Mapped[Interview] = relationship(back_populates="utterances")
    stakeholder: Mapped[Stakeholder | None] = relationship(back_populates="utterances")

    __table_args__ = (
        Index("ix_utterance_interview_sequence", "interview_id", "sequence"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Utterance {self.speaker}#{self.sequence}>"


__all__ = ["Interview", "Project", "Stakeholder", "Utterance"]
