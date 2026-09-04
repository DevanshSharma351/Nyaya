"""Retrieval: embedding, hybrid search, reranking, entailment."""

from nyaya.retrieval.embedder import embed_query, embed_texts
from nyaya.retrieval.hybrid import (
    DEFAULT_FUSION_WEIGHTS,
    RetrievalResult,
    Retrieved,
    dense_search,
    hybrid_search,
    lexical_search,
    reciprocal_rank_fusion,
    resolve_citation,
)
from nyaya.retrieval.rerank import rerank
from nyaya.retrieval.search import SearchOptions, search

__all__ = [
    "DEFAULT_FUSION_WEIGHTS",
    "RetrievalResult",
    "Retrieved",
    "SearchOptions",
    "dense_search",
    "embed_query",
    "embed_texts",
    "hybrid_search",
    "lexical_search",
    "reciprocal_rank_fusion",
    "rerank",
    "resolve_citation",
    "search",
]
