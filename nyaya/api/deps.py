"""Shared API dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.db import get_sessionmaker
from nyaya.graph.runner import WorkflowRunner


async def db_session() -> AsyncIterator[AsyncSession]:
    """A request-scoped session.

    Commits on success so an endpoint does not have to, and rolls back on any
    exception - a partially applied compliance write is worse than a failed one.
    """
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def workflow_runner(request: Request) -> WorkflowRunner:
    return cast(WorkflowRunner, request.app.state.workflow_runner)


__all__ = ["db_session", "workflow_runner"]
