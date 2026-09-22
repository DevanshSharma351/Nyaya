"""Turning a chosen lifecycle model into a project-specific workflow.

Section 15 of the brief asks for the half of "SDLC identification" that a label
alone does not deliver: phases, the activities inside them, responsible roles,
deliverables, security activities, testing requirements, compliance
checkpoints, human-approval gates, entry and exit criteria, and traceability
requirements. Naming a lifecycle without any of that tells a team what to call
their process, not how to run it.

Three principles decide what is generated.

**Deterministic, not written by a model.** Each lifecycle has a skeleton of
phases, and each phase has activities that belong to it by definition. A model
asked to invent a V-Model will produce something plausible and subtly wrong, and
nobody reviewing it would be able to say which parts were real. The skeletons
here are fixed; the model's only job elsewhere is explaining the choice.

**Customised by the project's own findings, not by its factor sliders.**
Activities are added because of what the analysis found - a blocking compliance
gap adds a remediation activity, a critical-risk requirement adds threat
modelling to design - so every non-skeleton line in the output can be traced to
a specific finding. An activity that appears for no stated reason is one nobody
can challenge.

**Gates are the same six the workflow engine already enforces.** The generated
workflow does not invent approval points: it names the gates that exist in
`nyaya.graph.gates`, so what a reader is shown is what the system will actually
stop at. A plan that promises checkpoints the machinery does not implement is
worse than no plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nyaya.core.enums import SDLCModel

# --- roles, named once so a deliverable and its owner cannot drift apart -----
BA = "Business analyst"
ARCHITECT = "Software architect"
DEV = "Development team"
SECURITY = "Information security"
COMPLIANCE = "Compliance officer"
QA = "Test engineering"
PM = "Project manager"
OPS = "Operations"
AUDIT = "Internal audit"


@dataclass(slots=True)
class Activity:
    """One unit of work inside a phase."""

    name: str
    role: str
    #: Present when the activity was added by a finding rather than the
    #: skeleton. The reason is shown to the reader, so nothing appears
    #: unexplained.
    because: str | None = None
    security: bool = False
    compliance: bool = False


@dataclass(slots=True)
class Phase:
    """A phase of the generated workflow."""

    name: str
    purpose: str
    entry_criteria: list[str]
    exit_criteria: list[str]
    activities: list[Activity] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    #: Gate key from `nyaya.graph.gates`, where one applies.
    gate: str | None = None

    @property
    def roles(self) -> list[str]:
        """Every role with work in this phase, in first-appearance order."""
        seen: list[str] = []
        for activity in self.activities:
            if activity.role not in seen:
                seen.append(activity.role)
        return seen


@dataclass(slots=True)
class Workflow:
    """A lifecycle, customised for one project."""

    model: SDLCModel
    cadence: str
    phases: list[Phase]
    traceability: list[str]
    notes: list[str] = field(default_factory=list)

    @property
    def gates(self) -> list[str]:
        return [p.gate for p in self.phases if p.gate]


# --- the skeletons -----------------------------------------------------------
#
# Iterative and sequential lifecycles differ in cadence and in where
# verification sits, not in which activities exist at all: every financial
# project does requirements, design, build, verification and release. So the
# phases are shared and the differences are stated explicitly.

def _phases(*, iterative: bool) -> list[Phase]:
    unit = "iteration" if iterative else "phase"
    return [
        Phase(
            name="Requirements and compliance analysis",
            purpose=(
                "Establish an approved requirement baseline in which every "
                "obligation cites the clause that creates it."
            ),
            entry_criteria=[
                "Stakeholders identified with their roles recorded",
                "Regulatory corpus loaded for the applicable jurisdictions",
            ],
            exit_criteria=[
                "Every requirement is testable and carries an approved citation",
                "Open questions are answered or explicitly accepted as open",
            ],
            activities=[
                Activity("Elicit requirements from stakeholders", BA),
                Activity("Rewrite into testable form and split compounds", BA),
                Activity("Resolve open questions with the originating stakeholder", BA),
                Activity(
                    "Map each requirement to its governing clause", COMPLIANCE,
                    compliance=True,
                ),
                Activity("Classify data sensitivity and retention duties", SECURITY, security=True),
            ],
            deliverables=[
                "Software Requirements Specification",
                "Requirements traceability matrix",
                "Open-issues list",
            ],
            gate="requirement_baseline",
        ),
        Phase(
            name="Architecture and security design",
            purpose="Decide the structure, and decide it against the obligations.",
            entry_criteria=["Requirement baseline approved"],
            exit_criteria=[
                "Every blocking control has a named design response",
                "Interfaces to legacy systems are specified",
            ],
            activities=[
                Activity("Produce the solution architecture", ARCHITECT),
                Activity("Specify interfaces and data contracts", ARCHITECT),
                Activity("Define audit-log and evidence retention design", ARCHITECT, compliance=True),
                Activity("Review the design against the control pack", COMPLIANCE, compliance=True),
            ],
            deliverables=["Architecture description", "Interface specifications"],
            gate="regulatory_interpretation",
        ),
        Phase(
            name="Implementation",
            purpose="Build, with verification attached to the work rather than deferred.",
            entry_criteria=["Design approved", "Environments provisioned"],
            exit_criteria=[
                "All code reviewed",
                "No unresolved high-severity security finding",
            ],
            activities=[
                Activity(f"Implement the scoped requirements for the {unit}", DEV),
                Activity("Peer review with the originating requirement linked", DEV),
                Activity("Static application security testing", SECURITY, security=True),
                Activity("Dependency and licence scanning", SECURITY, security=True),
            ],
            deliverables=["Reviewed source", "Security scan reports"],
        ),
        Phase(
            name="Verification",
            purpose="Show that each requirement is met, by the test that covers it.",
            entry_criteria=["Implementation complete for the scoped requirements"],
            exit_criteria=[
                "Every requirement has a passing test linked to it",
                "Coverage gaps are recorded as accepted risk or closed",
            ],
            activities=[
                Activity("Execute acceptance tests derived from the criteria", QA),
                Activity("Trace test results back to requirement identifiers", QA),
                Activity("Transaction-integrity and reconciliation testing", QA),
                Activity("Confirm evidence is produced as designed", AUDIT, compliance=True),
            ],
            deliverables=["Test report with requirement coverage", "Evidence samples"],
            gate="compliance_gap",
        ),
        Phase(
            name="Release and operation",
            purpose="Put it in front of customers, and keep the obligations true afterwards.",
            entry_criteria=["Verification complete", "Compliance approval recorded"],
            exit_criteria=[
                "Production monitoring and alerting live",
                "Regulatory-change watch registered for every cited source",
            ],
            activities=[
                Activity("Deploy through the change-management process", OPS),
                Activity("Confirm production monitoring and audit logging", OPS, security=True),
                Activity("Register cited clauses for amendment monitoring", COMPLIANCE, compliance=True),
                Activity("Record the production-readiness decision", PM),
            ],
            deliverables=["Release record", "Operational runbook"],
            gate="production_readiness",
        ),
    ]


CADENCE: dict[SDLCModel, str] = {
    SDLCModel.WATERFALL: "One pass. Each phase completes before the next begins.",
    SDLCModel.V_MODEL: (
        "One pass, with each verification level planned against the "
        "specification level that defines it."
    ),
    SDLCModel.SPIRAL: (
        "Repeated cycles, each opening with an explicit risk assessment that "
        "decides the scope of the cycle."
    ),
    SDLCModel.AGILE: "Fixed-length iterations, each ending in working software.",
    SDLCModel.DEVSECOPS: (
        "Continuous flow, with security and compliance checks inside the "
        "pipeline rather than after it."
    ),
    SDLCModel.AGILE_VMODEL_HYBRID: (
        "Agile iterations for build, with V-Model verification planning held "
        "against a controlled baseline - the usual answer when delivery must be "
        "quick but evidence must be formal."
    ),
    SDLCModel.AGILE_DEVSECOPS_HYBRID: (
        "Agile iterations on a continuously verified pipeline, with compliance "
        "gates automated where they can be and manual where they cannot."
    ),
}

ITERATIVE = {
    SDLCModel.SPIRAL,
    SDLCModel.AGILE,
    SDLCModel.DEVSECOPS,
    SDLCModel.AGILE_VMODEL_HYBRID,
    SDLCModel.AGILE_DEVSECOPS_HYBRID,
}

# Activities a specific lifecycle adds because the lifecycle itself requires
# them, as distinct from those a project's findings add.
MODEL_ACTIVITIES: dict[SDLCModel, list[tuple[str, Activity]]] = {
    SDLCModel.V_MODEL: [
        ("Verification", Activity("Plan each test level against its specification level", QA)),
    ],
    SDLCModel.SPIRAL: [
        (
            "Requirements and compliance analysis",
            Activity("Assess and rank risks to open the cycle", PM),
        ),
        ("Architecture and security design", Activity("Prototype the highest-risk element", DEV)),
    ],
    SDLCModel.DEVSECOPS: [
        ("Implementation", Activity("Automate the control checks into the pipeline", OPS, security=True)),
        ("Release and operation", Activity("Continuous compliance monitoring", COMPLIANCE, compliance=True)),
    ],
    SDLCModel.AGILE_DEVSECOPS_HYBRID: [
        ("Implementation", Activity("Automate the control checks into the pipeline", OPS, security=True)),
        ("Release and operation", Activity("Continuous compliance monitoring", COMPLIANCE, compliance=True)),
    ],
    SDLCModel.AGILE_VMODEL_HYBRID: [
        ("Verification", Activity("Plan each test level against its specification level", QA)),
    ],
    SDLCModel.AGILE: [
        ("Verification", Activity("Demonstrate the increment to stakeholders", BA)),
    ],
    SDLCModel.WATERFALL: [
        ("Requirements and compliance analysis", Activity("Freeze and formally sign off the baseline", PM)),
    ],
}

TRACEABILITY = [
    "Every requirement carries the citation that creates it, and the citation "
    "resolves to a clause in a version of a source that was in force.",
    "Every test names the requirement it verifies.",
    "Every approval records who gave it, when, and in what role.",
    "Every amendment to a cited source raises the requirements that depended on it.",
]


def generate(
    model: SDLCModel,
    *,
    blocking_gaps: int = 0,
    critical_requirements: int = 0,
    open_questions: int = 0,
    legacy_integration: bool = False,
) -> Workflow:
    """Build the workflow for `model`, customised by what the analysis found.

    Every argument is an observation, not a preference. They come from the
    coverage report, the extracted requirements and the open-questions list, so
    each added activity can name the finding that put it there.
    """
    phases = _phases(iterative=model in ITERATIVE)
    by_name = {phase.name: phase for phase in phases}

    for phase_name, activity in MODEL_ACTIVITIES.get(model, []):
        by_name[phase_name].activities.append(activity)

    notes: list[str] = []

    if blocking_gaps:
        by_name["Requirements and compliance analysis"].activities.append(
            Activity(
                f"Close {blocking_gaps} blocking control gap"
                f"{'s' if blocking_gaps != 1 else ''} before the baseline is approved",
                COMPLIANCE,
                because=f"coverage assessment found {blocking_gaps} blocking gaps",
                compliance=True,
            )
        )
        by_name["Requirements and compliance analysis"].exit_criteria.append(
            "No blocking control gap remains open"
        )
        notes.append(
            f"{blocking_gaps} blocking control gaps must close before the baseline "
            "is approved; they are not deferrable to a later iteration."
        )

    if critical_requirements:
        by_name["Architecture and security design"].activities.append(
            Activity(
                "Threat-model the components carrying critical requirements",
                SECURITY,
                because=f"{critical_requirements} requirements are critical risk",
                security=True,
            )
        )
        by_name["Verification"].activities.append(
            Activity(
                "Penetration test the critical paths",
                SECURITY,
                because=f"{critical_requirements} requirements are critical risk",
                security=True,
            )
        )

    if open_questions:
        by_name["Requirements and compliance analysis"].activities.append(
            Activity(
                f"Resolve {open_questions} open question"
                f"{'s' if open_questions != 1 else ''} with the originating stakeholder",
                BA,
                because="the extraction raised questions it refused to answer itself",
            )
        )
        notes.append(
            f"{open_questions} questions are unanswered. Each one is a value the "
            "system declined to invent, so the baseline is provisional until they "
            "are settled."
        )

    if legacy_integration:
        by_name["Architecture and security design"].activities.append(
            Activity(
                "Specify and test the legacy-system contract",
                ARCHITECT,
                because="the project depends on existing systems",
            )
        )
        by_name["Verification"].activities.append(
            Activity(
                "End-to-end testing against the legacy interfaces",
                QA,
                because="the project depends on existing systems",
            )
        )

    return Workflow(
        model=model,
        cadence=CADENCE[model],
        phases=phases,
        traceability=TRACEABILITY,
        notes=notes,
    )


__all__ = ["Activity", "Phase", "Workflow", "generate"]
