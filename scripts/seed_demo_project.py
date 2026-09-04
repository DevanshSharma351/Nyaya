"""Seed the demonstration baseline: an approved eKYC project with citations.

The impact module answers "which of our requirements does this amendment
break?", and it can only answer that if some requirements exist to be broken.
This creates them.

Two things about this data are deliberate.

Every requirement here cites a clause that really is in the corpus, and quotes
text that really appears in it. Seeding a demo with invented citations would
make the one module whose entire subject is citation integrity the only one
running on citations that were never checked.

The set is chosen to exercise the distinction the walk draws. Two requirements
cite clauses the bundled amendment touches - one amended, one removed - and two
cite clauses it leaves alone. If the untouched pair ever shows up in an impact
report, the walk is over-reporting, and a change report that cries wolf is one
nobody reads.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from nyaya.core.enums import (
    ApprovalStatus,
    EvidenceRelation,
    Priority,
    RiskLevel,
)
from nyaya.db import session_scope
from nyaya.db.models import Clause, Evidence, Project, Requirement, SourceDocument

PROJECT = "eKYC onboarding — retail"

# (ref, statement, citation, quoted text, priority, risk)
BASELINE: list[tuple[str, str, str, str, Priority, RiskLevel]] = [
    (
        "FR-KYC-001",
        "When a customer is onboarded remotely, the system shall screen the "
        "customer against the designated-persons list before the account is "
        "activated.",
        "RBI-MD-KYC:22(a)",
        "screening shall be performed prior to activation of the account",
        Priority.MUST,
        RiskLevel.CRITICAL,
    ),
    (
        "FR-KYC-002",
        "The system shall retain customer identification records for five years "
        "from the date the relationship ceases.",
        "RBI-MD-KYC:26(a)",
        "preserved for a period of five years from the date of cessation",
        Priority.MUST,
        RiskLevel.HIGH,
    ),
    (
        "FR-KYC-003",
        "The system shall retain transaction records for five years from the date "
        "of the transaction.",
        "RBI-MD-KYC:26(b)",
        "records of transactions shall be preserved for a period of five years",
        Priority.MUST,
        RiskLevel.HIGH,
    ),
    (
        "FR-KYC-004",
        "The system shall identify the beneficial owner of a legal person and "
        "record the ownership and control structure.",
        "RBI-MD-KYC:16(b)",
        "identify the beneficial owner and take reasonable measures to verify",
        Priority.MUST,
        RiskLevel.HIGH,
    ),
    (
        "FR-KYC-005",
        "The system shall assign every customer a risk category of low, medium or "
        "high, and shall not disclose that category to the customer.",
        "RBI-MD-KYC:17(b)",
        "shall not be disclosed to the customer",
        Priority.MUST,
        RiskLevel.MEDIUM,
    ),
]


async def main() -> int:
    async with session_scope() as session:
        existing = await session.scalar(select(Project).where(Project.name == PROJECT))
        if existing is not None:
            print(f"  {PROJECT!r} already present; nothing to do")
            return 0

        project = Project(
            name=PROJECT,
            domain="ekyc_onboarding",
            jurisdictions=["IN", "EU"],
        )
        session.add(project)
        await session.flush()

        unresolved: list[str] = []
        for ref, statement, key, quote, priority, risk in BASELINE:
            requirement = Requirement(
                project_id=project.id,
                ref=ref,
                statement=statement,
                categories=["regulatory"],
                priority=priority,
                risk_level=risk,
                approval_status=ApprovalStatus.APPROVED,
                acceptance_criteria=[],
                assumptions=[],
                generated_by="seed:demo-baseline",
            )
            session.add(requirement)
            await session.flush()

            # Resolve the citation rather than trusting it. An unresolvable key
            # means the corpus and this file have diverged, and a demonstration
            # of citation integrity should be the last thing to ship a dangling
            # citation.
            #
            # Resolved against the *earliest* version of the source, because
            # that is what this baseline represents: requirements approved while
            # version 1 was in force, which the amendment then arrives to
            # disturb. Resolving against the current version instead would be
            # both anachronistic and impossible - 26(b) does not exist in v2,
            # which is precisely the finding the impact module is there to make.
            clause = await session.scalar(
                select(Clause)
                .join(SourceDocument, SourceDocument.id == Clause.document_id)
                .where(Clause.citation_key == key)
                .order_by(SourceDocument.version)
                .limit(1)
            )
            if clause is None:
                unresolved.append(key)

            session.add(
                Evidence(
                    requirement_id=requirement.id,
                    clause_id=clause.id if clause else None,
                    cited_key=key,
                    quoted_text=quote,
                    relation=EvidenceRelation.SUPPORTS,
                    resolved=clause is not None,
                )
            )

        if unresolved:
            raise SystemExit(
                "These citations do not resolve against the ingested corpus, so "
                "the seed would create requirements whose stated authority does "
                f"not exist: {unresolved}. Run `make corpus` first."
            )

        print(f"  {PROJECT}: {len(BASELINE)} approved requirements, all citations resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
