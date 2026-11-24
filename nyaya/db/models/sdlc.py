"""SDLC selection: the extracted factor vector, and the ranked recommendation.

The ranking is produced by AHP-weighted TOPSIS over `factors`, not by a model.
Both the factor vector and the full score table are persisted so that a
recommendation can be re-derived and challenged - a recommendation that cannot
be reproduced is not defensible to an architect or an auditor.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nyaya.core.enums import ApprovalStatus, SDLCModel
from nyaya.db.base import Base, StrEnumType, Timestamped, UUIDPrimaryKey


class SDLCAssessment(Base, UUIDPrimaryKey, Timestamped):
    """One SDLC recommendation for a project, at a point in time."""

    __tablename__ = "sdlc_assessment"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )

    factors: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    """The 13 decision factors, normalised to [0,1], each with the evidence that
    justified its value - requirement stability, regulatory criticality, security
    risk, complexity, legacy dependence, change frequency, and so on."""

    weights: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    """AHP-derived criterion weights."""

    consistency_ratio: Mapped[float | None] = mapped_column(Float)
    """AHP consistency ratio. Above 0.10 the pairwise judgements are incoherent
    and the weighting must be revised before the ranking means anything."""

    scores: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    """TOPSIS closeness coefficient per candidate model - the ranked output."""

    recommended: Mapped[SDLCModel] = mapped_column(StrEnumType(SDLCModel, 32), nullable=False)
    justification: Mapped[str | None] = mapped_column(Text)
    """Natural-language explanation. Generated *after* the ranking, describing a
    decision the mathematics already made."""

    approval_status: Mapped[ApprovalStatus] = mapped_column(
        StrEnumType(ApprovalStatus, 32), default=ApprovalStatus.DRAFT, nullable=False
    )

    workflow: Mapped[SDLCWorkflow | None] = relationship(
        back_populates="assessment", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (Index("ix_sdlc_assessment_project", "project_id"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SDLCAssessment {self.recommended}>"


class SDLCWorkflow(Base, UUIDPrimaryKey, Timestamped):
    """The project-specific lifecycle instantiated from the selected model.

    Phases, activities, roles, deliverables, security activities, validation
    gates and compliance checkpoints - generated from the recommendation and the
    project's own risk and regulatory profile, so that the output is a workflow
    for *this* project rather than a textbook diagram.
    """

    __tablename__ = "sdlc_workflow"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sdlc_assessment.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    model: Mapped[SDLCModel] = mapped_column(StrEnumType(SDLCModel, 32), nullable=False)
    phases: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    """Ordered phases; each carries activities, roles, deliverables, entry and
    exit criteria, security activities and compliance checkpoints."""

    gates: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    """Human-approval gates, with the role competent to clear each one."""

    assessment: Mapped[SDLCAssessment] = relationship(back_populates="workflow")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SDLCWorkflow {self.model} ({len(self.phases)} phases)>"


__all__ = ["SDLCAssessment", "SDLCWorkflow"]
