"""Requirements and the structures that make their claims auditable.

The design commitment here: a requirement is never trusted on its own. It carries
`Evidence` (what source supports it, and whether that source *entails* it),
`Defect` records (what is wrong with it), `Conflict` edges (what it contradicts),
and `ControlMapping` rows (which regulatory control it satisfies). Confidence is
computed from those, never asserted by the generating model.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nyaya.core.enums import (
    ApprovalStatus,
    DefectType,
    EvidenceRelation,
    Priority,
    RiskLevel,
    Severity,
)
from nyaya.db.base import Base, StrEnumType, Timestamped, UUIDPrimaryKey

if TYPE_CHECKING:
    from nyaya.db.models.project import Utterance


class Requirement(Base, UUIDPrimaryKey, Timestamped):
    """A single structured requirement.

    **Versioning is by supersession, not mutation.** Once a requirement reaches
    APPROVED it becomes an immutable baseline; a change creates a new row whose
    `supersedes_id` points at the old one, which moves to SUPERSEDED. Baselines
    must be reconstructible at any past date for audit, which in-place updates
    would destroy.
    """

    __tablename__ = "requirement"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )

    ref: Mapped[str] = mapped_column(String(64), nullable=False)
    """Human-facing identifier, e.g. 'FR-KYC-001'."""

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    statement: Mapped[str] = mapped_column(Text, nullable=False)
    """A single testable assertion, normalised to an EARS-style template."""

    categories: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    """Multi-label: one requirement is legitimately security *and* regulatory."""

    priority: Mapped[Priority] = mapped_column(StrEnumType(Priority, 16), default=Priority.SHOULD, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(StrEnumType(RiskLevel, 16), default=RiskLevel.LOW, nullable=False)

    business_justification: Mapped[str | None] = mapped_column(Text)
    acceptance_criteria: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    assumptions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # --- provenance ---
    source_utterance_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("utterance.id", ondelete="SET NULL")
    )
    source_stakeholder_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("stakeholder.id", ondelete="SET NULL")
    )
    source_utterance: Mapped[Utterance | None] = relationship()

    # --- confidence ---
    # Fused from retrieval score, NLI entailment, self-consistency and validator
    # outcome. Components are retained so a low score can be explained, and so
    # calibration can be measured per-component during evaluation.
    confidence: Mapped[float | None] = mapped_column(Float)
    confidence_components: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # --- approval ---
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        StrEnumType(ApprovalStatus, 32), default=ApprovalStatus.DRAFT, nullable=False
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirement.id", ondelete="SET NULL")
    )

    generated_by: Mapped[str | None] = mapped_column(String(128))
    """Which agent and model produced this, for the model-attribution audit."""

    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )
    defects: Mapped[list[Defect]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )
    control_mappings: Mapped[list[ControlMapping]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "ref", "version", name="uq_requirement_ref_version"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
        Index("ix_requirement_project_status", "project_id", "approval_status"),
        Index("ix_requirement_categories", "categories", postgresql_using="gin"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Requirement {self.ref} v{self.version}>"


class Evidence(Base, UUIDPrimaryKey, Timestamped):
    """A citation linking a requirement to a clause, with a *verified* relation.

    `relation` is set by the NLI model, not by the agent that produced the
    citation. A citation whose clause does not entail the claim is recorded as
    NEUTRAL or CONTRADICTS and counts against citation correctness - which is
    how hallucinated citations are caught rather than trusted.
    """

    __tablename__ = "evidence"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False
    )
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clause.id", ondelete="SET NULL")
    )

    cited_key: Mapped[str] = mapped_column(String(256), nullable=False)
    """What the model claimed to cite, kept verbatim even when it resolves to
    nothing - an unresolvable citation is itself a finding."""

    quoted_text: Mapped[str | None] = mapped_column(Text)

    relation: Mapped[EvidenceRelation] = mapped_column(
        StrEnumType(EvidenceRelation, 16), default=EvidenceRelation.NEUTRAL, nullable=False
    )
    entailment_score: Mapped[float | None] = mapped_column(Float)
    retrieval_score: Mapped[float | None] = mapped_column(Float)
    rerank_score: Mapped[float | None] = mapped_column(Float)

    resolved: Mapped[bool] = mapped_column(default=False, nullable=False)
    """Whether `cited_key` resolved to a real clause in the versioned KB."""

    requirement: Mapped[Requirement] = relationship(back_populates="evidence")

    __table_args__ = (Index("ix_evidence_requirement", "requirement_id"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Evidence {self.cited_key} {self.relation}>"


class Defect(Base, UUIDPrimaryKey, Timestamped):
    """A quality problem detected in a requirement."""

    __tablename__ = "defect"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False
    )

    defect_type: Mapped[DefectType] = mapped_column(StrEnumType(DefectType, 32), nullable=False)
    severity: Mapped[Severity] = mapped_column(StrEnumType(Severity, 16), default=Severity.MINOR, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    span_start: Mapped[int | None] = mapped_column(Integer)
    span_end: Mapped[int | None] = mapped_column(Integer)
    """Character span of the offending text, so the UI can highlight it."""

    detector: Mapped[str] = mapped_column(String(64), nullable=False)
    """Which check fired. Deterministic detectors ('weak_word_lexicon',
    'ears_template') are distinguished from LLM ones so their relative
    contribution can be measured in the ablation."""

    resolved: Mapped[bool] = mapped_column(default=False, nullable=False)

    requirement: Mapped[Requirement] = relationship(back_populates="defects")

    __table_args__ = (Index("ix_defect_requirement_type", "requirement_id", "defect_type"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Defect {self.defect_type} {self.severity}>"


class Conflict(Base, UUIDPrimaryKey, Timestamped):
    """A contradiction or duplication between two requirements.

    Stored as an edge rather than a per-requirement flag, because the useful
    question is always "which pair", and because stakeholder-conflict resolution
    needs both sides and their respective sources.
    """

    __tablename__ = "conflict"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    left_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False
    )
    right_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False
    )

    conflict_type: Mapped[str] = mapped_column(String(32), nullable=False)
    """'contradiction' | 'duplication' | 'overlap' | 'stakeholder_disagreement'."""

    severity: Mapped[Severity] = mapped_column(StrEnumType(Severity, 16), default=Severity.MAJOR, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    similarity: Mapped[float | None] = mapped_column(Float)
    contradiction_score: Mapped[float | None] = mapped_column(Float)
    """From the NLI model. The candidate pair is proposed by cheap embedding
    clustering; only flagged pairs reach the LLM adjudicator."""

    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String(256))
    """Conflicts between stakeholder groups are resolved by a human, never by
    the system - recorded here as the accountable party."""

    __table_args__ = (
        UniqueConstraint("left_id", "right_id", name="uq_conflict_pair"),
        CheckConstraint("left_id <> right_id", name="no_self_conflict"),
        Index("ix_conflict_project", "project_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Conflict {self.conflict_type}>"


class ControlMapping(Base, UUIDPrimaryKey, Timestamped):
    """A requirement mapped to a regulatory or security control.

    `validator_passed` is the deterministic check's verdict, kept separate from
    the LLM's proposal. The gap between "model proposed" and "validator accepted"
    is a headline evaluation metric.
    """

    __tablename__ = "control_mapping"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), nullable=False
    )

    control_id: Mapped[str] = mapped_column(String(128), nullable=False)
    """Control identifier from the rule pack, e.g. 'KYC.CDD.SANCTIONS-SCREEN'."""

    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clause.id", ondelete="SET NULL")
    )
    jurisdiction: Mapped[str | None] = mapped_column(String(64))

    proposed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    """'llm' | 'rule' - mappings the rule pack derives deterministically are
    distinguished from those a model proposed."""

    validator_passed: Mapped[bool | None] = mapped_column()
    validator_detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_gap: Mapped[bool] = mapped_column(default=False, nullable=False)
    """True when a mandatory control has no requirement satisfying it. Gaps are
    the actionable output of compliance analysis."""

    requirement: Mapped[Requirement] = relationship(back_populates="control_mappings")

    __table_args__ = (
        UniqueConstraint("requirement_id", "control_id", name="uq_control_mapping"),
        Index("ix_control_mapping_control", "control_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ControlMapping {self.control_id}>"


class TraceLink(Base, UUIDPrimaryKey, Timestamped):
    """A generic edge in the traceability graph.

    Deliberately untyped at the endpoints (`kind` + UUID rather than a foreign
    key per entity type) so the graph can span heterogeneous artefacts -
    utterance, requirement, clause, control, test case, deliverable - without a
    join table per pair. This is what regulatory-change impact analysis walks.
    """

    __tablename__ = "trace_link"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )

    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    relation: Mapped[str] = mapped_column(String(32), nullable=False)
    """'derives_from' | 'satisfies' | 'verifies' | 'refines' | 'conflicts_with'."""

    __table_args__ = (
        UniqueConstraint(
            "source_kind", "source_id", "target_kind", "target_id", "relation",
            name="uq_trace_link_edge",
        ),
        Index("ix_trace_link_source", "source_kind", "source_id"),
        Index("ix_trace_link_target", "target_kind", "target_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TraceLink {self.source_kind}->{self.target_kind} ({self.relation})>"


__all__ = [
    "Conflict",
    "ControlMapping",
    "Defect",
    "Evidence",
    "Requirement",
    "TraceLink",
]
