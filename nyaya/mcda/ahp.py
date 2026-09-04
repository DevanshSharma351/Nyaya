"""Analytic Hierarchy Process: deriving criterion weights from pairwise judgements.

Weights for an SDLC decision cannot be asserted. "Regulatory criticality matters
more than delivery speed" is a defensible claim; "regulatory criticality has
weight 0.23" is not, unless something derives it.

AHP derives weights from pairwise comparisons, which humans make far more
reliably than direct weight assignment: an architect can say regulatory
criticality is *strongly* more important than team familiarity without being
able to say by how much on a 0-1 scale.

Crucially it also **measures whether the judgements were coherent**. If A > B and
B > C but C > A, the Consistency Ratio exposes it. A CR above 0.10 means the
weights are built on contradictory input and must not be used - a check that a
hand-assigned weight vector cannot offer, because it can never be inconsistent
and therefore never warns you.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Saaty's random consistency index: the mean CI of randomly generated reciprocal
# matrices of each order. CR is CI measured against this baseline, so consistency
# is judged relative to chance rather than in the abstract.
RANDOM_INDEX: dict[int, float] = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
    11: 1.51,
    12: 1.48,
    13: 1.56,
    14: 1.57,
    15: 1.59,
}

CONSISTENCY_LIMIT = 0.10


class InconsistentJudgementsError(ValueError):
    """Pairwise comparisons are too contradictory to derive weights from."""

    def __init__(self, ratio: float) -> None:
        super().__init__(
            f"Consistency Ratio {ratio:.3f} exceeds {CONSISTENCY_LIMIT}: the "
            f"pairwise judgements contradict one another, so the derived weights "
            f"would not represent any coherent preference. Revise the comparisons."
        )
        self.ratio = ratio


@dataclass(slots=True)
class AHPResult:
    criteria: list[str]
    weights: dict[str, float]
    consistency_ratio: float
    consistency_index: float
    principal_eigenvalue: float

    @property
    def consistent(self) -> bool:
        return self.consistency_ratio <= CONSISTENCY_LIMIT

    def ranked(self) -> list[tuple[str, float]]:
        return sorted(self.weights.items(), key=lambda kv: kv[1], reverse=True)


def build_matrix(criteria: list[str], comparisons: dict[tuple[str, str], float]) -> np.ndarray:
    """Build a reciprocal comparison matrix.

    `comparisons[(a, b)] = 5` means a is strongly more important than b, on
    Saaty's 1-9 scale. The reciprocal is filled automatically, which is what
    makes the matrix internally consistent by construction in the pairwise
    sense while still allowing transitive inconsistency - the thing CR detects.
    """
    index = {name: i for i, name in enumerate(criteria)}
    matrix = np.ones((len(criteria), len(criteria)), dtype=float)

    for (a, b), value in comparisons.items():
        if a not in index or b not in index:
            raise ValueError(f"Unknown criterion in comparison ({a!r}, {b!r})")
        if not 1 / 9 <= value <= 9:
            raise ValueError(f"Comparison {a}/{b}={value} outside Saaty's 1/9..9 scale")
        matrix[index[a], index[b]] = value
        matrix[index[b], index[a]] = 1.0 / value

    return matrix


def derive_weights(
    criteria: list[str],
    comparisons: dict[tuple[str, str], float],
    *,
    strict: bool = True,
) -> AHPResult:
    """Derive criterion weights via the principal eigenvector.

    The principal eigenvector is used rather than the row-geometric-mean
    approximation because the eigenvalue it yields is what the consistency
    measure is defined on; approximating the weights would leave CR unfounded.
    """
    matrix = build_matrix(criteria, comparisons)
    n = len(criteria)

    eigenvalues, eigenvectors = np.linalg.eig(matrix)
    principal = int(np.argmax(eigenvalues.real))
    vector = np.abs(eigenvectors[:, principal].real)
    weights = vector / vector.sum()

    lambda_max = float(eigenvalues[principal].real)
    consistency_index = (lambda_max - n) / (n - 1) if n > 1 else 0.0
    random_index = RANDOM_INDEX.get(n, 1.59)
    ratio = consistency_index / random_index if random_index else 0.0

    if strict and ratio > CONSISTENCY_LIMIT:
        raise InconsistentJudgementsError(ratio)

    return AHPResult(
        criteria=list(criteria),
        weights={name: float(w) for name, w in zip(criteria, weights, strict=True)},
        consistency_ratio=float(ratio),
        consistency_index=float(consistency_index),
        principal_eigenvalue=lambda_max,
    )


__all__ = [
    "CONSISTENCY_LIMIT",
    "RANDOM_INDEX",
    "AHPResult",
    "InconsistentJudgementsError",
    "build_matrix",
    "derive_weights",
]
