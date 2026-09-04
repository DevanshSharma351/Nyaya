"""Shared API dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.db import get_sessionmaker


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


__all__ = ["db_session"]
