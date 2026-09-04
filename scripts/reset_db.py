"""Drop and recreate the schema.

Development convenience only. Refuses to run outside a local environment,
because dropping every table is not something that should be one typo away in
any environment holding real data.
"""

from __future__ import annotations

import asyncio
import sys

import nyaya.db.models  # noqa: F401  - registers every mapper
from nyaya.config import get_settings
from nyaya.db import Base, get_engine


async def main() -> int:
    settings = get_settings()
    if settings.env != "local":
        print(f"refusing to reset schema in env={settings.env!r}", file=sys.stderr)
        return 1

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    print(f"schema recreated ({len(Base.metadata.tables)} tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
