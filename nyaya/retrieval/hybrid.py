"""Hybrid retrieval over the clause corpus.

Two retrievers, fused. They fail in different directions, which is the whole
point of running both:

**Dense** (pgvector, cosine over bge-m3) matches paraphrase. A stakeholder says
"check the customer against the sanctions list"; the clause says "screening
against designated lists notified under the Act". No lexical overlap worth
speaking of, and dense retrieval finds it.

**Lexical** (Postgres full-text, `ts_rank_cd`) matches the terms of art that
dense retrieval blurs. "Beneficial owner", "step-up authentication" and
"politically exposed person" are precise legal categories; an embedding places
them near their neighbours, which is exactly wrong when the citation must name
*this* obligation and not an adjacent one.

Fused by **Reciprocal Rank Fusion**: scores from the two are not comparable
(cosine similarity against `ts_rank_cd`), and normalising them requires
per-corpus calibration that drifts. RRF uses only rank, so it needs no
calibration and is robust to either retriever producing a wild score.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import Float, Text, func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.db.models import Clause, SourceDocument

# RRF damping. 60 is the value from the original formulation; it flattens the
# contribution of top ranks enough that one retriever cannot dominate the fusion
# on the strength of a single confident hit.
RRF_K = 60

# (dense, lexical). Measured on the labelled eKYC set - see `nyaya.eval` and
# ADR-0004. Fusion is OFF by default because it was measured to *hurt*: dense
# alone scores MRR 0.659, RRF-fused hybrid 0.620, and after reranking the two
# are numerically identical (0.737), meaning the lexical arm contributes nothing
# but latency. Set a non-zero weight to re-enable it - the knob is retained
# because this result is corpus-dependent and should be re-measured as the KB
# grows.
DEFAULT_FUSION_WEIGHTS = (1.0, 0.0)

# Regulatory hierarchies are shallow (part > chapter > section > sub-clause), so
# this bounds the upward walk without truncating a real chain.
MAX_ANCESTOR_DEPTH = 5

# Organisational divisions carry a title, not an obligation. They are already
# transparent to citation - nobody cites "Chapter IV, section 16" - and they must
# be transparent to context for the same reason: including one prepends a bare
# heading such as "SCREENING AND REPORTING" to the entailment premise, which
# adds no obligation and measurably dilutes the signal. Clause 22 scored
# `supports` 0.646 alone and `neutral` 0.427 with its chapter attached.
_ORGANISATIONAL = re.compile(r"^\s*(?:chapter|part|title)\b", re.I)


@dataclass(slots=True)
class Retrieved:
    """One clause returned by retrieval, with the scores that produced it."""

    clause_id: uuid.UUID
    citation_key: str
    text: str
    heading: str | None
    document_code: str
    jurisdiction: str

    dense_rank: int | None = None
    lexical_rank: int | None = None
    dense_score: float | None = None
    lexical_score: float | None = None
    fused_score: float = 0.0
    rerank_score: float | None = None

    ancestors: list[str] = field(default_factory=list)
    """Text of enclosing clauses, outermost first. Populated by `load_context`."""

    @property
    def display(self) -> str:
        """Heading plus body, as shown to a model or a reader."""
        return f"{self.heading}\n{self.text}" if self.heading else self.text

    @property
    def contextual(self) -> str:
        """The clause together with its enclosing clauses.

        A leaf sub-clause is frequently meaningless alone: `22(a)` reads
        "screening shall be performed prior to activation", which never says
        what is being screened against - that is in the parent. Measured on
        exactly that pair, the sub-clause alone entailed the requirement at
        0.004 while the clause with its parent entailed it at 0.994.

        So this, not `display`, is what should be used as an entailment premise
        and as evidence shown to a model. `display` remains for citation
        rendering, where the quoted span must be the clause itself.
        """
        return " ".join([*self.ancestors, self.display]).strip()


@dataclass(slots=True)
class RetrievalResult:
    results: list[Retrieved] = field(default_factory=list)
    dense_count: int = 0
    lexical_count: int = 0

    def __len__(self) -> int:
        return len(self.results)

    def keys(self) -> list[str]:
        return [r.citation_key for r in self.results]


def _base_select():
    return select(
        Clause.id,
        Clause.citation_key,
        Clause.text,
        Clause.heading,
        SourceDocument.short_code,
        SourceDocument.jurisdiction,
    ).join(SourceDocument, Clause.document_id == SourceDocument.id)


def _apply_scope(stmt, jurisdictions: list[str] | None, as_of: object | None):
    """Restrict retrieval to applicable, in-force sources.

    Retrieving a superseded clause would let the system cite a regulation that
    is no longer in force - a compliance failure dressed up as a citation.
    """
    if jurisdictions:
        stmt = stmt.where(SourceDocument.jurisdiction.in_(jurisdictions))
    stmt = stmt.where(SourceDocument.is_authoritative.is_(True))
    if as_of is not None:
        stmt = stmt.where(
            (SourceDocument.effective_from.is_(None)) | (SourceDocument.effective_from <= as_of)
        ).where((SourceDocument.effective_to.is_(None)) | (SourceDocument.effective_to > as_of))
    else:
        stmt = stmt.where(SourceDocument.effective_to.is_(None))
    return stmt


async def dense_search(
    session: AsyncSession,
    query_vector: list[float],
    *,
    limit: int = 40,
    jurisdictions: list[str] | None = None,
    as_of: object | None = None,
) -> list[Retrieved]:
    """Nearest neighbours by cosine distance."""
    distance = Clause.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        _apply_scope(
            _base_select().add_columns(distance).where(Clause.embedding.isnot(None)),
            jurisdictions,
            as_of,
        )
        .order_by(distance)
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()
    return [
        Retrieved(
            clause_id=r[0],
            citation_key=r[1],
            text=r[2],
            heading=r[3],
            document_code=r[4],
            jurisdiction=r[5],
            dense_rank=i,
            dense_score=1.0 - float(r[6]),  # cosine similarity
        )
        for i, r in enumerate(rows, start=1)
    ]


async def lexical_search(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 40,
    jurisdictions: list[str] | None = None,
    as_of: object | None = None,
) -> list[Retrieved]:
    """Full-text search over the generated `search_vector` column.

    The query is converted to a **disjunction**. Postgres's query builders all
    conjoin terms, which is fatal here: a stakeholder question runs to fifteen
    words, and demanding that one clause contain every stemmed term matches
    nothing at all. Measured on the labelled set, the conjunctive form returned
    zero rows for 22 of 24 queries.

    Disjunction alone would be indiscriminate, so ranking does the discriminating:
    `ts_rank_cd` weights by term density and proximity, rewarding clauses that
    contain more of the query terms close together. Recall comes from the OR,
    precision from the ranking.

    `plainto_tsquery` is used as the source of the lexemes because it already
    performs stemming, stopword removal and escaping; only the operator is
    rewritten.
    """
    tsquery = func.replace(func.plainto_tsquery("english", query).cast(Text), " & ", " | ").cast(
        TSQUERY
    )
    # ts_rank_cd weights by term density and proximity, which suits clause-length
    # text better than ts_rank's raw frequency count.
    rank = func.ts_rank_cd(Clause.search_vector, tsquery).cast(Float).label("rank")

    stmt = (
        _apply_scope(
            _base_select().add_columns(rank).where(Clause.search_vector.op("@@")(tsquery)),
            jurisdictions,
            as_of,
        )
        .order_by(rank.desc())
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()
    return [
        Retrieved(
            clause_id=r[0],
            citation_key=r[1],
            text=r[2],
            heading=r[3],
            document_code=r[4],
            jurisdiction=r[5],
            lexical_rank=i,
            lexical_score=float(r[6]),
        )
        for i, r in enumerate(rows, start=1)
    ]


def reciprocal_rank_fusion(
    runs: list[list[Retrieved]],
    *,
    k: int = RRF_K,
    limit: int | None = None,
    weights: list[float] | None = None,
) -> list[Retrieved]:
    """Fuse ranked runs by Reciprocal Rank Fusion.

    Each run contributes `weight / (k + rank)` per document. Only ranks are used,
    so no score normalisation is required between retrievers whose scores live on
    incomparable scales.

    `weights` exists because **unweighted RRF assumes the arms are of comparable
    quality, and ours are not.** Measured on the labelled set, dense retrieval
    scores MRR 0.579 and lexical 0.249; fusing them equally produced 0.443 -
    worse than dense alone. Weighting restores the stronger arm's precedence
    while keeping the weaker one's distinct recall.
    """
    merged: dict[uuid.UUID, Retrieved] = {}
    scores: dict[uuid.UUID, float] = {}
    run_weights = weights or [1.0] * len(runs)
    if len(run_weights) != len(runs):
        raise ValueError(f"{len(run_weights)} weights for {len(runs)} runs")

    for run, weight in zip(runs, run_weights, strict=True):
        for rank, item in enumerate(run, start=1):
            existing = merged.get(item.clause_id)
            if existing is None:
                merged[item.clause_id] = item
            else:
                # Same clause found by both retrievers: keep each rank and score.
                existing.dense_rank = existing.dense_rank or item.dense_rank
                existing.lexical_rank = existing.lexical_rank or item.lexical_rank
                existing.dense_score = existing.dense_score or item.dense_score
                existing.lexical_score = existing.lexical_score or item.lexical_score
            scores[item.clause_id] = scores.get(item.clause_id, 0.0) + weight / (k + rank)

    for clause_id, score in scores.items():
        merged[clause_id].fused_score = score

    ordered = sorted(merged.values(), key=lambda r: r.fused_score, reverse=True)
    return ordered[:limit] if limit else ordered


async def hybrid_search(
    session: AsyncSession,
    query: str,
    query_vector: list[float],
    *,
    limit: int = 40,
    candidates_per_arm: int | None = None,
    jurisdictions: list[str] | None = None,
    as_of: object | None = None,
    fusion_weights: tuple[float, float] | None = None,
) -> RetrievalResult:
    """Run both retrievers and fuse them.

    Each arm retrieves more candidates than the final limit, because a document
    ranked poorly by one retriever and well by the other should still surface -
    which cannot happen if each arm is truncated to the output width first.
    """
    per_arm = candidates_per_arm or max(limit, 40)
    weights = fusion_weights or DEFAULT_FUSION_WEIGHTS

    dense = await dense_search(
        session, query_vector, limit=per_arm, jurisdictions=jurisdictions, as_of=as_of
    )
    lexical = await lexical_search(
        session, query, limit=per_arm, jurisdictions=jurisdictions, as_of=as_of
    )

    fused = reciprocal_rank_fusion([dense, lexical], limit=limit, weights=list(weights))
    return RetrievalResult(results=fused, dense_count=len(dense), lexical_count=len(lexical))


async def load_context(session: AsyncSession, items: list[Retrieved]) -> None:
    """Populate `ancestors` on each item by walking the clause hierarchy upward.

    Ancestors are fetched level by level rather than per item, so the number of
    queries is bounded by hierarchy depth instead of by result count.
    """
    if not items:
        return

    by_id = {item.clause_id: item for item in items}
    chains: dict[uuid.UUID, list[str]] = {item.clause_id: [] for item in items}
    # clause id currently being resolved -> the results awaiting its ancestors
    frontier: dict[uuid.UUID, list[uuid.UUID]] = {
        item.clause_id: [item.clause_id] for item in items
    }

    for _ in range(MAX_ANCESTOR_DEPTH):
        if not frontier:
            break

        rows = (
            await session.execute(
                select(Clause.id, Clause.parent_id).where(Clause.id.in_(frontier.keys()))
            )
        ).all()

        owners_by_parent: dict[uuid.UUID, list[uuid.UUID]] = {}
        for clause_id, parent_id in rows:
            if parent_id is None:
                continue
            owners_by_parent.setdefault(parent_id, []).extend(frontier[clause_id])

        if not owners_by_parent:
            break

        parent_rows = (
            await session.execute(
                select(Clause.id, Clause.heading, Clause.text, Clause.clause_number).where(
                    Clause.id.in_(owners_by_parent.keys())
                )
            )
        ).all()

        for parent_id, heading, text, number in parent_rows:
            if number and _ORGANISATIONAL.match(number):
                continue  # a division heading, not an obligation
            body = f"{heading} {text}".strip() if heading else (text or "")
            for owner_id in owners_by_parent[parent_id]:
                chains[owner_id].insert(0, body)

        frontier = owners_by_parent

    for clause_id, chain in chains.items():
        by_id[clause_id].ancestors = [c for c in chain if c]


async def resolve_citation(session: AsyncSession, citation_key: str) -> Retrieved | None:
    """Look up a clause by its exact citation key.

    Used by the deterministic validator: a citation that does not resolve here
    is recorded as unresolvable rather than trusted.
    """
    stmt = _base_select().where(Clause.citation_key == citation_key).limit(1)
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    return Retrieved(
        clause_id=row[0],
        citation_key=row[1],
        text=row[2],
        heading=row[3],
        document_code=row[4],
        jurisdiction=row[5],
    )


__all__ = [
    "DEFAULT_FUSION_WEIGHTS",
    "MAX_ANCESTOR_DEPTH",
    "RRF_K",
    "RetrievalResult",
    "Retrieved",
    "dense_search",
    "hybrid_search",
    "lexical_search",
    "load_context",
    "reciprocal_rank_fusion",
    "resolve_citation",
]
