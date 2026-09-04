"""The Nyaya HTTP API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text

from nyaya.api.routers import analysis, graph, knowledge, projects
from nyaya.api.schemas import HealthOut
from nyaya.config import ModelRole
from nyaya.db import get_engine, get_sessionmaker
from nyaya.db.models import Clause
from nyaya.llm import aclose_all, get_provider

DESCRIPTION = """\
Agentic requirements engineering, compliance mapping and SDLC selection for
regulated financial software.

Every requirement carries citations that have been checked rather than trusted:
a cited clause must resolve, its quoted text must appear in it, and two
independent models must agree that it obliges the requirement before the mapping
is accepted without human review.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await aclose_all()
    await get_engine().dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nyaya",
        description=DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
    )

    # The frontend is served separately in development. Origins are listed
    # explicitly rather than wildcarded, since this API returns compliance
    # findings and should not be readable from an arbitrary page.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in (projects.router, knowledge.router, analysis.router, graph.router):
        app.include_router(router, prefix="/api")

    @app.get("/api/health", response_model=HealthOut, tags=["system"])
    async def health() -> HealthOut:
        """Report what is actually reachable.

        Model availability is included because a degraded run - retrieval
        without reranking, or citation checking without entailment - produces
        weaker guarantees, and a client should be able to see that rather than
        infer it from worse results.
        """
        database = True
        clauses = 0
        try:
            async with get_sessionmaker()() as session:
                await session.execute(text("SELECT 1"))
                clauses = (
                    await session.execute(select(func.count(Clause.id)))
                ).scalar_one()
        except Exception:
            database = False

        models: dict[str, bool] = {}
        for role in ModelRole:
            try:
                models[role.value] = await get_provider(role).health()
            except Exception:
                models[role.value] = False

        from nyaya.retrieval.nli import available as nli_available
        from nyaya.retrieval.rerank import available as reranker_available

        models["reranker"] = reranker_available()
        models["nli"] = nli_available()

        healthy = database and any(models.values())
        return HealthOut(
            status="ok" if healthy else "degraded",
            database=database,
            models=models,
            corpus_clauses=clauses,
        )

    return app


app = create_app()

__all__ = ["app", "create_app"]
