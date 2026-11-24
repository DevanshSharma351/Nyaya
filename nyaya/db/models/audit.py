"""Audit ledger, approvals, and the PII token vault.

The ledger is append-only and hash-chained: each event stores the hash of its
predecessor, so removing or altering any past event invalidates every hash after
it. This converts "we logged it" into "we can prove the log is intact", which is
the difference between a log and an audit record.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nyaya.core.enums import ApprovalStatus, SensitivityLabel
from nyaya.db.base import Base, StrEnumType, Timestamped, UUIDPrimaryKey

GENESIS_HASH = "0" * 64


class AuditEvent(Base, UUIDPrimaryKey):
    """One immutable entry in the tamper-evident ledger.

    Records every prompt, retrieval, agent decision, human edit and approval.
    There is deliberately no `updated_at` and no update path: entries are
    written once.
    """

    __tablename__ = "audit_event"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL")
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    """Position in the chain, unique per project. Gaps indicate tampering."""

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    """'llm_call' | 'retrieval' | 'agent_decision' | 'human_edit' |
    'approval' | 'rule_evaluation' | 'ingestion' | 'security_event'."""

    actor: Mapped[str] = mapped_column(String(256), nullable=False)
    """An agent name, or an authenticated human subject. Never anonymous."""

    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    """'agent' | 'human' | 'system' - separates automated from accountable acts."""

    subject_kind: Mapped[str | None] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID | None] = mapped_column()

    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    """Event detail. Sensitive values are masked before they reach this column."""

    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "sequence", name="uq_audit_event_sequence"),
        Index("ix_audit_event_project_seq", "project_id", "sequence"),
        Index("ix_audit_event_type", "event_type"),
        Index("ix_audit_event_subject", "subject_kind", "subject_id"),
    )

    @staticmethod
    def compute_hash(
        *,
        prev_hash: str,
        sequence: int,
        occurred_at: datetime,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> str:
        """Derive the chain hash for an entry.

        `payload` is serialised with sorted keys so that logically identical
        events hash identically regardless of dictionary ordering.
        """
        material = json.dumps(
            {
                "prev": prev_hash,
                "seq": sequence,
                "at": occurred_at.isoformat(),
                "type": event_type,
                "actor": actor,
                "payload": payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditEvent #{self.sequence} {self.event_type}>"


class Approval(Base, UUIDPrimaryKey, Timestamped):
    """A human decision on an artefact that requires sign-off.

    The brief mandates human approval for requirement baselines, regulatory
    interpretations, high-risk security requirements, conflict resolutions,
    architecture-critical requirements, SDLC selection, and changes to approved
    requirements. Each is an `Approval` row; the workflow cannot proceed past the
    corresponding graph interrupt until one exists.
    """

    __tablename__ = "approval"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )

    subject_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    gate: Mapped[str] = mapped_column(String(64), nullable=False)
    """Which mandatory checkpoint this satisfies, e.g. 'requirement_baseline'."""

    required_role: Mapped[str] = mapped_column(String(32), nullable=False)
    """Only a stakeholder holding this role may decide. A product owner cannot
    sign off a regulatory interpretation."""

    status: Mapped[ApprovalStatus] = mapped_column(
        StrEnumType(ApprovalStatus, 32), default=ApprovalStatus.PENDING_REVIEW, nullable=False
    )

    decided_by: Mapped[str | None] = mapped_column(String(256))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_approval_subject", "subject_kind", "subject_id"),
        Index("ix_approval_project_status", "project_id", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Approval {self.gate} {self.status}>"


class PIIToken(Base, UUIDPrimaryKey, Timestamped):
    """Reversible pseudonymisation vault.

    Detected PII is replaced with a surrogate before any text reaches a model;
    this table maps the surrogate back to the original. Storing the mapping
    separately from the working text means the model never sees real identifiers,
    while approved artefacts can still be rehydrated for human consumption.
    """

    __tablename__ = "pii_token"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )

    token: Mapped[str] = mapped_column(String(64), nullable=False)
    """The surrogate, e.g. '<PERSON_7f3a>'."""

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    """Presidio entity label - 'PERSON', 'IN_PAN', 'IN_AADHAAR', 'EMAIL_ADDRESS'."""

    original_value: Mapped[str] = mapped_column(Text, nullable=False)
    sensitivity: Mapped[SensitivityLabel] = mapped_column(
        StrEnumType(SensitivityLabel, 32), default=SensitivityLabel.RESTRICTED, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("project_id", "token", name="uq_pii_token"),
        Index("ix_pii_token_project", "project_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PIIToken {self.token} ({self.entity_type})>"


__all__ = ["GENESIS_HASH", "Approval", "AuditEvent", "PIIToken"]
