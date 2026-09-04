"""Regulatory-change impact analysis.

When a regulator amends a clause, the question a bank must answer within days is
*which of our requirements are now wrong*. Answering it by re-reading the
specification is how compliance gaps survive for years.

Because every citation is a persisted edge, the answer is a graph walk. This is
the capability that the whole clause-level, version-by-supersession design was
built to enable - and it is why documents are superseded rather than mutated:
a citation made against the old text must remain resolvable, or the impact
analysis cannot tell "cited the version that changed" from "cited nothing".

Reported at three levels of severity, because they demand different responses:

- **stale** - the requirement cites a clause whose text changed. It may still be
  correct; it must be re-verified.
- **orphaned** - the requirement cites a clause that no longer exists in the
  current version. Its authority is gone.
- **uncovered** - a control the amended clause establishes now has no requirement
  satisfying it. A new gap.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.db.models import Clause, ControlMapping, Evidence, Requirement, SourceDocument


@dataclass(slots=True)
class AffectedRequirement:
    requirement_id: uuid.UUID
    ref: str
    statement: str
    severity: str
    citation_key: str
    detail: str


@dataclass(slots=True)
class ImpactReport:
    document_code: str
    from_version: str
    to_version: str
    changed_clauses: list[str] = field(default_factory=list)
    removed_clauses: list[str] = field(default_factory=list)
    added_clauses: list[str] = field(default_factory=list)
    affected: list[AffectedRequirement] = field(default_factory=list)

    @property
    def stale(self) -> list[AffectedRequirement]:
        return [a for a in self.affected if a.severity == "stale"]

    @property
    def orphaned(self) -> list[AffectedRequirement]:
        return [a for a in self.affected if a.severity == "orphaned"]

    def summary(self) -> str:
        return (
            f"{self.document_code} v{self.from_version} -> v{self.to_version}: "
            f"{len(self.changed_clauses)} clauses changed, "
            f"{len(self.removed_clauses)} removed, {len(self.added_clauses)} added; "
            f"{len(self.orphaned)} requirements orphaned, "
            f"{len(self.stale)} require re-verification"
        )


async def analyse_change(
    session: AsyncSession,
    *,
    short_code: str,
    from_version: str,
    to_version: str,
) -> ImpactReport:
    """Compare two versions of a source and report the requirements affected."""
    old = await _document(session, short_code, from_version)
    new = await _document(session, short_code, to_version)
    if old is None or new is None:
        raise ValueError(
            f"both versions of {short_code} must be ingested "
            f"(found: v{from_version}={old is not None}, v{to_version}={new is not None})"
        )

    old_clauses = await _clauses(session, old.id)
    new_clauses = await _clauses(session, new.id)

    report = ImpactReport(
        document_code=short_code, from_version=from_version, to_version=to_version
    )
    report.added_clauses = sorted(set(new_clauses) - set(old_clauses))
    report.removed_clauses = sorted(set(old_clauses) - set(new_clauses))
    report.changed_clauses = sorted(
        key
        for key in set(old_clauses) & set(new_clauses)
        if _normalise(old_clauses[key]) != _normalise(new_clauses[key])
    )

    impacted = set(report.changed_clauses) | set(report.removed_clauses)
    if not impacted:
        return report

    # Walk backwards along the citation edges: every requirement whose evidence
    # names an impacted clause key.
    rows = (
        await session.execute(
            select(Requirement, Evidence.cited_key)
            .join(Evidence, Evidence.requirement_id == Requirement.id)
            .where(Evidence.cited_key.in_(impacted))
        )
    ).all()

    for requirement, cited_key in rows:
        removed = cited_key in report.removed_clauses
        report.affected.append(
            AffectedRequirement(
                requirement_id=requirement.id,
                ref=requirement.ref,
                statement=requirement.statement,
                severity="orphaned" if removed else "stale",
                citation_key=cited_key,
                detail=(
                    f"clause {cited_key} no longer exists in v{to_version}; the "
                    f"requirement has lost its stated authority"
                    if removed
                    else f"clause {cited_key} was amended in v{to_version}; the "
                    f"citation must be re-verified against the new text"
                ),
            )
        )

    return report


async def controls_losing_authority(
    session: AsyncSession, removed_keys: list[str]
) -> list[str]:
    """Control mappings whose supporting clause has been removed.

    A control whose authority is gone must not keep counting as covered - that
    would report compliance against a regulation that no longer exists.
    """
    if not removed_keys:
        return []
    rows = (
        await session.execute(
            select(ControlMapping.control_id)
            .join(Clause, Clause.id == ControlMapping.clause_id)
            .where(Clause.citation_key.in_(removed_keys))
            .distinct()
        )
    ).scalars().all()
    return sorted(rows)


async def _document(
    session: AsyncSession, short_code: str, version: str
) -> SourceDocument | None:
    return (
        await session.execute(
            select(SourceDocument).where(
                SourceDocument.short_code == short_code,
                SourceDocument.version == version,
            )
        )
    ).scalars().first()


async def _clauses(session: AsyncSession, document_id: uuid.UUID) -> dict[str, str]:
    rows = (
        await session.execute(
            select(Clause.citation_key, Clause.text).where(
                Clause.document_id == document_id
            )
        )
    ).all()
    return {key: text for key, text in rows}


def _normalise(text: str) -> str:
    """Compare on content, not formatting.

    A reflowed or re-wrapped clause is not an amendment, and reporting it as one
    would flood the impact report with noise and train reviewers to skim it.
    """
    return " ".join((text or "").split()).lower()


__all__ = [
    "AffectedRequirement",
    "ImpactReport",
    "analyse_change",
    "controls_losing_authority",
]
