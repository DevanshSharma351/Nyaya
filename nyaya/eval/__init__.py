"""Evaluation harness.

Retrieval is benchmarked before any agent depends on it, because every
downstream metric - citation correctness, control coverage, hallucination rate -
is bounded above by whether the governing clause was retrieved at all.
"""

from nyaya.eval.metrics import (
    hit_at_k,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from nyaya.eval.retrieval_gold import ALL_QUERIES, GOLD, TERM_QUERIES, GoldQuery

__all__ = [
    "ALL_QUERIES",
    "GOLD",
    "TERM_QUERIES",
    "GoldQuery",
    "hit_at_k",
    "mean",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
]
