"""TOPSIS: ranking SDLC candidates against the extracted project profile.

TOPSIS ranks alternatives by closeness to an ideal solution and distance from
the worst one. It suits this decision for two reasons:

1. **It produces a graded closeness coefficient, not a winner.** The brief asks
   for ranked recommendations - "Agile-DevSecOps hybrid 88 %, V-Model 76 %" -
   because a project rarely has one defensible lifecycle, and a single label
   hides how close the runner-up was. A margin of 0.02 and a margin of 0.30 mean
   very different things to an architect, and only a graded method shows that.

2. **It handles criteria that pull in opposite directions.** Regulatory
   criticality favours formal verification while change frequency favours
   iteration; TOPSIS does not require them to be commensurable, only scaled.

The arithmetic is deliberately visible rather than delegated to a library. A
recommendation an architect cannot re-derive is not one they can challenge, and
a recommendation nobody can challenge should not be acted on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class Alternative:
    """One candidate, scored on each criterion in [0,1]."""

    name: str
    scores: dict[str, float]


@dataclass(slots=True)
class Ranking:
    """One alternative's position in the result."""

    name: str
    closeness: float
    """Closeness coefficient in [0,1]; higher is better."""

    distance_to_best: float
    distance_to_worst: float
    contributions: dict[str, float] = field(default_factory=dict)
    """Weighted normalised score per criterion, so a ranking can be explained
    by which criteria drove it rather than merely stated."""

    @property
    def percentage(self) -> int:
        return round(self.closeness * 100)


@dataclass(slots=True)
class TOPSISResult:
    rankings: list[Ranking]
    criteria: list[str]
    weights: dict[str, float]

    @property
    def recommended(self) -> Ranking:
        return self.rankings[0]

    @property
    def margin(self) -> float:
        """Gap between the top two. A narrow margin means the decision is close
        and the choice should be made by a human on grounds the model cannot see."""
        return (
            self.rankings[0].closeness - self.rankings[1].closeness
            if len(self.rankings) > 1
            else 1.0
        )

    def explain(self, top: int = 3) -> list[str]:
        lines = []
        for rank in self.rankings[:top]:
            drivers = sorted(rank.contributions.items(), key=lambda kv: kv[1], reverse=True)[:3]
            drivers_text = ", ".join(f"{name} ({value:.3f})" for name, value in drivers)
            lines.append(f"{rank.name}: {rank.percentage}% - driven by {drivers_text}")
        return lines


def rank(
    alternatives: list[Alternative],
    weights: dict[str, float],
    *,
    benefit: dict[str, bool] | None = None,
) -> TOPSISResult:
    """Rank `alternatives` by TOPSIS closeness.

    `benefit` marks each criterion as one to maximise (True) or minimise
    (False); it defaults to maximising. Cost criteria are inverted during
    normalisation rather than negated, so distances stay well-defined.
    """
    if not alternatives:
        raise ValueError("no alternatives to rank")

    criteria = list(weights.keys())
    benefit = benefit or {}

    matrix = np.array(
        [[alt.scores.get(c, 0.0) for c in criteria] for alt in alternatives],
        dtype=float,
    )

    # Vector normalisation: each column divided by its Euclidean norm, which
    # preserves the *ratio* between alternatives rather than merely rescaling to
    # a range - a min-max scaling would make the worst alternative zero on every
    # criterion regardless of how good it actually was.
    norms = np.linalg.norm(matrix, axis=0)
    norms[norms == 0] = 1.0
    normalised = matrix / norms

    weight_vector = np.array([weights[c] for c in criteria], dtype=float)
    weighted = normalised * weight_vector

    ideal_best = np.empty(len(criteria))
    ideal_worst = np.empty(len(criteria))
    for i, criterion in enumerate(criteria):
        column = weighted[:, i]
        if benefit.get(criterion, True):
            ideal_best[i], ideal_worst[i] = column.max(), column.min()
        else:
            ideal_best[i], ideal_worst[i] = column.min(), column.max()

    to_best = np.linalg.norm(weighted - ideal_best, axis=1)
    to_worst = np.linalg.norm(weighted - ideal_worst, axis=1)

    denominator = to_best + to_worst
    # All alternatives identical: closeness is undefined, so report a tie rather
    # than dividing by zero.
    closeness = np.divide(
        to_worst, denominator, out=np.full_like(to_worst, 0.5), where=denominator != 0
    )

    rankings = [
        Ranking(
            name=alt.name,
            closeness=float(closeness[i]),
            distance_to_best=float(to_best[i]),
            distance_to_worst=float(to_worst[i]),
            contributions={c: float(weighted[i, j]) for j, c in enumerate(criteria)},
        )
        for i, alt in enumerate(alternatives)
    ]
    rankings.sort(key=lambda r: r.closeness, reverse=True)

    return TOPSISResult(rankings=rankings, criteria=criteria, weights=dict(weights))


__all__ = ["Alternative", "Ranking", "TOPSISResult", "rank"]
