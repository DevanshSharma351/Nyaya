"""Ranking metrics.

Implemented directly rather than pulled from a library so the definitions are
visible and auditable - a reported number whose definition is buried in a
dependency is not a number anyone can defend in a viva or a paper.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant items appearing in the top `k`."""
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def precision_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / k


def reciprocal_rank(retrieved: Sequence[str], target: str) -> float:
    """1/rank of `target`, or 0 if absent.

    Reported against the *primary* clause rather than any relevant one: the
    question that matters is whether the single clause most directly stating the
    obligation surfaces first, since that is the one a citation should name.
    """
    for rank, key in enumerate(retrieved, start=1):
        if key == target:
            return 1.0 / rank
    return 0.0


def hit_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """1.0 if any relevant item is in the top `k`."""
    return 1.0 if set(retrieved[:k]) & relevant else 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Normalised discounted cumulative gain with binary relevance."""
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, key in enumerate(retrieved[:k], start=1)
        if key in relevant
    )
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else 0.0


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


__all__ = [
    "hit_at_k",
    "mean",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
]
