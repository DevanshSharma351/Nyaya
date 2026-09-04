"""Ingest an amendment to the Master Direction, as version 2.

The impact module answers "the regulator amended the source, what is now
wrong?", and it cannot answer anything without two versions of a document to
compare. This seeds the second one.

The amendment is expressed as the edits themselves rather than as a second copy
of the file. That is deliberate on two counts. A duplicated two-hundred-line
corpus drifts from the original the first time either is touched, and more
importantly the amendment *is* the diff: writing it this way means the change
being demonstrated is stated in one place, in a form a reader can check against
the original.

The three edits are chosen to exercise all three cases the walk distinguishes:

  - 22(a) is amended. Requirements citing it may still be correct and a human
    has to read them, so they are reported as stale.
  - 26(a) is amended in a way that changes a number a requirement may have
    quoted, which is the case most likely to go unnoticed by a human reader.
  - 26(b) is removed outright. Anything citing it is orphaned: it now cites a
    clause that does not exist, and is wrong rather than merely doubtful.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import date
from pathlib import Path

from nyaya.db import session_scope
from nyaya.ingestion import ingest_document

SOURCE = Path("knowledge_base/corpus/RBI-MD-KYC.txt")

# (original, replacement). An empty replacement removes the clause.
AMENDMENTS: list[tuple[str, str]] = [
    (
        "(a) screening shall be performed prior to activation of the account and no\n"
        "transaction shall be permitted until screening is completed;\n",
        "(a) screening shall be performed prior to activation of the account, no\n"
        "transaction shall be permitted until screening is completed, and the customer\n"
        "shall be re-screened at intervals not exceeding ninety days thereafter;\n",
    ),
    (
        "(a) records of the identity of customers and of the evidence obtained shall be\n"
        "preserved for a period of five years from the date of cessation of the\n"
        "relationship;\n",
        "(a) records of the identity of customers and of the evidence obtained shall be\n"
        "preserved for a period of eight years from the date of cessation of the\n"
        "relationship;\n",
    ),
    (
        "(b) records of transactions shall be preserved for a period of five years from\n"
        "the date of the transaction;\n",
        "",
    ),
]


def amended_text() -> str:
    text = SOURCE.read_text()
    for original, replacement in AMENDMENTS:
        if original not in text:
            raise SystemExit(
                "The corpus no longer contains a passage this amendment edits. "
                "Re-derive the amendment against the current text rather than "
                "ingesting a version that silently changes nothing:\n"
                f"{original.strip()[:90]}…"
            )
        text = text.replace(original, replacement, 1)
    return text


async def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE} not found; run this from the repository root")

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "RBI-MD-KYC-v2.txt"
        path.write_text(amended_text())
        async with session_scope() as session:
            report = await ingest_document(
                session,
                path,
                short_code="RBI-MD-KYC",
                title="Master Direction on Know Your Customer",
                issuer="Reserve Bank of India",
                jurisdiction="IN",
                doc_type="regulation",
                version="2",
                effective_from=date(2025, 4, 1),
            )
            print(f"  {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
