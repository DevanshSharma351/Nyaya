"""The documents the brief asks the system to produce.

Section 1 names the expected outputs and section 12 lists them again: a
Software Requirements Specification, user stories with acceptance criteria,
use-case descriptions, a risk register, a compliance-control matrix, a
requirements traceability matrix, and an open-issues list. Everything upstream
exists to make these trustworthy, and until now none of them were produced - the
system could say a great deal about a requirement and hand over nothing a team
could take to a review.

**These are derived, not written by a model.** Every field is a projection of
data that already passed the checks: the statement is the approved one, the
citation is the verified one, the acceptance criteria are the extracted ones. A
model asked to write an SRS would produce fluent prose containing requirements
nobody approved, and the reader could not tell which was which. The one thing
that would justify generation - turning a requirement into a user story - is
done by template here, because a template that occasionally reads awkwardly is
better than a sentence that occasionally invents a user.

The traceability matrix is the artefact that matters most and is the cheapest to
produce honestly: it is the join the system has been maintaining all along.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from nyaya.core.enums import RequirementCategory, RiskLevel

# EARS statements begin with a condition clause. Splitting it off is what lets
# a user story name the trigger separately from the behaviour.
_TRIGGER = re.compile(
    r"^\s*(when|while|where|if)\s+(?P<trigger>.+?),\s*(?P<body>the\s+.+)$",
    re.IGNORECASE | re.DOTALL,
)
_ACTOR = re.compile(r"^the\s+(?P<actor>[\w\s-]+?)\s+shall\s+(?P<behaviour>.+)$", re.IGNORECASE)

# Who a requirement is *for*, inferred from its categories rather than guessed
# from its wording. Ordered: the first matching category wins, so a requirement
# that is both regulatory and functional is written for the compliance officer,
# which is who will actually be asked to sign it off.
BENEFICIARY: list[tuple[RequirementCategory, str]] = [
    (RequirementCategory.REGULATORY, "compliance officer"),
    (RequirementCategory.SECURITY, "security team"),
    (RequirementCategory.PRIVACY, "data protection officer"),
    (RequirementCategory.AUDIT_REPORTING, "auditor"),
    (RequirementCategory.OPERATIONAL, "operations team"),
    (RequirementCategory.INTEGRATION, "integrating system"),
    (RequirementCategory.PERFORMANCE, "customer"),
    (RequirementCategory.AVAILABILITY, "customer"),
    (RequirementCategory.USABILITY, "customer"),
]
DEFAULT_BENEFICIARY = "business"

RISK_SCORE = {
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


@dataclass(slots=True)
class UserStory:
    ref: str
    role: str
    capability: str
    benefit: str
    acceptance_criteria: list[str]
    trigger: str | None = None

    @property
    def text(self) -> str:
        return f"As {self.role}, I need {self.capability}, so that {self.benefit}."


@dataclass(slots=True)
class UseCase:
    ref: str
    name: str
    actor: str
    precondition: str
    main_flow: list[str]
    postcondition: str
    exceptions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TraceRow:
    """One row of the requirements traceability matrix.

    The columns are the chain the system actually maintains: a stakeholder
    statement, the requirement drawn from it, the clause that obliges it, the
    control it satisfies, and the acceptance criteria that verify it. A blank in
    any column is a real finding, which is why blanks are preserved rather than
    filtered out.
    """

    ref: str
    statement: str
    source_quote: str
    citations: list[str]
    controls: list[str]
    verification: list[str]
    approval_status: str
    confidence: float | None

    @property
    def gaps(self) -> list[str]:
        missing = []
        if not self.source_quote:
            missing.append("no source quotation")
        if not self.citations:
            missing.append("no citation")
        if not self.controls:
            missing.append("no control mapping")
        if not self.verification:
            missing.append("no acceptance criteria")
        return missing


@dataclass(slots=True)
class RiskEntry:
    ref: str
    description: str
    category: str
    level: str
    score: int
    treatment: str
    owner: str


@dataclass(slots=True)
class Artefacts:
    generated_at: datetime
    project: str
    user_stories: list[UserStory]
    use_cases: list[UseCase]
    traceability: list[TraceRow]
    risks: list[RiskEntry]
    open_issues: list[str]
    assumptions: list[str]

    @property
    def traceability_coverage(self) -> float:
        """Share of requirements whose chain is complete end to end.

        One of the brief's twelve evaluation metrics, and the only one that can
        be computed from the artefacts themselves.
        """
        if not self.traceability:
            return 0.0
        whole = sum(1 for row in self.traceability if not row.gaps)
        return whole / len(self.traceability)


def _beneficiary(categories: list[RequirementCategory]) -> str:
    for category, who in BENEFICIARY:
        if category in categories:
            return who
    return DEFAULT_BENEFICIARY


def _split(statement: str) -> tuple[str | None, str, str]:
    """Return (trigger, actor, behaviour) for an EARS-form statement."""
    trigger = None
    body = statement.strip()

    match = _TRIGGER.match(body)
    if match:
        trigger = match.group("trigger").strip()
        body = match.group("body").strip()

    actor_match = _ACTOR.match(body)
    if actor_match:
        return trigger, actor_match.group("actor").strip(), actor_match.group("behaviour").strip().rstrip(".")
    # Not in EARS form. Returned whole rather than guessed at - a user story
    # built from a mis-parsed statement is worse than one that reads stiffly.
    return trigger, "system", body.rstrip(".")


def _story(item, index: int) -> UserStory:
    trigger, _actor, behaviour = _split(item.requirement.statement)
    categories = list(item.requirement.categories)
    return UserStory(
        ref=f"US-{index:03d}",
        role=f"the {_beneficiary(categories)}",
        capability=f"the system to {behaviour}",
        benefit=(
            item.requirement.rationale.strip().rstrip(".")
            or "the obligation that requires it is met"
        ),
        acceptance_criteria=list(item.requirement.acceptance_criteria),
        trigger=trigger,
    )


def _use_case(item, index: int) -> UseCase:
    trigger, actor, behaviour = _split(item.requirement.statement)
    return UseCase(
        ref=f"UC-{index:03d}",
        name=behaviour[:80].rstrip(),
        actor=actor.title(),
        precondition=trigger or "The actor is authenticated and authorised",
        main_flow=[
            f"The {actor} initiates the operation.",
            f"The system performs: {behaviour}.",
            "The system records evidence of the operation for audit.",
        ],
        postcondition="The operation is complete and evidence is retained.",
        # Defects are the known ways this requirement can fail to be satisfied,
        # so they become the exception paths rather than being dropped.
        exceptions=[d.detail for d in item.defects][:4],
    )


def _risk(item, index: int) -> RiskEntry:
    level = item.requirement.risk_level
    categories = list(item.requirement.categories)
    category = categories[0].value if categories else "functional"
    treatment = (
        "Blocking: must be designed for and verified before release."
        if level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        else "Standard controls; verify through acceptance testing."
    )
    return RiskEntry(
        ref=f"RSK-{index:03d}",
        description=f"Failure to satisfy: {item.requirement.statement}",
        category=category,
        level=level.value,
        score=RISK_SCORE.get(level, 1),
        treatment=treatment,
        owner="Information security" if RequirementCategory.SECURITY in categories else "Product owner",
    )


def build(
    items: list,
    *,
    project: str = "Untitled project",
    unclear: list[str] | None = None,
    control_mappings: dict[str, list[str]] | None = None,
) -> Artefacts:
    """Derive the artefact set from an extraction result.

    `control_mappings` maps a requirement reference to the controls it
    satisfies, when a coverage assessment has been run. Absent, the traceability
    matrix reports the control column as empty - which is accurate, not a
    placeholder, and shows up in the coverage figure accordingly.
    """
    mappings = control_mappings or {}
    stories: list[UserStory] = []
    use_cases: list[UseCase] = []
    traceability: list[TraceRow] = []
    risks: list[RiskEntry] = []
    assumptions: list[str] = []

    for index, item in enumerate(items, start=1):
        ref = f"FR-{index:03d}"
        stories.append(_story(item, index))
        use_cases.append(_use_case(item, index))
        risks.append(_risk(item, index))
        assumptions.extend(item.requirement.assumptions)

        citations = [c for c in getattr(item, "citations", []) if c]
        traceability.append(
            TraceRow(
                ref=ref,
                statement=item.requirement.statement,
                source_quote=item.requirement.quoted_source,
                citations=citations,
                controls=mappings.get(ref, []),
                verification=list(item.requirement.acceptance_criteria),
                approval_status="draft",
                confidence=getattr(item, "confidence", None),
            )
        )

    return Artefacts(
        generated_at=datetime.now(UTC),
        project=project,
        user_stories=stories,
        use_cases=use_cases,
        traceability=traceability,
        risks=sorted(risks, key=lambda r: -r.score),
        open_issues=list(unclear or []),
        assumptions=sorted(set(assumptions)),
    )


__all__ = ["Artefacts", "RiskEntry", "TraceRow", "UseCase", "UserStory", "build"]
