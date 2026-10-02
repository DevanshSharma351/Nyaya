"""Workflow execution runner with durable LangGraph checkpointing and gate orchestration."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nyaya.agents.extraction import AnalysedRequirement
from nyaya.agents.schemas import ExtractedRequirement

if TYPE_CHECKING:
    from nyaya.api.schemas import (
        WorkflowStatusOut,
    )
from nyaya.core import ledger
from nyaya.core.enums import ApprovalStatus, StakeholderRole
from nyaya.db.models import Approval, Requirement
from nyaya.graph.gates import GATES, authorise
from nyaya.graph.state import initial_state
from nyaya.graph.workflow import build_graph


class WorkflowRunner:
    """Singleton runner managing compiled LangGraph app and checkpointer."""

    def __init__(self, checkpointer: Any | None = None) -> None:
        self.checkpointer = checkpointer or MemorySaver()
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

        # Check if project has persisted requirements to reuse
        db_requirements = (
            await session.execute(
                select(Requirement)
                .where(Requirement.project_id == project_id)
                .options(selectinload(Requirement.defects))
            )
        ).scalars().all()

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
                            quoted_source="",
                        ),
                        defects=[],
                        ears_pattern="ubiquitous",
                    )
                )

        text = source_text or (db_requirements[0].statement if db_requirements else "")
        state = initial_state(
            project_id=str(project_id),
            source_text=text,
            domain=domain,
            jurisdictions=jurisdictions or ["IN"],
            stakeholder_role=stakeholder_role,
        )
        if existing_reqs:
            state["requirements"] = existing_reqs

        # Execute graph until interrupted or complete
        result = await self.app.ainvoke(state, config)
        return await self._format_status(session, project_id, result)

    async def get_status(
        self, session: AsyncSession, project_id: uuid.UUID
    ) -> WorkflowStatusOut:
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
    ) -> WorkflowStatusOut:
        """Submit an authorized human approval or rejection to resume execution."""
        # 1. Enforce authorization
        authorise(gate_name, role)

        # 2. Record approval in DB
        approval_status = (
            ApprovalStatus.APPROVED if decision == "approve" else ApprovalStatus.REJECTED
        )
        existing = (
            await session.execute(
                select(Approval).where(
                    Approval.project_id == project_id,
                    Approval.gate == gate_name,
                    Approval.status == ApprovalStatus.PENDING_REVIEW,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.status = approval_status
            existing.decided_by = actor
            existing.decided_at = datetime.now(UTC)
            existing.comment = comment
        else:
            approval = Approval(
                project_id=project_id,
                subject_kind="project",
                subject_id=project_id,
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
                "decision": decision,
                "role": role.value,
                "comment": comment,
            },
        )
        await session.flush()

        # 4. Resume LangGraph execution
        config = self._config(project_id)
        result = await self.app.ainvoke(
            Command(
                resume={
                    "decision": decision,
                    "actor": actor,
                    "comment": comment,
                }
            ),
            config,
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
                interrupt_payload.get("gate")
                if isinstance(interrupt_payload, dict)
                else None
            )

        # Record pending Approval record in DB if awaiting a gate
        if current_gate is not None:
            existing = (
                await session.execute(
                    select(Approval).where(
                        Approval.project_id == project_id,
                        Approval.gate == current_gate,
                        Approval.status == ApprovalStatus.PENDING_REVIEW,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                gate_spec = GATES.get(current_gate)
                roles = (
                    ", ".join([r.value for r in gate_spec.required_roles])
                    if gate_spec
                    else "any"
                )
                session.add(
                    Approval(
                        project_id=project_id,
                        subject_kind="project",
                        subject_id=project_id,
                        gate=current_gate,
                        required_role=roles,
                        status=ApprovalStatus.PENDING_REVIEW,
                    )
                )
                await session.flush()

        halted = bool(values.get("halted", False))
        halt_reason = str(values.get("halt_reason", ""))
        completed = not bool(snapshot.next) and not bool(interrupt_payload) and not halted

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
                    ranked[0][0].value
                    if hasattr(ranked[0][0], "value")
                    else str(ranked[0][0])
                )

        coverage_list = values.get("coverage", [])
        coverage_packs = [c.pack for c in coverage_list] if coverage_list else []

        return WorkflowStatusOut(
            project_id=project_id,
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


_runner_instance: WorkflowRunner | None = None


def get_workflow_runner() -> WorkflowRunner:
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = WorkflowRunner()
    return _runner_instance


__all__ = ["WorkflowRunner", "get_workflow_runner"]
