"""Ingest the bundled regulatory corpus into the knowledge base."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from nyaya.db import session_scope
from nyaya.ingestion import ingest_document

CORPUS = Path("knowledge_base/corpus")

SOURCES = [
    dict(
        path=CORPUS / "RBI-MD-KYC.txt",
        short_code="RBI-MD-KYC",
        title="Master Direction on Know Your Customer",
        issuer="Reserve Bank of India",
        jurisdiction="IN",
        doc_type="regulation",
        effective_from=date(2023, 1, 1),
    ),
    dict(
        path=CORPUS / "DPDP-2023.txt",
        short_code="DPDP-2023",
        title="Digital Personal Data Protection Provisions",
        issuer="Parliament of India",
        jurisdiction="IN",
        doc_type="regulation",
        effective_from=date(2023, 8, 11),
    ),
    dict(
        path=CORPUS / "GDPR.txt",
        short_code="GDPR",
        title="General Data Protection Provisions",
        issuer="European Parliament",
        jurisdiction="EU",
        doc_type="regulation",
        effective_from=date(2018, 5, 25),
    ),
]


async def main() -> int:
    async with session_scope() as session:
        for spec in SOURCES:
            report = await ingest_document(session, **spec)
            print(f"  {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
