"""Append-only, hash-chained audit ledger.

Every entry commits to its predecessor's hash, so altering or removing any past
entry invalidates every hash after it. `verify_chain` walks a project's ledger
and reports the first position where the chain breaks.

Writes are serialised per project: the sequence number and the previous hash
must be read and extended atomically, or two concurrent writers would fork the
chain. This is enforced with a transaction-scoped advisory lock rather than a
table lock, so unrelated projects never block one another.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from nyaya.db.models.audit import GENESIS_HASH, AuditEvent

# Arbitrary namespace constant, so advisory locks taken here cannot collide with
# locks taken by any other subsystem.
_LOCK_NAMESPACE = 0x4E59_4159  # "NYAY"


@dataclass(slots=True)
class ChainVerification:
    """Outcome of verifying a ledger chain."""

    intact: bool
    entries_checked: int
    broken_at: int | None = None
    reason: str | None = None


async def record(
    session: AsyncSession,
    *,
    project_id: uuid.UUID | None,
    event_type: str,
    actor: str,
    actor_kind: str = "agent",
    payload: dict[str, Any] | None = None,
    subject_kind: str | None = None,
    subject_id: uuid.UUID | None = None,
) -> AuditEvent:
    """Append one entry to the ledger and return it.

    The caller's surrounding transaction governs durability: the entry is
    written but not committed here, so an event is never recorded for work that
    was subsequently rolled back.
    """
    payload = payload or {}

    # Serialise appends for this project. The lock is released when the
    # enclosing transaction ends, so it covers exactly the read-then-append.
    lock_key = _lock_key(project_id)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:ns, :key)"),
        {"ns": _LOCK_NAMESPACE, "key": lock_key},
    )

    tail = (
        await session.execute(
            select(AuditEvent.sequence, AuditEvent.entry_hash)
            .where(AuditEvent.project_id == project_id)
            .order_by(AuditEvent.sequence.desc())
            .limit(1)
        )
    ).first()

    sequence = (tail.sequence + 1) if tail else 1
    prev_hash = tail.entry_hash if tail else GENESIS_HASH
    occurred_at = datetime.now(UTC)

    entry_hash = AuditEvent.compute_hash(
        prev_hash=prev_hash,
        sequence=sequence,
        occurred_at=occurred_at,
        event_type=event_type,
        actor=actor,
        payload=payload,
    )

    event = AuditEvent(
        project_id=project_id,
        sequence=sequence,
        occurred_at=occurred_at,
        event_type=event_type,
        actor=actor,
        actor_kind=actor_kind,
        subject_kind=subject_kind,
        subject_id=subject_id,
        payload=payload,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    session.add(event)
    await session.flush()
    return event


async def verify_chain(session: AsyncSession, project_id: uuid.UUID | None) -> ChainVerification:
    """Walk a project's ledger and confirm the hash chain is unbroken.

    Detects three distinct failures: a recomputed hash that no longer matches
    the stored one (an entry was edited), a link that does not point at its
    predecessor (an entry was removed or reordered), and a gap in the sequence.
    """
    events = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.project_id == project_id)
                .order_by(AuditEvent.sequence)
            )
        )
        .scalars()
        .all()
    )

    expected_prev = GENESIS_HASH
    for index, event in enumerate(events, start=1):
        if event.sequence != index:
            return ChainVerification(
                intact=False,
                entries_checked=index - 1,
                broken_at=event.sequence,
                reason=f"sequence gap: expected {index}, found {event.sequence}",
            )

        if event.prev_hash != expected_prev:
            return ChainVerification(
                intact=False,
                entries_checked=index - 1,
                broken_at=event.sequence,
                reason="broken link: prev_hash does not match predecessor",
            )

        recomputed = AuditEvent.compute_hash(
            prev_hash=event.prev_hash,
            sequence=event.sequence,
            occurred_at=event.occurred_at,
            event_type=event.event_type,
            actor=event.actor,
            payload=event.payload,
        )
        if recomputed != event.entry_hash:
            return ChainVerification(
                intact=False,
                entries_checked=index - 1,
                broken_at=event.sequence,
                reason="content altered: recomputed hash differs from stored hash",
            )

        expected_prev = event.entry_hash

    return ChainVerification(intact=True, entries_checked=len(events))


async def chain_length(session: AsyncSession, project_id: uuid.UUID | None) -> int:
    """Number of entries recorded for a project."""
    return (
        await session.execute(
            select(func.count(AuditEvent.id)).where(AuditEvent.project_id == project_id)
        )
    ).scalar_one()


def _lock_key(project_id: uuid.UUID | None) -> int:
    """Map a project to a stable 32-bit advisory-lock key."""
    if project_id is None:
        return 0
    # Signed 32-bit range, as required by the two-argument advisory lock form.
    return (project_id.int % (2**31 - 1)) or 1


__all__ = ["ChainVerification", "chain_length", "record", "verify_chain"]
