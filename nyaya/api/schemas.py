"""Request and response models for the HTTP API.

Kept separate from the ORM and from the agent schemas. The API contract should
be able to stay stable while the internal representation changes, and a response
model that is also a database row leaks storage decisions to every client.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from nyaya.core.enums import Priority, RequirementCategory, RiskLevel


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    domain: str = "ekyc_onboarding"
    description: str | None = None
    jurisdictions: list[str] = Field(default_factory=lambda: ["IN"])


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    domain: str
    jurisdictions: list[str]
    status: str
    created_at: datetime
    requirement_count: int = 0


class DefectOut(BaseModel):
    defect_type: str
    severity: str
    detail: str
    detector: str


class EvidenceOut(BaseModel):
    cited_key: str
    quoted_text: str | None
    relation: str
    entailment_score: float | None
    rerank_score: float | None
    resolved: bool


class RequirementOut(BaseModel):
    id: uuid.UUID
    ref: str
    statement: str
    categories: list[RequirementCategory]
    priority: Priority
    risk_level: RiskLevel
    approval_status: str
    confidence: float | None
    acceptance_criteria: list[str]
    defects: list[DefectOut] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)


class ExtractIn(BaseModel):
    text: str = Field(min_length=1)
    domain: str = "ekyc_onboarding"
    jurisdictions: list[str] = Field(default_factory=lambda: ["IN"])


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)
    jurisdictions: list[str] | None = None


class ClauseOut(BaseModel):
    citation_key: str
    text: str
    heading: str | None
    document_code: str
    jurisdiction: str
    relevance: float | None = None


class ControlCoverageOut(BaseModel):
    control_id: str
    title: str
    severity: str
    citations: list[str]
    satisfied_by: list[str]
    is_gap: bool


class CoverageOut(BaseModel):
    pack: str
    pack_version: str
    coverage_ratio: float
    controls: list[ControlCoverageOut]
    blocking_gaps: list[str]


class FactorsIn(BaseModel):
    """Optional overrides for the SDLC factor vector.

    Every factor defaults to neutral, so a caller supplies only what it knows.
    A partially-known profile is normal; demanding all thirteen would push the
    caller into inventing values.
    """

    overrides: dict[str, float] = Field(default_factory=dict)


class SDLCRankOut(BaseModel):
    model: str
    percentage: int
    closeness: float
    drivers: dict[str, float]


class SDLCOut(BaseModel):
    recommended: str
    ranked: list[SDLCRankOut]
    close_call: bool
    consistency_ratio: float
    notes: list[str]
    explanation: list[str]


class ImpactIn(BaseModel):
    short_code: str
    from_version: str
    to_version: str


class AffectedOut(BaseModel):
    ref: str
    statement: str
    severity: str
    citation_key: str
    detail: str


class ImpactOut(BaseModel):
    summary: str
    changed_clauses: list[str]
    removed_clauses: list[str]
    added_clauses: list[str]
    affected: list[AffectedOut]


class GraphNode(BaseModel):
    """A node in the traceability graph, for the 3D visualisation."""

    id: str
    kind: str  # "requirement" | "clause" | "control" | "document"
    label: str
    detail: str = ""
    status: str = ""
    weight: float = 1.0


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    strength: float = 1.0


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class HealthOut(BaseModel):
    status: str
    database: bool
    models: dict[str, bool]
    corpus_clauses: int


__all__ = [
    "AffectedOut",
    "ClauseOut",
    "ControlCoverageOut",
    "CoverageOut",
    "DefectOut",
    "EvidenceOut",
    "ExtractIn",
    "FactorsIn",
    "GraphEdge",
    "GraphNode",
    "GraphOut",
    "HealthOut",
    "ImpactIn",
    "ImpactOut",
    "ProjectIn",
    "ProjectOut",
    "RequirementOut",
    "SDLCOut",
    "SDLCRankOut",
    "SearchIn",
]
