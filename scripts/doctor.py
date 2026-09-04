"""Check that everything the application needs is actually running.

Written because the failure this project produces most often is not a bug in
any module: it is the API not running, or Postgres not up, or Ollama not
serving. Every one of those surfaces in the browser as "Failed to fetch" on
every page at once, which looks like the frontend is broken and is not.

Each check reports what is wrong *and* the command that fixes it. A diagnostic
that tells you something is down without telling you how to bring it up has
only moved the question.
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass

import httpx
from sqlalchemy import func, select, text

from nyaya.config import ModelRole, get_settings
from nyaya.db import get_engine
from nyaya.db.models import Clause, SourceDocument

OK = "  ok  "
DOWN = " down "


@dataclass(slots=True)
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def _port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def check_postgres() -> Check:
    settings = get_settings()
    if not _port_open(settings.postgres_host, settings.postgres_port):
        return Check(
            "postgres",
            False,
            f"nothing listening on {settings.postgres_host}:{settings.postgres_port}",
            "make up",
        )
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return Check("postgres", True, f"port {settings.postgres_port}")
    except Exception as exc:
        return Check("postgres", False, str(exc)[:110], "make up")


async def check_corpus() -> Check:
    try:
        async with get_engine().connect() as conn:
            clauses = await conn.scalar(
                select(func.count(Clause.id))
                .select_from(Clause)
                .join(SourceDocument, SourceDocument.id == Clause.document_id)
                .where(SourceDocument.effective_to.is_(None))
            )
            versioned = await conn.scalar(
                select(func.count())
                .select_from(
                    select(SourceDocument.short_code)
                    .group_by(SourceDocument.short_code)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
    except Exception as exc:
        return Check("corpus", False, str(exc)[:110], "make seed")

    if not clauses:
        return Check("corpus", False, "no clauses ingested", "make seed")
    detail = f"{clauses} clauses in force"
    if not versioned:
        # Not fatal, but the impact module cannot do anything without it.
        return Check(
            "corpus", True, f"{detail}; no amended source, so /impact has nothing to compare"
        )
    return Check("corpus", True, f"{detail}, {versioned} source with an amendment")


async def check_ollama() -> Check:
    settings = get_settings()
    base = settings.ollama_base_url
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            body = (await client.get(f"{base}/api/tags")).json()
    except Exception:
        return Check("ollama", False, f"unreachable at {base}", "ollama serve")

    have = {m["name"].split(":")[0] for m in body.get("models", [])}
    want = {settings.model_for(role).model.split(":")[0] for role in ModelRole}
    missing = sorted(want - have)
    if missing:
        return Check(
            "ollama",
            False,
            f"missing {', '.join(missing)}",
            " && ".join(f"ollama pull {m}" for m in missing),
        )
    return Check("ollama", True, f"{len(have)} models present")


async def check_api() -> Check:
    if not _port_open("127.0.0.1", 8000):
        return Check("api", False, "nothing listening on :8000", "make api")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            body = (await client.get("http://127.0.0.1:8000/api/health")).json()
    except Exception as exc:
        return Check("api", False, str(exc)[:110], "make api")

    down = [name for name, up in body.get("models", {}).items() if not up]
    if down:
        return Check("api", True, f"reachable, but {', '.join(down)} unavailable")
    return Check("api", True, f"reachable, {body.get('corpus_clauses')} clauses")


def check_cors() -> Check:
    """The one failure that looks exactly like the API being down.

    A rejected origin reaches the browser as "Failed to fetch" with no further
    detail, while the server logs a perfectly normal 200. Worth stating.
    """
    origins = get_settings().allowed_origins
    expected = {"http://localhost:3000", "http://localhost:3100"}
    missing = sorted(expected - set(origins))
    if missing:
        return Check(
            "cors",
            False,
            f"{', '.join(missing)} not allowed; the browser will report 'Failed to fetch'",
            "set NYAYA_CORS_ORIGINS to include the frontend's origin",
        )
    return Check("cors", True, f"{len(origins)} origins allowed")


async def main() -> int:
    checks = [
        await check_postgres(),
        await check_corpus(),
        await check_ollama(),
        check_cors(),
        await check_api(),
    ]

    print()
    for check in checks:
        mark = OK if check.ok else DOWN
        print(f"[{mark}] {check.name:<10} {check.detail}")
        if not check.ok and check.fix:
            print(f"          fix: {check.fix}")
    print()

    failed = [c for c in checks if not c.ok]
    if failed:
        print(f"{len(failed)} of {len(checks)} checks failed.\n")
        return 1
    print("Everything the application needs is up.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
