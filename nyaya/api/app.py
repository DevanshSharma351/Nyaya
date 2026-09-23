"""The Nyaya HTTP API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from nyaya.api.routers import analysis, graph, knowledge, projects
from nyaya.api.schemas import HealthOut
from nyaya.config import ModelRole, get_settings
from nyaya.db import get_engine, get_sessionmaker
from nyaya.db.models import Clause, SourceDocument
from nyaya.llm import aclose_all, get_provider

logger = logging.getLogger(__name__)

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

    # The frontend is served separately, so its origin has to be allowed
    # explicitly. Listed rather than wildcarded: this API returns compliance
    # findings and should not be readable from an arbitrary page.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(httpx.TimeoutException)
    async def _model_timeout(_request: Request, exc: httpx.TimeoutException):
        """A slow local model is a condition, not a crash.

        It reached the client as a 500 with a traceback, which tells a reader
        that the application is broken when what actually happened is that an
        8B model on a laptop did not finish in time. The distinction matters
        because the remedies are completely different, and only one of them is
        available to the person reading it.
        """
        logger.warning("model timed out: %s", exc)
        return JSONResponse(
            status_code=504,
            content={
                "detail": (
                    "The local model did not respond within "
                    f"{get_settings().ollama_timeout_seconds:.0f} seconds. "
                    "Nothing is broken - extraction on an 8B model is slow, and "
                    "a long brief makes it slower. Try a shorter brief, or set "
                    "NYAYA_OLLAMA_TIMEOUT_SECONDS higher and retry."
                ),
                "kind": "model_timeout",
            },
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
                # Only clauses in currently in-force sources. Counting every
                # row includes superseded versions, and the moment an amendment
                # is ingested the figure jumps - 104 became 160 - while the
                # corpus a reader can actually cite has not grown at all.
                clauses = (
                    await session.execute(
                        select(func.count(Clause.id))
                        .select_from(Clause)
                        .join(SourceDocument, SourceDocument.id == Clause.document_id)
                        .where(SourceDocument.effective_to.is_(None))
                    )
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
