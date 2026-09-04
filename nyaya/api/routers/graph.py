"""The traceability graph, shaped for visualisation.

Returns nodes and edges rather than a rendered picture, so the client decides
how to draw it. The graph is the same structure the change-impact walk
traverses - what a viewer explores and what the analysis queries are one thing,
which is why a highlighted path in the UI corresponds to a real derivation
rather than a decorative link.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.api.deps import db_session
from nyaya.api.schemas import GraphEdge, GraphNode, GraphOut
from nyaya.db.models import Clause, ControlMapping, Evidence, Requirement, SourceDocument

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/{project_id}", response_model=GraphOut)
async def project_graph(
    project_id: uuid.UUID, session: AsyncSession = Depends(db_session)
):
    """Requirements, the clauses they cite, and the controls they satisfy."""
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    requirements = (
        await session.execute(
            select(Requirement).where(Requirement.project_id == project_id)
        )
    ).scalars().all()

    for requirement in requirements:
        node_id = f"req:{requirement.id}"
        nodes[node_id] = GraphNode(
            id=node_id,
            kind="requirement",
            label=requirement.ref,
            detail=requirement.statement,
            status=str(requirement.approval_status),
            # Risk drives visual weight, so the eye lands on what matters first.
            weight={"low": 1.0, "medium": 1.4, "high": 1.8, "critical": 2.3}.get(
                str(requirement.risk_level), 1.0
            ),
        )

    requirement_ids = [r.id for r in requirements]
    if not requirement_ids:
        return GraphOut(nodes=[], edges=[])

    citations = (
        await session.execute(
            select(Evidence, Clause, SourceDocument)
            .join(Clause, Clause.id == Evidence.clause_id, isouter=True)
            .join(SourceDocument, SourceDocument.id == Clause.document_id, isouter=True)
            .where(Evidence.requirement_id.in_(requirement_ids))
        )
    ).all()

    for evidence, clause, document in citations:
        # An unresolved citation still becomes a node. Hiding it would remove
        # from the picture exactly the finding a reviewer most needs to see.
        node_id = f"clause:{evidence.cited_key}"
        if node_id not in nodes:
            nodes[node_id] = GraphNode(
                id=node_id,
                kind="clause",
                label=evidence.cited_key,
                detail=(clause.text if clause is not None else "unresolved citation"),
                status=("resolved" if evidence.resolved else "unresolved"),
                weight=1.2 if evidence.resolved else 0.8,
            )
            if document is not None:
                doc_id = f"doc:{document.short_code}"
                nodes.setdefault(
                    doc_id,
                    GraphNode(
                        id=doc_id, kind="document", label=document.short_code,
                        detail=document.title, status=document.jurisdiction, weight=2.6,
                    ),
                )
                edges.append(
                    GraphEdge(source=node_id, target=doc_id, relation="part_of", strength=0.4)
                )

        edges.append(
            GraphEdge(
                source=f"req:{evidence.requirement_id}",
                target=node_id,
                relation=str(evidence.relation),
                strength=float(evidence.entailment_score or 0.2),
            )
        )

    mappings = (
        await session.execute(
            select(ControlMapping).where(
                ControlMapping.requirement_id.in_(requirement_ids)
            )
        )
    ).scalars().all()

    for mapping in mappings:
        node_id = f"control:{mapping.control_id}"
        nodes.setdefault(
            node_id,
            GraphNode(
                id=node_id, kind="control", label=mapping.control_id,
                detail=f"proposed by {mapping.proposed_by}",
                status="confirmed" if mapping.validator_passed else "unconfirmed",
                weight=1.6,
            ),
        )
        edges.append(
            GraphEdge(
                source=f"req:{mapping.requirement_id}",
                target=node_id,
                relation="satisfies",
                strength=1.0 if mapping.validator_passed else 0.35,
            )
        )

    return GraphOut(nodes=list(nodes.values()), edges=edges)


@router.get("/demo/knowledge", response_model=GraphOut)
async def knowledge_graph(
    limit: int = 120, session: AsyncSession = Depends(db_session)
):
    """The clause hierarchy itself, for the landing visualisation.

    Available before any project exists, so the first thing a visitor sees is
    the actual regulatory corpus rather than a placeholder.
    """
    rows = (
        await session.execute(
            select(Clause, SourceDocument)
            .join(SourceDocument, SourceDocument.id == Clause.document_id)
            .where(SourceDocument.effective_to.is_(None))
            .order_by(Clause.depth, Clause.citation_key)
            .limit(limit)
        )
    ).all()

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    by_uuid: dict[uuid.UUID, str] = {}

    for clause, document in rows:
        doc_id = f"doc:{document.short_code}"
        nodes.setdefault(
            doc_id,
            GraphNode(
                id=doc_id, kind="document", label=document.short_code,
                detail=document.title, status=document.jurisdiction, weight=3.0,
            ),
        )
        node_id = f"clause:{clause.citation_key}"
        by_uuid[clause.id] = node_id
        nodes[node_id] = GraphNode(
            id=node_id, kind="clause", label=clause.citation_key,
            detail=(clause.heading or clause.text or "")[:180],
            status=document.jurisdiction,
            weight=max(0.6, 2.0 - clause.depth * 0.35),
        )
        edges.append(
            GraphEdge(source=node_id, target=doc_id, relation="part_of", strength=0.3)
        )

    for clause, _ in rows:
        if clause.parent_id in by_uuid:
            edges.append(
                GraphEdge(
                    source=by_uuid[clause.id],
                    target=by_uuid[clause.parent_id],
                    relation="within",
                    strength=0.8,
                )
            )

    return GraphOut(nodes=list(nodes.values()), edges=edges)


__all__ = ["router"]
