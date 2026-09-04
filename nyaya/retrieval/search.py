"""The retrieval entry point agents use.

Implements the configuration that measured best on the labelled eKYC set:
**dense retrieval, then cross-encoder reranking.** See ADR-0004 for the numbers
and for why lexical fusion is off by default.

Agents call `search`; they do not choose a retrieval strategy. Changing that
strategy is then a single edit here plus a re-run of `nyaya.eval`, rather than a
change scattered across every agent that needs evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.config import get_settings
from nyaya.retrieval.embedder import embed_query
from nyaya.retrieval.hybrid import (
    DEFAULT_FUSION_WEIGHTS,
    RetrievalResult,
    Retrieved,
    dense_search,
    lexical_search,
    reciprocal_rank_fusion,
)
from nyaya.retrieval.rerank import available as reranker_available
from nyaya.retrieval.rerank import rerank


@dataclass(slots=True)
class SearchOptions:
    """Retrieval configuration.

    Defaults encode the measured-best path. The alternatives remain reachable so
    the eval harness can run ablations without a separate code path - the arm
    under test must be the code that actually ships.
    """

    top_k: int = 8
    """Evidence window handed to an agent. Deliberately small: a compliance
    prompt containing thirty clauses invites the model to cite a plausible
    neighbour rather than the governing one."""

    candidates: int = 30
    """Shortlist depth passed to the reranker. Wider costs latency; narrower
    risks discarding the right clause before it can be scored properly."""

    use_reranker: bool = True
    lexical_weight: float = DEFAULT_FUSION_WEIGHTS[1]
    jurisdictions: list[str] | None = None
    as_of: object | None = None


async def search(
    session: AsyncSession,
    query: str,
    *,
    options: SearchOptions | None = None,
) -> RetrievalResult:
    """Retrieve the clauses most likely to govern `query`."""
    opts = options or SearchOptions()
    settings = get_settings()

    vector = await embed_query(query)
    dense = await dense_search(
        session,
        vector,
        limit=max(opts.candidates, settings.retrieval_top_k),
        jurisdictions=opts.jurisdictions,
        as_of=opts.as_of,
    )

    lexical: list[Retrieved] = []
    candidates = dense
    if opts.lexical_weight > 0:
        lexical = await lexical_search(
            session,
            query,
            limit=max(opts.candidates, settings.retrieval_top_k),
            jurisdictions=opts.jurisdictions,
            as_of=opts.as_of,
        )
        candidates = reciprocal_rank_fusion([dense, lexical], weights=[1.0, opts.lexical_weight])

    shortlist = candidates[: opts.candidates]

    if opts.use_reranker and shortlist and reranker_available():
        results = await rerank(query, list(shortlist), top_n=opts.top_k)
    else:
        results = shortlist[: opts.top_k]

    return RetrievalResult(results=results, dense_count=len(dense), lexical_count=len(lexical))


__all__ = ["SearchOptions", "search"]
