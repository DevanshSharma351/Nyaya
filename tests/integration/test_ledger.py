"""The audit ledger's tamper-evidence claim, tested rather than asserted."""

from __future__ import annotations

from sqlalchemy import text

from nyaya.core import ledger


async def test_chain_is_sequential_and_linked(session, project):
    """Entries increment by one and each links to its predecessor."""
    first = await ledger.record(
        session,
        project_id=project.id,
        event_type="ingestion",
        actor="ingestion_agent",
        payload={"document": "RBI-MD-KYC"},
    )
    second = await ledger.record(
        session,
        project_id=project.id,
        event_type="llm_call",
        actor="extraction_agent",
        payload={"model": "qwen3:8b"},
    )
    await session.commit()

    assert (first.sequence, second.sequence) == (1, 2)
    assert first.prev_hash == "0" * 64  # genesis
    assert second.prev_hash == first.entry_hash  # linked
    assert first.entry_hash != second.entry_hash


async def test_intact_chain_verifies(session, project):
    for i in range(5):
        await ledger.record(
            session,
            project_id=project.id,
            event_type="agent_decision",
            actor="quality_agent",
            payload={"step": i},
        )
    await session.commit()

    result = await ledger.verify_chain(session, project.id)
    assert result.intact is True
    assert result.entries_checked == 5
    assert result.broken_at is None


async def test_altered_payload_is_detected(session, project):
    """Editing a past entry's content must invalidate the chain.

    The update is issued as raw SQL, deliberately bypassing the ORM - this is
    the threat model: someone with database access rewriting history.
    """
    for i in range(4):
        await ledger.record(
            session,
            project_id=project.id,
            event_type="approval",
            actor="compliance_officer",
            actor_kind="human",
            payload={"decision": i},
        )
    await session.commit()
    assert (await ledger.verify_chain(session, project.id)).intact

    await session.execute(
        text(
            "UPDATE audit_event SET payload = '{\"decision\": 999}'::jsonb "
            "WHERE project_id = :pid AND sequence = 2"
        ),
        {"pid": project.id},
    )
    await session.commit()

    result = await ledger.verify_chain(session, project.id)
    assert result.intact is False
    assert result.broken_at == 2
    assert "altered" in (result.reason or "")


async def test_deleted_entry_is_detected(session, project):
    """Removing an entry breaks the sequence and must be caught."""
    for i in range(4):
        await ledger.record(
            session,
            project_id=project.id,
            event_type="retrieval",
            actor="retrieval_agent",
            payload={"query": f"q{i}"},
        )
    await session.commit()

    await session.execute(
        text("DELETE FROM audit_event WHERE project_id = :pid AND sequence = 3"),
        {"pid": project.id},
    )
    await session.commit()

    result = await ledger.verify_chain(session, project.id)
    assert result.intact is False
    assert result.broken_at == 4
    assert "sequence gap" in (result.reason or "")


async def test_hash_is_order_independent_for_payload_keys(session, project):
    """Logically identical payloads must hash identically.

    Guards the JSON canonicalisation: without sorted keys, the same event
    recorded twice could produce different hashes and make verification flaky.
    """
    from datetime import UTC, datetime

    from nyaya.db.models.audit import AuditEvent

    at = datetime.now(UTC)
    common = dict(prev_hash="0" * 64, sequence=1, occurred_at=at, event_type="llm_call", actor="a")

    assert AuditEvent.compute_hash(**common, payload={"a": 1, "b": 2}) == AuditEvent.compute_hash(
        **common, payload={"b": 2, "a": 1}
    )
