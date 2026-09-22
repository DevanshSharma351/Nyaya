"""The SDLC selection engine.

Ranks lifecycle models against a project's extracted characteristics using
AHP-derived weights and TOPSIS.

**The mathematics decides; the model only explains.** That division is the
point. An LLM asked directly to pick a lifecycle produces a plausible paragraph
that cannot be re-derived, challenged on its inputs, or compared against another
project. Here the inputs (factor scores), the weights (with their consistency
ratio) and the arithmetic are all inspectable, so an architect who disagrees can
point at the specific factor score they dispute rather than arguing with prose.

Candidate profiles below encode how well each lifecycle serves each factor.
They are drawn from the established characteristics of the models - Waterfall
suits stable requirements and heavy approval gates, Spiral suits high technical
uncertainty, DevSecOps suits continuous secure delivery - and are the part of
this engine most in need of validation against practitioner judgement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nyaya.core.enums import SDLCModel
from nyaya.mcda.ahp import AHPResult, derive_weights
from nyaya.mcda.topsis import Alternative, TOPSISResult, rank

# Criteria on which a lifecycle model's profile value should MATCH the
# project's need rather than exceed it.
#
# Process ceremony has a cost. A model demanding heavy documentation and formal
# verification is a poor fit for a low-risk internal tool - not a neutral one -
# because the ceremony is paid for whether or not it is needed. Treating every
# criterion as "more is better" made a DevSecOps hybrid outrank plain Agile on
# an exploratory low-risk dashboard, which is the wrong answer: Agile's
# advantage there is precisely its lightness.
#
# Capability criteria (security, complexity handling) remain benefit-type: a
# model that copes well with complexity is not penalised on a simple project,
# it merely earns less weight there.
MATCH_CRITERIA: frozenset[str] = frozenset(
    {
        "documentation_need",
        "formal_verification_need",
        "requirement_stability",
        "change_frequency",
        "continuous_delivery_need",
    }
)

# Keeps a criterion from vanishing entirely when a project scores it near zero,
# so the ranking still reflects a model's unsuitability rather than ignoring it.
SALIENCE_FLOOR = 0.2

# The decision factors the brief enumerates, scored in [0,1].
FACTORS: tuple[str, ...] = (
    "requirement_stability",
    "regulatory_criticality",
    "security_risk",
    "project_complexity",
    "legacy_dependence",
    "change_frequency",
    "continuous_delivery_need",
    "stakeholder_availability",
    "documentation_need",
    "formal_verification_need",
    "failure_consequence",
    "schedule_pressure",
    "team_experience",
)

# How well each lifecycle serves a project exhibiting each factor strongly.
# A high value means "this model copes well when this factor is high".
PROFILES: dict[SDLCModel, dict[str, float]] = {
    SDLCModel.WATERFALL: {
        "requirement_stability": 0.95,
        "regulatory_criticality": 0.70,
        "security_risk": 0.40,
        "project_complexity": 0.35,
        "legacy_dependence": 0.60,
        "change_frequency": 0.10,
        "continuous_delivery_need": 0.10,
        "stakeholder_availability": 0.30,
        "documentation_need": 0.95,
        "formal_verification_need": 0.60,
        "failure_consequence": 0.60,
        "schedule_pressure": 0.40,
        "team_experience": 0.50,
    },
    SDLCModel.V_MODEL: {
        "requirement_stability": 0.90,
        "regulatory_criticality": 0.90,
        "security_risk": 0.75,
        "project_complexity": 0.50,
        "legacy_dependence": 0.60,
        "change_frequency": 0.15,
        "continuous_delivery_need": 0.15,
        "stakeholder_availability": 0.35,
        "documentation_need": 0.90,
        "formal_verification_need": 0.95,
        "failure_consequence": 0.95,
        "schedule_pressure": 0.35,
        "team_experience": 0.55,
    },
    SDLCModel.SPIRAL: {
        "requirement_stability": 0.40,
        "regulatory_criticality": 0.60,
        "security_risk": 0.75,
        "project_complexity": 0.90,
        "legacy_dependence": 0.75,
        "change_frequency": 0.60,
        "continuous_delivery_need": 0.35,
        "stakeholder_availability": 0.60,
        "documentation_need": 0.65,
        "formal_verification_need": 0.60,
        "failure_consequence": 0.80,
        "schedule_pressure": 0.30,
        "team_experience": 0.75,
    },
    SDLCModel.AGILE: {
        "requirement_stability": 0.20,
        "regulatory_criticality": 0.30,
        "security_risk": 0.40,
        "project_complexity": 0.55,
        "legacy_dependence": 0.35,
        "change_frequency": 0.95,
        "continuous_delivery_need": 0.80,
        "stakeholder_availability": 0.90,
        "documentation_need": 0.30,
        "formal_verification_need": 0.20,
        "failure_consequence": 0.35,
        "schedule_pressure": 0.80,
        "team_experience": 0.70,
    },
    SDLCModel.DEVSECOPS: {
        "requirement_stability": 0.35,
        "regulatory_criticality": 0.70,
        "security_risk": 0.95,
        "project_complexity": 0.70,
        "legacy_dependence": 0.40,
        "change_frequency": 0.90,
        "continuous_delivery_need": 0.95,
        "stakeholder_availability": 0.70,
        "documentation_need": 0.55,
        "formal_verification_need": 0.45,
        "failure_consequence": 0.70,
        "schedule_pressure": 0.80,
        "team_experience": 0.80,
    },
    # --- added because "such as" is an example list, not a closed one -------
    #
    # Each of these is a distinct answer to "how should this be built", with a
    # profile that differs from its neighbours on factors that matter. Where two
    # would have been near-identical, only one is here.
    SDLCModel.INCREMENTAL: {
        # Deliver in planned slices against a stable overall scope. The usual
        # shape of a core-banking migration: the destination is known, the route
        # is staged, and each stage must be provably complete.
        "requirement_stability": 0.80,
        "regulatory_criticality": 0.70,
        "security_risk": 0.60,
        "project_complexity": 0.70,
        "legacy_dependence": 0.80,
        "change_frequency": 0.35,
        "continuous_delivery_need": 0.45,
        "stakeholder_availability": 0.50,
        "documentation_need": 0.70,
        "formal_verification_need": 0.55,
        "failure_consequence": 0.70,
        "schedule_pressure": 0.55,
        "team_experience": 0.55,
    },
    SDLCModel.ITERATIVE: {
        # Refine the same system repeatedly rather than extend it in slices.
        # Fits work where the requirement is understood but the right solution
        # is not - a fraud model, a risk-scoring engine.
        "requirement_stability": 0.45,
        "regulatory_criticality": 0.55,
        "security_risk": 0.55,
        "project_complexity": 0.75,
        "legacy_dependence": 0.50,
        "change_frequency": 0.65,
        "continuous_delivery_need": 0.45,
        "stakeholder_availability": 0.60,
        "documentation_need": 0.50,
        "formal_verification_need": 0.45,
        "failure_consequence": 0.55,
        "schedule_pressure": 0.45,
        "team_experience": 0.55,
    },
    SDLCModel.PROTOTYPING: {
        # Build to learn what is wanted. Only defensible where failure is cheap:
        # a prototype-led approach to a payments switch would be negligent, and
        # the low failure-consequence and regulatory scores say so.
        "requirement_stability": 0.15,
        "regulatory_criticality": 0.30,
        "security_risk": 0.30,
        "project_complexity": 0.45,
        "legacy_dependence": 0.30,
        "change_frequency": 0.85,
        "continuous_delivery_need": 0.40,
        "stakeholder_availability": 0.90,
        "documentation_need": 0.25,
        "formal_verification_need": 0.15,
        "failure_consequence": 0.20,
        "schedule_pressure": 0.60,
        "team_experience": 0.45,
    },
    SDLCModel.RAD: {
        # Small expert team, heavy stakeholder involvement, short calendar.
        # Distinguished from prototyping by producing a real system, and from
        # agile by depending on component reuse and an experienced team.
        "requirement_stability": 0.35,
        "regulatory_criticality": 0.35,
        "security_risk": 0.35,
        "project_complexity": 0.35,
        "legacy_dependence": 0.35,
        "change_frequency": 0.75,
        "continuous_delivery_need": 0.55,
        "stakeholder_availability": 0.95,
        "documentation_need": 0.25,
        "formal_verification_need": 0.20,
        "failure_consequence": 0.30,
        "schedule_pressure": 0.90,
        "team_experience": 0.80,
    },
    SDLCModel.SCALED_AGILE: {
        # Agile across many teams with a coordinating cadence. The distinguishing
        # factors are complexity and size rather than anything about the
        # engineering: a single team does not need this and pays for it.
        "requirement_stability": 0.45,
        "regulatory_criticality": 0.75,
        "security_risk": 0.70,
        "project_complexity": 0.95,
        "legacy_dependence": 0.70,
        "change_frequency": 0.70,
        "continuous_delivery_need": 0.70,
        "stakeholder_availability": 0.60,
        "documentation_need": 0.65,
        "formal_verification_need": 0.50,
        "failure_consequence": 0.75,
        "schedule_pressure": 0.55,
        "team_experience": 0.65,
    },
    SDLCModel.KANBAN: {
        # Continuous flow with work-in-progress limits and no fixed iteration.
        # The right answer for run-and-maintain and for regulatory-reporting
        # teams, whose work arrives rather than being planned - which is why
        # requirement stability is low but change frequency is not extreme.
        "requirement_stability": 0.40,
        "regulatory_criticality": 0.60,
        "security_risk": 0.55,
        "project_complexity": 0.40,
        "legacy_dependence": 0.65,
        "change_frequency": 0.80,
        "continuous_delivery_need": 0.85,
        "stakeholder_availability": 0.55,
        "documentation_need": 0.40,
        "formal_verification_need": 0.30,
        "failure_consequence": 0.50,
        "schedule_pressure": 0.50,
        "team_experience": 0.60,
    },
    SDLCModel.AGILE_VMODEL_HYBRID: {
        "requirement_stability": 0.55,
        "regulatory_criticality": 0.90,
        "security_risk": 0.75,
        "project_complexity": 0.65,
        "legacy_dependence": 0.65,
        "change_frequency": 0.65,
        "continuous_delivery_need": 0.45,
        "stakeholder_availability": 0.65,
        "documentation_need": 0.85,
        "formal_verification_need": 0.85,
        "failure_consequence": 0.90,
        "schedule_pressure": 0.55,
        "team_experience": 0.65,
    },
    SDLCModel.AGILE_DEVSECOPS_HYBRID: {
        "requirement_stability": 0.45,
        "regulatory_criticality": 0.85,
        "security_risk": 0.90,
        "project_complexity": 0.75,
        "legacy_dependence": 0.50,
        "change_frequency": 0.90,
        "continuous_delivery_need": 0.85,
        "stakeholder_availability": 0.75,
        "documentation_need": 0.70,
        "formal_verification_need": 0.60,
        "failure_consequence": 0.85,
        "schedule_pressure": 0.75,
        "team_experience": 0.75,
    },
}

# Default pairwise comparisons for a regulated financial project, on Saaty's
# 1-9 scale. These encode a defensible position - in banking, regulatory and
# security considerations dominate delivery speed - and are the input an
# organisation should replace with its own practitioners' judgements.
DEFAULT_COMPARISONS: dict[tuple[str, str], float] = {
    ("regulatory_criticality", "requirement_stability"): 3,
    ("regulatory_criticality", "change_frequency"): 2,
    ("regulatory_criticality", "schedule_pressure"): 5,
    ("security_risk", "requirement_stability"): 3,
    ("security_risk", "change_frequency"): 2,
    ("security_risk", "schedule_pressure"): 5,
    ("failure_consequence", "schedule_pressure"): 4,
    ("failure_consequence", "requirement_stability"): 2,
    ("change_frequency", "schedule_pressure"): 2,
    ("requirement_stability", "schedule_pressure"): 2,
}


@dataclass(slots=True)
class SDLCRecommendation:
    ranking: TOPSISResult
    weights: AHPResult
    factors: dict[str, float]
    close_call: bool = False
    """True when the top two are within `CLOSE_MARGIN`. The engine should not
    present a near-tie as a decision; that choice belongs to a human weighing
    considerations the factor vector does not capture."""

    notes: list[str] = field(default_factory=list)

    @property
    def recommended(self) -> SDLCModel:
        return SDLCModel(self.ranking.recommended.name)

    def ranked(self) -> list[tuple[str, int]]:
        return [(r.name, r.percentage) for r in self.ranking.rankings]


CLOSE_MARGIN = 0.05


def recommend(
    factors: dict[str, float],
    *,
    comparisons: dict[tuple[str, str], float] | None = None,
    candidates: list[SDLCModel] | None = None,
) -> SDLCRecommendation:
    """Rank lifecycle models against a project's factor profile.

    `factors` weights how much each criterion matters *for this project*: a
    project with stable requirements should not be penalised on a
    change-frequency criterion that does not apply to it. Factors are combined
    with the AHP weights so both the general priority and the project's own
    profile shape the result.
    """
    missing = set(FACTORS) - set(factors)
    if missing:
        raise ValueError(f"missing factor scores: {sorted(missing)}")

    weights = derive_weights(list(FACTORS), comparisons or DEFAULT_COMPARISONS, strict=False)

    notes: list[str] = []
    if not weights.consistent:
        notes.append(
            f"pairwise judgements are inconsistent (CR={weights.consistency_ratio:.3f} "
            f"> 0.10); the weighting should be revised before this ranking is relied on"
        )

    # Benefit criteria are scaled by how strongly the project exhibits them: a
    # capability that is important in general but irrelevant here recedes.
    #
    # Match criteria are NOT scaled, and this is the subtle part. Their score
    # already measures *mismatch*, which matters just as much when the need is
    # low as when it is high - a project needing light process cares about not
    # being burdened exactly as much as a regulated one cares about rigour.
    # Scaling them by the factor discounted the very criterion that should have
    # penalised excess ceremony, which is why a DevSecOps hybrid was outranking
    # plain Agile on an exploratory low-risk tool.
    effective = {
        name: (
            weights.weights[name]
            if name in MATCH_CRITERIA
            else weights.weights[name] * max(factors[name], SALIENCE_FLOOR)
        )
        for name in FACTORS
    }
    total = sum(effective.values())
    if total <= 0:
        raise ValueError("all factor scores are zero; nothing to rank on")
    effective = {name: value / total for name, value in effective.items()}

    models = candidates or list(PROFILES)
    alternatives = [
        Alternative(name=model.value, scores=_fit(PROFILES[model], factors)) for model in models
    ]
    ranking = rank(alternatives, effective)

    close = ranking.margin < CLOSE_MARGIN
    if close:
        notes.append(
            f"the top two candidates are within {ranking.margin:.3f}; this is a "
            f"close call and the choice should be made by the project's "
            f"architects and compliance officers, not by the ranking alone"
        )

    return SDLCRecommendation(
        ranking=ranking,
        weights=weights,
        factors=dict(factors),
        close_call=close,
        notes=notes,
    )


def _fit(profile: dict[str, float], factors: dict[str, float]) -> dict[str, float]:
    """How well one lifecycle serves this project, per criterion.

    Match-type criteria score on proximity, so a model demanding more ceremony
    than the project needs is penalised exactly as one demanding too little.
    Benefit-type criteria score on capability, which the weighting then scales
    by how much the project actually needs it.
    """
    return {
        name: (
            1.0 - abs(profile[name] - factors[name]) if name in MATCH_CRITERIA else profile[name]
        )
        for name in FACTORS
    }


def default_factors(**overrides: float) -> dict[str, float]:
    """A neutral factor profile, for tests and as a starting point."""
    profile = dict.fromkeys(FACTORS, 0.5)
    profile.update(overrides)
    return profile


__all__ = [
    "CLOSE_MARGIN",
    "DEFAULT_COMPARISONS",
    "FACTORS",
    "MATCH_CRITERIA",
    "PROFILES",
    "SALIENCE_FLOOR",
    "SDLCRecommendation",
    "default_factors",
    "recommend",
]
