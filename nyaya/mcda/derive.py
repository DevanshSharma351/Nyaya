"""Deriving SDLC decision factors from an extracted requirement set.

The factor vector is the input to the whole lifecycle recommendation, and where
it comes from decides whether the recommendation means anything. Asked for
directly, it is a conclusion dressed as an input: whoever fills in the sliders
has already chosen the answer, and the arithmetic downstream only launders it.

Derived from the requirements the pipeline actually extracted, the
recommendation is traceable to evidence like every other output here - and the
derivation is auditable, which is why each factor below records the observation
it came from rather than being tuned until the answer looked right.

This lives outside the workflow module because two callers need it: the graph,
running the full pipeline, and the API, answering "given this project brief,
which lifecycle fits?" in one call. A second implementation of the same
reasoning would be a second thing to keep correct.
"""

from __future__ import annotations

from dataclasses import dataclass

from nyaya.core.enums import RiskLevel
from nyaya.mcda.sdlc import default_factors

ELEVATED = {RiskLevel.HIGH, RiskLevel.CRITICAL}

# Floors, not defaults. A brief that mentions no security requirement is not
# evidence that security does not matter - it is far more often evidence that
# nobody wrote it down. Letting a factor fall to zero on silence would let an
# incomplete brief argue for a lighter process, which is precisely backwards.
FLOORS = {
    "regulatory_criticality": 0.5,
    "security_risk": 0.4,
    "failure_consequence": 0.4,
    "formal_verification_need": 0.3,
}


@dataclass(slots=True)
class Derivation:
    """The factor vector, with the observations that produced it."""

    factors: dict[str, float]
    observations: list[str]


def factors_from_requirements(requirements: list, unclear: list[str]) -> dict[str, float]:
    """Factor vector only. Kept for callers that do not need the explanation."""
    return derive(requirements, unclear).factors


def derive(requirements: list, unclear: list[str]) -> Derivation:
    """Derive the factor vector and say, in words, where each number came from."""
    total = max(len(requirements), 1)

    regulatory = (
        sum(
            1
            for r in requirements
            if any(c.value == "regulatory" for c in r.requirement.categories)
        )
        / total
    )
    security = (
        sum(
            1
            for r in requirements
            if any(c.value == "security" for c in r.requirement.categories)
        )
        / total
    )
    elevated = (
        sum(1 for r in requirements if r.requirement.risk_level in ELEVATED) / total
    )
    # Open questions are the signal that the requirements are not yet settled.
    # Two per requirement is treated as fully unsettled; the ratio is what
    # matters, since a large brief naturally raises more questions.
    unsettled = min(len(unclear) / (total * 2), 1.0)

    factors = default_factors(
        regulatory_criticality=max(regulatory, FLOORS["regulatory_criticality"]),
        security_risk=max(security, FLOORS["security_risk"]),
        failure_consequence=max(elevated, FLOORS["failure_consequence"]),
        requirement_stability=1.0 - unsettled,
        change_frequency=unsettled,
        formal_verification_need=max(elevated, FLOORS["formal_verification_need"]),
    )

    count = len(requirements)
    observations = [
        f"{count} requirement{'s' if count != 1 else ''} extracted from the brief.",
        f"{regulatory:.0%} carry a regulatory category"
        + (
            f" — below the {FLOORS['regulatory_criticality']:.0%} floor, so the floor applies."
            if regulatory < FLOORS["regulatory_criticality"]
            else "."
        ),
        f"{security:.0%} carry a security category"
        + (
            f" — below the {FLOORS['security_risk']:.0%} floor, so the floor applies."
            if security < FLOORS["security_risk"]
            else "."
        ),
        f"{elevated:.0%} are high or critical risk, which sets failure consequence"
        " and the need for formal verification.",
        f"{len(unclear)} open question{'s' if len(unclear) != 1 else ''} were raised, "
        f"putting requirement stability at {1.0 - unsettled:.2f} and change "
        f"frequency at {unsettled:.2f}.",
    ]

    return Derivation(factors=factors, observations=observations)


__all__ = ["ELEVATED", "FLOORS", "Derivation", "derive", "factors_from_requirements"]
