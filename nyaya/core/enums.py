"""Controlled vocabularies.

These are closed sets on purpose. Agents emit values from these enumerations
rather than free text, which is what makes downstream aggregation, rule
evaluation and metric computation well-defined.
"""

from __future__ import annotations

from enum import StrEnum


class RequirementCategory(StrEnum):
    """Requirement taxonomy.

    A requirement may carry several of these simultaneously - classification is
    multi-label, because e.g. an audit-logging requirement is legitimately both
    a security and a regulatory requirement.
    """

    BUSINESS = "business"
    STAKEHOLDER = "stakeholder"
    FUNCTIONAL = "functional"
    SECURITY = "security"
    PRIVACY = "privacy"
    REGULATORY = "regulatory"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    USABILITY = "usability"
    DATA_MANAGEMENT = "data_management"
    INTEGRATION = "integration"
    AUDIT_REPORTING = "audit_reporting"
    OPERATIONAL = "operational"


class Priority(StrEnum):
    """MoSCoW prioritisation."""

    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(StrEnum):
    """Lifecycle of an artefact awaiting human sign-off.

    Nothing reaches APPROVED without an identified human actor; this is the
    enforcement point for the human-in-the-loop requirement.
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    SUPERSEDED = "superseded"


class DefectType(StrEnum):
    """Quality defects the analysis agents detect in a requirement."""

    AMBIGUITY = "ambiguity"
    INCOMPLETENESS = "incompleteness"
    INCONSISTENCY = "inconsistency"
    DUPLICATION = "duplication"
    INFEASIBILITY = "infeasibility"
    UNTESTABLE = "untestable"
    MISSING_SOURCE = "missing_source"
    UNDEFINED_TERM = "undefined_term"
    CONFLICTING_EXPECTATION = "conflicting_expectation"
    MISSING_CONTROL = "missing_control"


class Severity(StrEnum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    BLOCKER = "blocker"


class StakeholderRole(StrEnum):
    """Whose requirement this is.

    Drives the role-specific interview templates, and is what makes
    stakeholder-conflict detection possible.
    """

    CUSTOMER = "customer"
    BUSINESS_ANALYST = "business_analyst"
    PRODUCT_OWNER = "product_owner"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    LEGAL = "legal"
    RISK = "risk"
    OPERATIONS = "operations"
    AUDITOR = "auditor"
    REGULATOR = "regulator"


class SDLCModel(StrEnum):
    """Candidate lifecycle models the selection engine ranks."""

    WATERFALL = "waterfall"
    V_MODEL = "v_model"
    SPIRAL = "spiral"
    AGILE = "agile"
    DEVSECOPS = "devsecops"
    AGILE_VMODEL_HYBRID = "agile_vmodel_hybrid"
    AGILE_DEVSECOPS_HYBRID = "agile_devsecops_hybrid"


class SensitivityLabel(StrEnum):
    """Data classification, assigned before any content reaches a model.

    RESTRICTED content is masked prior to egress; the reversible token vault
    rehydrates it only after human approval.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class EvidenceRelation(StrEnum):
    """How a cited source relates to the claim it is attached to.

    Determined by the NLI check, not by the generating model's assertion.
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


__all__ = [
    "ApprovalStatus",
    "DefectType",
    "EvidenceRelation",
    "Priority",
    "RequirementCategory",
    "RiskLevel",
    "SDLCModel",
    "SensitivityLabel",
    "Severity",
    "StakeholderRole",
]
