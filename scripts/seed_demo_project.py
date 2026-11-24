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
from sqlalchemy.orm import selectinload

from nyaya.core.enums import (
    ApprovalStatus,
    EvidenceRelation,
    Priority,
    RiskLevel,
)
from nyaya.db import session_scope
from nyaya.db.models import (
    Clause,
    ControlMapping,
    Evidence,
    Interview,
    Project,
    Requirement,
    SourceDocument,
    Utterance,
)

PROJECT = "eKYC onboarding — retail"
DEMO_GENERATOR = "seed:demo-baseline"

# Synthetic stakeholder quotes and acceptance checks for the historical demo.
# Each named control uses the same citation as its requirement's evidence.
DEMO_DETAILS = {
    "FR-KYC-001": (
        "Screen remote applicants against the designated-persons list before activating their accounts.",
        "Given an applicant whose screening is pending, an activation request is denied.",
        "KYC.SCREEN.SANCTIONS",
    ),
    "FR-KYC-002": (
        "Keep customer identification records for five years after the relationship ends.",
        "Given a relationship closed four years ago, an authorised reviewer can retrieve the identification record.",
        "KYC.RECORDS.RETENTION",
    ),
    "FR-KYC-003": (
        "Keep each transaction record for five years from the date of the transaction.",
        "Given a transaction made four years ago, an authorised reviewer can retrieve its record.",
        None,
    ),
    "FR-KYC-004": (
        "For a business applicant, identify the beneficial owner and record who owns and controls the business.",
        "Given a company application with no identified beneficial owner, submission for approval is blocked.",
        "KYC.CDD.BENEFICIAL-OWNER",
    ),
    "FR-KYC-005": (
        "Assign every customer a low, medium, or high risk category. Keep that category confidential from the customer.",
        "Given a customer whose category is high, the customer-facing account view omits the category.",
        "KYC.RISK.NO-DISCLOSURE",
    ),
}

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
        project = await session.scalar(select(Project).where(Project.name == PROJECT))
        if project is None:
            project = Project(name=PROJECT, domain="ekyc_onboarding", jurisdictions=["IN", "EU"])
            session.add(project)
            await session.flush()

        existing = {
            row.ref: row
            for row in await session.scalars(
                select(Requirement)
                .where(Requirement.project_id == project.id, Requirement.version == 1)
                .options(
                    selectinload(Requirement.evidence), selectinload(Requirement.control_mappings)
                )
            )
        }
        missing_sources = [
            ref
            for ref in DEMO_DETAILS
            if ref not in existing
            or (
                existing[ref].generated_by == DEMO_GENERATOR
                and existing[ref].approval_status == ApprovalStatus.APPROVED
                and existing[ref].source_utterance_id is None
            )
        ]
        interview = None
        if missing_sources:
            interview = Interview(
                project_id=project.id,
                title="Synthetic demo brief",
                channel="brief",
                status="complete",
                utterances=[],
            )
            session.add(interview)

        unresolved: list[str] = []
        for index, (ref, statement, key, quote, priority, risk) in enumerate(BASELINE, 1):
            requirement = existing.get(ref)
            if requirement is not None and (
                requirement.generated_by != DEMO_GENERATOR
                or requirement.approval_status != ApprovalStatus.APPROVED
                or requirement.statement != statement
            ):
                continue
            if requirement is None:
                requirement = Requirement(
                    project_id=project.id,
                    ref=ref,
                    statement=statement,
                    categories=["regulatory"],
                    priority=priority,
                    risk_level=risk,
                    approval_status=ApprovalStatus.APPROVED,
                    assumptions=[],
                    generated_by=DEMO_GENERATOR,
                    evidence=[],
                    control_mappings=[],
                )
                session.add(requirement)

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
            if clause is None or " ".join(quote.split()) not in " ".join(clause.text.split()):
                unresolved.append(key)
                continue

            source, criterion, control_id = DEMO_DETAILS[ref]
            if not requirement.acceptance_criteria:
                requirement.acceptance_criteria = [criterion]
            if interview is not None and ref in missing_sources:
                utterance = Utterance(
                    sequence=index, speaker="stakeholder", raw_text=source, masked_text=source
                )
                interview.utterances.append(utterance)
                requirement.source_utterance = utterance
            if not any(
                e.cited_key == key and e.clause_id == clause.id for e in requirement.evidence
            ):
                requirement.evidence.append(
                    Evidence(
                        clause_id=clause.id,
                        cited_key=key,
                        quoted_text=quote,
                        relation=EvidenceRelation.SUPPORTS,
                        resolved=True,
                    )
                )
            if control_id and not any(
                m.control_id == control_id for m in requirement.control_mappings
            ):
                requirement.control_mappings.append(
                    ControlMapping(
                        control_id=control_id,
                        clause_id=clause.id,
                        jurisdiction="IN",
                        proposed_by="rule",
                        validator_passed=True,
                        validator_detail={
                            "source": "synthetic_demo_baseline",
                            "quote_verified": True,
                        },
                    )
                )

        if unresolved:
            raise SystemExit(
                "These citations do not resolve against the ingested corpus, so "
                "the seed would create requirements whose stated authority does "
                f"not exist: {unresolved}. Run `make corpus` first."
            )

        print(f"  {PROJECT}: synthetic demo baseline ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
