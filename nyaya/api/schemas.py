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


class Clarification(BaseModel):
    """An open question, and the answer a stakeholder gave for it."""

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class ExtractIn(BaseModel):
    text: str = Field(min_length=1)
    domain: str = "ekyc_onboarding"
    jurisdictions: list[str] = Field(default_factory=lambda: ["IN"])

    clarifications: list[Clarification] = Field(default_factory=list)
    """Answers to questions a previous extraction raised.

    These are folded into the source text rather than passed to the model as a
    side channel, and that is the whole point. Every requirement here has to
    quote the text it came from, and every quantity in it is checked against
    that text - a threshold that appears in no source is a fabrication, which is
    the failure mode this system exists to prevent. An answer supplied out of
    band would let a real, human-supplied number look exactly like an invented
    one. Folded in, an answered question simply becomes more stated input, and
    the same checks apply to it unchanged.
    """


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


class BriefIn(BaseModel):
    """A project brief in the stakeholder's own words."""

    text: str = Field(min_length=1)
    domain: str = "ekyc_onboarding"
    jurisdictions: list[str] = Field(default_factory=lambda: ["IN"])
    clarifications: list[Clarification] = Field(default_factory=list)


class SDLCFromBriefOut(BaseModel):
    """The recommendation, plus everything needed to challenge it.

    The derived factor vector and the observations behind it are returned, not
    just the ranking. A lifecycle recommendation an architect cannot re-derive
    is one they cannot argue with, and the factors are the step where the
    argument actually lives.
    """

    recommendation: SDLCOut
    factors: dict[str, float]
    observations: list[str]
    requirements_extracted: int
    unclear: list[str]
    workflow: WorkflowOut
    """The recommendation made concrete. A lifecycle name tells a team what to
    call their process; the workflow tells them how to run it, which is the half
    of "SDLC identification" a label alone does not deliver."""


# --- generated artefacts (brief §12) ----------------------------------------


class UserStoryOut(BaseModel):
    ref: str
    text: str
    role: str
    trigger: str | None
    acceptance_criteria: list[str]


class UseCaseOut(BaseModel):
    ref: str
    name: str
    actor: str
    precondition: str
    main_flow: list[str]
    postcondition: str
    exceptions: list[str]


class TraceRowOut(BaseModel):
    ref: str
    statement: str
    source_quote: str
    citations: list[str]
    controls: list[str]
    verification: list[str]
    approval_status: str
    confidence: float | None
    gaps: list[str]
    """Blank columns, reported rather than hidden. An incomplete chain is the
    finding a traceability matrix exists to surface."""


class RiskEntryOut(BaseModel):
    ref: str
    description: str
    category: str
    level: str
    score: int
    treatment: str
    owner: str


class ArtefactsOut(BaseModel):
    project: str
    generated_at: datetime
    user_stories: list[UserStoryOut]
    use_cases: list[UseCaseOut]
    traceability: list[TraceRowOut]
    traceability_coverage: float
    risks: list[RiskEntryOut]
    open_issues: list[str]
    assumptions: list[str]


# --- generated lifecycle workflow (brief §15) --------------------------------


class ActivityOut(BaseModel):
    name: str
    role: str
    because: str | None
    security: bool
    compliance: bool


class PhaseOut(BaseModel):
    name: str
    purpose: str
    entry_criteria: list[str]
    exit_criteria: list[str]
    activities: list[ActivityOut]
    deliverables: list[str]
    roles: list[str]
    gate: str | None


class WorkflowOut(BaseModel):
    model: str
    cadence: str
    phases: list[PhaseOut]
    traceability: list[str]
    notes: list[str]


class WorkflowIn(BaseModel):
    """Which lifecycle, and what the analysis found about the project."""

    model: str
    blocking_gaps: int = Field(default=0, ge=0)
    critical_requirements: int = Field(default=0, ge=0)
    open_questions: int = Field(default=0, ge=0)
    legacy_integration: bool = False


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
    "ActivityOut",
    "AffectedOut",
    "ArtefactsOut",
    "BriefIn",
    "Clarification",
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
    "PhaseOut",
    "ProjectIn",
    "ProjectOut",
    "RequirementOut",
    "RiskEntryOut",
    "SDLCFromBriefOut",
    "SDLCOut",
    "SDLCRankOut",
    "SearchIn",
    "TraceRowOut",
    "UseCaseOut",
    "UserStoryOut",
    "WorkflowIn",
    "WorkflowOut",
]
