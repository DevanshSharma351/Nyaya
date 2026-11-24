"""Drop and recreate the schema.

Development convenience only. Refuses to run outside a local environment,
because dropping every table is not something that should be one typo away in
any environment holding real data.
"""

from __future__ import annotations

import asyncio
import sys
from argparse import ArgumentParser

import nyaya.db.models  # noqa: F401  - registers every mapper
from nyaya.config import get_settings
from nyaya.db import Base, get_engine


async def main(*, init_only: bool = False) -> int:
    settings = get_settings()
    if not init_only and settings.env != "local":
        print(f"refusing to reset schema in env={settings.env!r}", file=sys.stderr)
        return 1

    engine = get_engine()
    try:
        async with engine.begin() as conn:
            if not init_only:
                await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()

    action = "initialized" if init_only else "recreated"
    print(f"schema {action} ({len(Base.metadata.tables)} tables)")
    return 0


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--init-only", action="store_true", help="Create missing tables without dropping data"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(init_only=args.init_only)))
