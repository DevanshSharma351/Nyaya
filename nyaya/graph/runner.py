"""Workflow execution runner with durable LangGraph checkpointing and gate orchestration."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Command
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nyaya.agents.compliance import ComplianceResult, ValidatedMapping
from nyaya.agents.extraction import AnalysedRequirement, RequirementDefect
from nyaya.agents.schemas import ExtractedRequirement

if TYPE_CHECKING:
    from nyaya.api.schemas import (
        WorkflowStatusOut,
    )
from nyaya.config import get_settings
from nyaya.core import ledger
from nyaya.core.confidence import Confidence, ConfidenceComponents
from nyaya.core.enums import (
    ApprovalStatus,
    DefectType,
    EvidenceRelation,
    Priority,
    RequirementCategory,
    RiskLevel,
    Severity,
    StakeholderRole,
)
from nyaya.db.models import Approval, Requirement
from nyaya.graph.gates import GATES, authorise
from nyaya.graph.persistence import project_open_questions
from nyaya.graph.state import initial_state
from nyaya.graph.workflow import WorkflowContext, build_graph
from nyaya.ingestion.pii import redact_intake
from nyaya.llm import Usage
from nyaya.mcda.ahp import AHPResult
from nyaya.mcda.sdlc import SDLCRecommendation
from nyaya.mcda.topsis import Ranking, TOPSISResult
from nyaya.retrieval.hybrid import Retrieved
from nyaya.retrieval.obligation import ObligationTier
from nyaya.rules.dsl import Condition, Control
from nyaya.rules.engine import ControlCoverage, CoverageReport

CHECKPOINT_TYPES = (
    AnalysedRequirement,
    ExtractedRequirement,
    RequirementDefect,
    DefectType,
    Severity,
    Priority,
    RequirementCategory,
    RiskLevel,
    ComplianceResult,
    ValidatedMapping,
    EvidenceRelation,
    ObligationTier,
    Retrieved,
    Confidence,
    ConfidenceComponents,
    Usage,
    CoverageReport,
    ControlCoverage,
    Control,
    Condition,
    SDLCRecommendation,
    AHPResult,
    TOPSISResult,
    Ranking,
)


class WorkflowConflictError(ValueError):
    """The request does not match the current workflow state."""


class WorkflowRunner:
    """Singleton runner managing compiled LangGraph app and checkpointer."""

    def __init__(self, checkpointer: Any) -> None:
        self.checkpointer = checkpointer
        self.app = build_graph(checkpointer=self.checkpointer)

    def _config(self, project_id: uuid.UUID) -> dict[str, Any]:
        return {"configurable": {"thread_id": str(project_id)}}

    async def start(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        source_text: str | None = None,
        domain: str = "ekyc_onboarding",
        jurisdictions: list[str] | None = None,
        stakeholder_role: str | None = None,
    ) -> WorkflowStatusOut:
        """Start or re-run the workflow for a project."""
        config = self._config(project_id)
        snapshot = await self.app.aget_state(config)
        if snapshot.next:
            raise WorkflowConflictError("This project already has a workflow in progress.")

        # Check if project has persisted requirements to reuse
        db_requirements = (
            (
                await session.execute(
                    select(Requirement)
                    .where(
                        Requirement.project_id == project_id,
                        Requirement.approval_status != ApprovalStatus.SUPERSEDED,
                    )
                    .options(
                        selectinload(Requirement.defects),
                        selectinload(Requirement.source_utterance),
                    )
                    .order_by(Requirement.ref)
                )
            )
            .scalars()
            .all()
        )

        existing_reqs: list[AnalysedRequirement] = []
        if db_requirements:
            for req in db_requirements:
                existing_reqs.append(
                    AnalysedRequirement(
                        requirement=ExtractedRequirement(
                            statement=req.statement,
                            rationale=req.business_justification or "",
                            categories=list(req.categories),
                            priority=req.priority,
                            risk_level=req.risk_level,
                            acceptance_criteria=list(req.acceptance_criteria),
                            assumptions=list(req.assumptions),
                            quoted_source=req.source_utterance.masked_text or ""
                            if req.source_utterance
                            else "",
                        ),
                        defects=[
                            RequirementDefect(
                                defect_type=d.defect_type,
                                severity=d.severity,
                                detail=d.detail,
                                detector=d.detector,
                                span_start=d.span_start,
                                span_end=d.span_end,
                            )
                            for d in req.defects
                        ],
                        persisted_id=req.id,
                        persisted_updated_at=req.updated_at,
                    )
                )

        text = redact_intake(
            source_text or (db_requirements[0].statement if db_requirements else "")
        )
        state = initial_state(
            project_id=str(project_id),
            source_text=text,
            domain=domain,
            jurisdictions=jurisdictions or ["IN"],
            stakeholder_role=stakeholder_role,
        )
        if existing_reqs:
            state["requirements"] = existing_reqs
            state["unclear"] = await project_open_questions(session, project_id)

        # Execute graph until interrupted or complete
        result = await self.app.ainvoke(state, config, context=WorkflowContext(session))
        return await self._format_status(session, project_id, result)

    async def get_status(self, session: AsyncSession, project_id: uuid.UUID) -> WorkflowStatusOut:
        """Query current execution state and pending interrupts."""
        config = self._config(project_id)
        snapshot = await self.app.aget_state(config)
        if not snapshot.values:
            from nyaya.api.schemas import WorkflowStatusOut

            return WorkflowStatusOut(
                project_id=project_id,
                status="idle",
                completed=False,
            )
        return await self._format_status(session, project_id, snapshot.values)

    async def decide(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        gate_name: str,
        decision: str,
        actor: str,
        role: StakeholderRole,
        comment: str = "",
        expected_run_id: uuid.UUID | None = None,
    ) -> WorkflowStatusOut:
        """Submit an authorized human approval or rejection to resume execution."""
        # 1. Enforce authorization
        authorise(gate_name, role)
        config = self._config(project_id)
        snapshot = await self.app.aget_state(config)
        active_gates = {
            item.value.get("gate")
            for task in snapshot.tasks
            for item in task.interrupts
            if isinstance(item.value, dict)
        }
        if gate_name not in active_gates:
            raise WorkflowConflictError("This gate is no longer awaiting a decision.")
        run_id = uuid.UUID(snapshot.values["run_id"])
        if expected_run_id is not None and run_id != expected_run_id:
            raise WorkflowConflictError("This decision is for a previous workflow run.")
        gate = GATES[gate_name]
        if gate_name == "conflict_resolution" and decision == "approve" and not comment.strip():
            raise WorkflowConflictError("Record how the stakeholder conflict was resolved.")
        if decision == "approve":
            expected = {
                item.persisted_id: item.persisted_updated_at
                for item in snapshot.values.get("requirements", [])
                if item.persisted_id is not None
            }
            if expected:
                current = dict(
                    (
                        await session.execute(
                            select(Requirement.id, Requirement.updated_at).where(
                                Requirement.project_id == project_id,
                                Requirement.approval_status != ApprovalStatus.SUPERSEDED,
                            )
                        )
                    )
                    .tuples()
                    .all()
                )
                if current != expected:
                    raise WorkflowConflictError(
                        "Requirements changed during review. Reject this run and start a new review."
                    )

        # 2. Record approval in DB
        approval_status = (
            ApprovalStatus.APPROVED if decision == "approve" else ApprovalStatus.REJECTED
        )
        pending = (
            (
                await session.execute(
                    select(Approval).where(
                        Approval.project_id == project_id,
                        Approval.subject_id == run_id,
                        Approval.gate == gate_name,
                        Approval.status == ApprovalStatus.PENDING_REVIEW,
                    )
                )
            )
            .scalars()
            .all()
        )
        existing = next(
            (a for a in pending if not gate.all_roles_required or a.required_role == role.value),
            None,
        )
        if gate.all_roles_required and existing is None:
            raise WorkflowConflictError("This role has already submitted its decision.")

        if existing is not None:
            existing.required_role = role.value
            existing.status = approval_status
            existing.decided_by = actor
            existing.decided_at = datetime.now(UTC)
            existing.comment = comment
        else:
            approval = Approval(
                project_id=project_id,
                subject_kind="workflow_run",
                subject_id=run_id,
                gate=gate_name,
                required_role=role.value,
                status=approval_status,
                decided_by=actor,
                decided_at=datetime.now(UTC),
                comment=comment,
            )
            session.add(approval)

        # 3. Log to tamper-evident audit ledger
        await ledger.record(
            session,
            project_id=project_id,
            event_type="approval",
            actor=actor,
            actor_kind="human",
            payload={
                "gate": gate_name,
                "run_id": str(run_id),
                "decision": decision,
                "role": role.value,
                "comment": comment,
            },
        )
        await session.flush()
        if gate.all_roles_required:
            remaining = [a for a in pending if a is not existing]
            if decision == "approve" and remaining:
                return await self._format_status(session, project_id, snapshot.values)
            for approval in remaining:
                approval.status = ApprovalStatus.SUPERSEDED

        # 4. Resume LangGraph execution
        result = await self.app.ainvoke(
            Command(
                resume={
                    "decision": decision,
                    "actor": actor,
                    "comment": comment,
                }
            ),
            config,
            context=WorkflowContext(session),
        )
        return await self._format_status(session, project_id, result)

    async def _format_status(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        values_or_res: dict[str, Any],
    ) -> WorkflowStatusOut:
        from nyaya.api.schemas import WorkflowDecisionOut, WorkflowStatusOut

        config = self._config(project_id)
        snapshot = await self.app.aget_state(config)
        values = snapshot.values or values_or_res

        interrupt_payload: dict[str, Any] | None = None
        current_gate: str | None = None

        # Inspect if currently paused at an interrupt
        if snapshot.tasks:
            for task in snapshot.tasks:
                if task.interrupts:
                    interrupt_payload = task.interrupts[0].value
                    current_gate = (
                        interrupt_payload.get("gate")
                        if isinstance(interrupt_payload, dict)
                        else None
                    )
                    break
        elif values_or_res.get("__interrupt__"):
            interrupt_payload = values_or_res["__interrupt__"][0].value
            current_gate = (
                interrupt_payload.get("gate") if isinstance(interrupt_payload, dict) else None
            )

        # Record pending Approval record in DB if awaiting a gate
        if current_gate is not None:
            run_id = uuid.UUID(values["run_id"])
            gate = GATES[current_gate]
            recorded = (
                (
                    await session.execute(
                        select(Approval).where(
                            Approval.project_id == project_id,
                            Approval.subject_id == run_id,
                            Approval.gate == current_gate,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if gate.all_roles_required:
                roles = {r.value for r in gate.required_roles}
                missing = sorted(roles - {a.required_role for a in recorded})
                approved = {
                    a.required_role for a in recorded if a.status == ApprovalStatus.APPROVED
                }
                if interrupt_payload is not None:
                    interrupt_payload = {
                        **interrupt_payload,
                        "required_roles": sorted(roles - approved),
                        "summary": {
                            **interrupt_payload.get("summary", {}),
                            "approved_roles": sorted(approved),
                        },
                    }
            else:
                missing = [] if recorded else ["any_eligible_role"]
            for role_name in missing:
                session.add(
                    Approval(
                        project_id=project_id,
                        subject_kind="workflow_run",
                        subject_id=run_id,
                        gate=current_gate,
                        required_role=role_name,
                        status=ApprovalStatus.PENDING_REVIEW,
                    )
                )
            if missing:
                await session.flush()

        halted = bool(values.get("halted", False))
        halt_reason = str(values.get("halt_reason", ""))

        completed = not snapshot.next and not interrupt_payload and not halted

        status_str = (
            "halted"
            if halted
            else "waiting_approval"
            if current_gate
            else "completed"
            if completed
            else "running"
        )

        decisions_out = [
            WorkflowDecisionOut(
                gate=d.get("gate", ""),
                decision=d.get("decision", ""),
                actor=d.get("actor", ""),
                comment=d.get("comment", ""),
                at=d.get("at", ""),
            )
            for d in values.get("decisions", [])
        ]

        sdlc = values.get("sdlc")
        sdlc_top = None
        if sdlc is not None:
            ranked = sdlc.ranked()
            if ranked:
                sdlc_top = (
                    ranked[0][0].value if hasattr(ranked[0][0], "value") else str(ranked[0][0])
                )

        coverage_list = values.get("coverage", [])
        coverage_packs = [c.pack for c in coverage_list] if coverage_list else []

        return WorkflowStatusOut(
            project_id=project_id,
            run_id=values.get("run_id"),
            status=status_str,
            current_node=snapshot.next[0] if snapshot.next else None,
            current_gate=current_gate,
            gate_payload=interrupt_payload,
            halted=halted,
            halt_reason=halt_reason,
            decisions=decisions_out,
            requirement_count=len(values.get("requirements", [])),
            compliance_count=len(values.get("compliance", [])),
            coverage_packs=coverage_packs,
            sdlc_recommended=sdlc_top,
            completed=completed,
        )


@asynccontextmanager
async def postgres_workflow_runner() -> AsyncIterator[WorkflowRunner]:
    """Open the app's durable checkpoint store for the lifetime of the API."""
    serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
    async with AsyncConnectionPool(
        get_settings().sync_database_url,
        min_size=1,
        max_size=4,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    ) as pool:
        await pool.wait(timeout=10)
        # Concurrent index creation requires autocommit. Serialize setup across
        # workers with a session lock on the same connection as the migrations.
        async with pool.connection() as connection:
            await connection.execute("SET statement_timeout = '20s'")
            try:
                await connection.execute("SELECT pg_advisory_lock(2144752001, 0)")
                try:
                    await AsyncPostgresSaver(connection, serde=serde).setup()
                finally:
                    await connection.execute("SELECT pg_advisory_unlock(2144752001, 0)")
            finally:
                await connection.execute("RESET statement_timeout")
        yield WorkflowRunner(AsyncPostgresSaver(pool, serde=serde))
