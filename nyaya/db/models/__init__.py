"""ORM models.

Imported as a package so that every mapper is registered with the declarative
base before Alembic autogenerates a migration; a model missing from here is
silently absent from the schema.
"""

from nyaya.db.models.audit import GENESIS_HASH, Approval, AuditEvent, PIIToken
from nyaya.db.models.knowledge import Clause, SourceDocument
from nyaya.db.models.project import Interview, Project, Stakeholder, Utterance
from nyaya.db.models.requirement import (
    Conflict,
    ControlMapping,
    Defect,
    Evidence,
    Requirement,
    TraceLink,
)
from nyaya.db.models.sdlc import SDLCAssessment, SDLCWorkflow

__all__ = [
    "GENESIS_HASH",
    "Approval",
    "AuditEvent",
    "Clause",
    "Conflict",
    "ControlMapping",
    "Defect",
    "Evidence",
    "Interview",
    "PIIToken",
    "Project",
    "Requirement",
    "SDLCAssessment",
    "SDLCWorkflow",
    "SourceDocument",
    "Stakeholder",
    "TraceLink",
    "Utterance",
]
