"""Measure the retrieval spine before any agent depends on it.

Every downstream metric - citation correctness, control coverage, hallucination
rate - is bounded above by whether the right clause was retrieved at all. So
retrieval is benchmarked in isolation first, with each arm run over the same
labelled set.

Arms are cumulative, so each row isolates the contribution of one component:

    dense      embeddings alone
    lexical    full-text alone
    hybrid     the two fused by RRF
    +rerank    hybrid, reordered by a cross-encoder
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.db import session_scope
from nyaya.eval.metrics import hit_at_k, mean, ndcg_at_k, recall_at_k, reciprocal_rank
from nyaya.eval.retrieval_gold import ALL_QUERIES, GoldQuery, by_style
from nyaya.retrieval.embedder import embed_query
from nyaya.retrieval.hybrid import (
    dense_search,
    lexical_search,
    reciprocal_rank_fusion,
)
from nyaya.retrieval.rerank import available as reranker_available
from nyaya.retrieval.rerank import rerank

CUTOFFS = (1, 3, 5, 10)
ARM_ORDER = ("lexical", "dense", "hybrid", "dense+rr", "hybrid+rr")


@dataclass(slots=True)
class ArmResult:
    """Aggregate scores for one retrieval configuration."""

    name: str
    mrr: float = 0.0
    recall: dict[int, float] = field(default_factory=dict)
    hit: dict[int, float] = field(default_factory=dict)
    ndcg: dict[int, float] = field(default_factory=dict)
    misses: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def row(self) -> str:
        return (
            f"{self.name:<10} "
            f"{self.mrr:>6.3f} "
            + " ".join(f"{self.recall[k]:>6.3f}" for k in CUTOFFS)
            + f"  {self.ndcg[10]:>6.3f}"
            + f"  {self.hit[5]:>6.3f}"
            + f"  {self.latency_ms:>7.1f}"
        )


@dataclass(slots=True)
class PerQuery:
    qid: str
    arm: str
    ranked: list[str]
    primary_rank: int | None


async def _run_arms(
    session: AsyncSession,
    gold: GoldQuery,
    *,
    per_arm: int = 40,
    top: int = 10,
    use_reranker: bool = False,
    fusion_weight: float = 0.35,
) -> dict[str, list[str]]:
    """Return the ranked citation keys produced by each arm for one query."""
    vector = await embed_query(gold.query)
    jurisdictions = list(gold.jurisdictions)

    dense = await dense_search(session, vector, limit=per_arm, jurisdictions=jurisdictions)
    lexical = await lexical_search(session, gold.query, limit=per_arm, jurisdictions=jurisdictions)
    fused = reciprocal_rank_fusion([dense, lexical], weights=[1.0, fusion_weight])

    arms = {
        "dense": [r.citation_key for r in dense[:top]],
        "lexical": [r.citation_key for r in lexical[:top]],
        "hybrid": [r.citation_key for r in fused[:top]],
    }

    if use_reranker:
        # Rerank the fused shortlist, and dense alone, so the reranker's
        # contribution can be attributed to each base separately.
        arms["hybrid+rr"] = [
            r.citation_key for r in await rerank(gold.query, list(fused[:30]), top_n=top)
        ]
        arms["dense+rr"] = [
            r.citation_key for r in await rerank(gold.query, list(dense[:30]), top_n=top)
        ]
    return arms


def _score(name: str, runs: list[tuple[GoldQuery, list[str]]], latency_ms: float) -> ArmResult:
    result = ArmResult(name=name, latency_ms=latency_ms)
    result.mrr = mean([reciprocal_rank(keys, g.primary) for g, keys in runs])
    for k in CUTOFFS:
        result.recall[k] = mean([recall_at_k(keys, set(g.relevant), k) for g, keys in runs])
        result.hit[k] = mean([hit_at_k(keys, set(g.relevant), k) for g, keys in runs])
        result.ndcg[k] = mean([ndcg_at_k(keys, set(g.relevant), k) for g, keys in runs])
    result.misses = [g.qid for g, keys in runs if reciprocal_rank(keys, g.primary) == 0.0]
    return result


async def evaluate(
    top: int = 10,
    *,
    queries: tuple[GoldQuery, ...] = ALL_QUERIES,
    use_reranker: bool | None = None,
) -> tuple[dict[str, ArmResult], list[PerQuery]]:
    """Run every arm over `queries` and return aggregates plus per-query detail."""
    if use_reranker is None:
        use_reranker = reranker_available()

    collected: dict[str, list[tuple[GoldQuery, list[str]]]] = {}
    per_query: list[PerQuery] = []
    started = time.perf_counter()

    async with session_scope() as session:
        for gold in queries:
            arms = await _run_arms(session, gold, top=top, use_reranker=use_reranker)
            for name, keys in arms.items():
                collected.setdefault(name, []).append((gold, keys))
                rank = keys.index(gold.primary) + 1 if gold.primary in keys else None
                per_query.append(PerQuery(gold.qid, name, keys, rank))

    elapsed_ms = (time.perf_counter() - started) * 1000 / max(len(queries), 1)
    return (
        {name: _score(name, runs, elapsed_ms) for name, runs in collected.items()},
        per_query,
    )


def render(results: dict[str, ArmResult]) -> str:
    header = (
        f"{'arm':<10} {'MRR':>6} "
        + " ".join(f"{'R@' + str(k):>6}" for k in CUTOFFS)
        + f"  {'nDCG10':>6}  {'Hit@5':>6}  {'ms/q':>7}"
    )
    lines = [header, "-" * len(header)]
    lines += [results[name].row() for name in ARM_ORDER if name in results]
    return "\n".join(lines)


async def main() -> int:
    use_rr = reranker_available()
    if not use_rr:
        print("(reranker unavailable - skipping rerank arms)\n")

    for style in ("paraphrase", "term_of_art"):
        subset = by_style(style)
        results, _ = await evaluate(queries=subset, use_reranker=use_rr)
        print(f"=== {style}  (n={len(subset)}) ===")
        print(render(results))
        for name in ARM_ORDER:
            if name in results and results[name].misses:
                print(f"  {name:<10} primary outside top-10: {', '.join(results[name].misses)}")
        print()

    results, _ = await evaluate(use_reranker=use_rr)
    print(f"=== combined  (n={len(ALL_QUERIES)}) ===")
    print(render(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
