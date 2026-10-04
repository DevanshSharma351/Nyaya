"use client";

/**
 * Workflow & Governance — Human-in-the-Loop Gate Orchestration.
 *
 * Implements Layer 7 (Orchestration) and Layer 8 (Governance & Safety).
 * Shows the durable LangGraph state machine execution, active human approval
 * gates with role-based competence enforcement, and tamper-evident audit trail.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Lock,
  Play,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { ProjectSelector } from "@/components/chrome/ProjectSelector";
import { Badge, Button, Empty, Failure } from "@/components/ui";
import {
  api,
  type Approval,
  type GateSpec,
  type Project,
  type WorkflowStatus,
} from "@/lib/api";

const PIPELINE_NODES = [
  { id: "extract", label: "Extraction Agent", layer: "Layer 5", type: "agent" },
  { id: "baseline_gate", label: "Requirement Baseline", layer: "Human Gate 1", type: "gate" },
  { id: "map_compliance", label: "Compliance Agent", layer: "Layer 5", type: "agent" },
  { id: "interpretation_gate", label: "Regulatory Interpretation", layer: "Human Gate 2", type: "gate" },
  { id: "assess_coverage", label: "Coverage Engine", layer: "Layer 4", type: "rule" },
  { id: "gap_gate", label: "Compliance Gap", layer: "Human Gate 3", type: "gate" },
  { id: "recommend_sdlc", label: "SDLC AHP/TOPSIS", layer: "Layer 4", type: "mcda" },
  { id: "sdlc_gate", label: "SDLC Selection", layer: "Human Gate 4", type: "gate" },
  { id: "persist", label: "Persist & Traceability", layer: "Layer 6", type: "persist" },
];

export default function WorkflowPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [gates, setGates] = useState<GateSpec[]>([]);
  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Decision Form State
  const [actor, setActor] = useState("compliance.officer@bank.example");
  const [selectedRole, setSelectedRole] = useState<string>("");
  const [comment, setComment] = useState("");

  const selectedProject = useMemo(
    () => projects.find((p) => p.id === projectId) ?? null,
    [projects, projectId]
  );

  // Load gate specifications and projects once on mount
  useEffect(() => {
    let cancelled = false;
    api.workflowGates().then((g) => {
      if (!cancelled) setGates(g);
    }).catch(() => {});

    api.projects().then((list) => {
      if (cancelled) return;
      setProjects(list);
      const savedId = typeof window !== "undefined" ? sessionStorage.getItem("nyaya_project_id") : null;
      if (savedId && list.some((p) => p.id === savedId)) {
        setProjectId(savedId);
      } else if (list.length > 0) {
        setProjectId(list[0].id);
      }
    }).catch(() => {});

    return () => {
      cancelled = true;
    };
  }, []);

  // Load workflow status and approvals for selected project
  const refreshStatus = useCallback(async (id: string) => {
    if (!id) {
      setStatus(null);
      setApprovals([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [st, apprs] = await Promise.all([
        api.getWorkflowStatus(id),
        api.listWorkflowApprovals(id),
      ]);
      setStatus(st);
      setApprovals(apprs);

      // Pre-select competent role if waiting for a gate
      if (st.gate_payload?.required_roles?.length) {
        setSelectedRole(st.gate_payload.required_roles[0]);
      }
    } catch (err: unknown) {
      setStatus(null);
      setApprovals([]);
      setError((err as Error)?.message || "Failed to load workflow state");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (projectId) {
      queueMicrotask(() => {
        if (!cancelled) {
          void refreshStatus(projectId);
        }
      });
    } else {
      queueMicrotask(() => {
        if (!cancelled) {
          setStatus(null);
          setApprovals([]);
        }
      });
    }
    return () => {
      cancelled = true;
    };
  }, [projectId, refreshStatus]);

  // Start / re-run workflow
  const handleStartWorkflow = async () => {
    if (!projectId) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await api.startWorkflow(projectId);
      setStatus(res);
      await refreshStatus(projectId);
    } catch (err: unknown) {
      setError((err as Error)?.message || "Failed to start workflow");
    } finally {
      setActionLoading(false);
    }
  };

  // Submit gate approval / rejection
  const handleGateDecision = async (decision: "approve" | "reject") => {
    if (!projectId || !status?.current_gate) return;
    if (!selectedRole) {
      setError("Please select a stakeholder role with authority for this gate.");
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const res = await api.decideWorkflowGate(projectId, {
        gate: status.current_gate,
        decision,
        actor: actor.trim() || "anonymous@bank.example",
        role: selectedRole,
        comment: comment.trim(),
      });
      setStatus(res);
      setComment("");
      await refreshStatus(projectId);
    } catch (err: unknown) {
      setError((err as Error)?.message || "Decision rejected by gate authorization");
    } finally {
      setActionLoading(false);
    }
  };

  // Compute node status in pipeline
  const getNodeState = (nodeId: string) => {
    if (!status) return "pending";
    if (status.status === "halted") {
      if (status.current_gate === nodeId) return "halted";
      return "pending";
    }
    if (status.completed) return "completed";
    if (status.current_gate === nodeId) return "active";

    // Mark previous nodes as completed based on decisions history
    const decidedGates = status.decisions.map((d) => d.gate);
    if (nodeId === "extract" && (decidedGates.length > 0 || status.requirement_count > 0)) {
      return "completed";
    }
    if (nodeId === "baseline_gate" && decidedGates.includes("requirement_baseline")) {
      return "completed";
    }
    if (nodeId === "map_compliance" && (decidedGates.includes("regulatory_interpretation") || status.compliance_count > 0)) {
      return "completed";
    }
    if (nodeId === "interpretation_gate" && decidedGates.includes("regulatory_interpretation")) {
      return "completed";
    }
    if (nodeId === "assess_coverage" && (decidedGates.includes("compliance_gap") || status.coverage_packs.length > 0)) {
      return "completed";
    }
    if (nodeId === "gap_gate" && decidedGates.includes("compliance_gap")) {
      return "completed";
    }
    if (nodeId === "recommend_sdlc" && (decidedGates.includes("sdlc_selection") || status.sdlc_recommended)) {
      return "completed";
    }
    if (nodeId === "sdlc_gate" && decidedGates.includes("sdlc_selection")) {
      return "completed";
    }
    if (nodeId === "persist" && (status.completed || decidedGates.includes("sdlc_selection"))) {
      return "completed";
    }

    return "pending";
  };

  const getTone = (st: string) => {
    if (st === "completed" || st === "approved") return "var(--confirmed)";
    if (st === "waiting_approval" || st === "pending_review") return "var(--review)";
    if (st === "halted" || st === "rejected") return "var(--gap)";
    return "var(--text-secondary)";
  };

  return (
    <ModuleShell
      eyebrow="Layer 7 & 8 · Orchestration & Governance"
      title="Workflow & Human Gates"
      lede="Execution order is explicit, every transition is checkpointed, and human-approval gates are durable interrupt points that suspend execution until authorized stakeholders clear them."
      pathname="/workflow"
    >
      {/* Unified Project Selector Bar */}
      <Block>
        <ProjectSelector
          activeModule="workflow"
          currentProjectId={projectId}
          onSelectProject={(id) => {
            setProjectId(id);
            sessionStorage.setItem("nyaya_project_id", id);
            refreshStatus(id);
          }}
        />
      </Block>

      {/* Workflow Controls Bar */}
      <Block>
        <div className="glass-raised p-4 rounded-xl flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="caption font-medium text-[var(--text-secondary)]">Workflow Execution Status:</span>
            {status ? (
              <Badge tone={getTone(status.status)}>
                {status.status.replace("_", " ").toUpperCase()}
              </Badge>
            ) : (
              <Badge tone="var(--text-tertiary)">IDLE</Badge>
            )}
            {status?.current_gate && (
              <span className="caption font-semibold" style={{ color: "var(--review)" }}>
                Waiting at Gate: {status.current_gate.replace(/_/g, " ")}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {projectId && (
              <Button
                variant="quiet"
                onClick={() => refreshStatus(projectId)}
                disabled={loading || actionLoading}
              >
                <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
                Refresh
              </Button>
            )}
            {projectId && (
              <Button
                variant="primary"
                onClick={handleStartWorkflow}
                disabled={actionLoading}
              >
                <Play size={14} />
                {status && status.status !== "idle" ? "Re-run Workflow" : "Launch Workflow"}
              </Button>
            )}
          </div>
        </div>
      </Block>

      {error && <Failure message={error} />}

      {!projectId ? (
        <Empty>
          No Project Selected. Run an extraction in the Requirements module first or select an existing project above to run the LangGraph approval workflow.
        </Empty>
      ) : (
        <>
          {/* Pipeline Visual Flow */}
          <Block>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
              <div className="text-sm font-medium text-[var(--text)]">8-Layer Orchestration Pipeline</div>
              {selectedProject && (
                <div className="caption text-[var(--text-tertiary)]">
                  Project: {selectedProject.name} • {gates.length > 0 ? `${gates.length} Gates Registered` : "7 Gates Active"}
                </div>
              )}
            </div>
            <p className="caption mb-4 text-[var(--text-secondary)]">
              Explicit StateGraph execution with durable checkpoints. Execution suspends automatically at human-approval gates until a verified stakeholder role clears it.
            </p>

            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
              {PIPELINE_NODES.map((node) => {
                const nodeState = getNodeState(node.id);
                const isGate = node.type === "gate";
                return (
                  <div
                    key={node.id}
                    className={`relative flex flex-col justify-between rounded-xl border p-3 transition-all ${
                      nodeState === "active"
                        ? "border-amber-500/60 bg-amber-500/10 shadow-[0_0_15px_rgba(245,158,11,0.15)] ring-1 ring-amber-500/40"
                        : nodeState === "completed"
                          ? "border-emerald-500/40 bg-emerald-500/5 text-[var(--text)]"
                          : nodeState === "halted"
                            ? "border-rose-500/60 bg-rose-500/10 text-rose-300"
                            : "border-[var(--hairline)] bg-[var(--surface-subtle)] opacity-70"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                        {node.layer}
                      </span>
                      {nodeState === "completed" ? (
                        <CheckCircle2 size={14} className="text-emerald-400" />
                      ) : nodeState === "active" ? (
                        <Clock size={14} className="animate-spin text-amber-400" />
                      ) : nodeState === "halted" ? (
                        <XCircle size={14} className="text-rose-400" />
                      ) : isGate ? (
                        <Lock size={12} className="text-[var(--text-tertiary)]" />
                      ) : null}
                    </div>

                    <div className="my-2">
                      <div className="text-sm font-semibold text-[var(--text)]">
                        {node.label}
                      </div>
                      <div className="mt-0.5 text-[11px] capitalize text-[var(--text-secondary)]">
                        {node.type}
                      </div>
                    </div>

                    <div className="text-[10px] font-medium">
                      {nodeState === "active" ? (
                        <span className="text-amber-400">Suspended / Awaiting Decision</span>
                      ) : nodeState === "completed" ? (
                        <span className="text-emerald-400">Passed</span>
                      ) : nodeState === "halted" ? (
                        <span className="text-rose-400">Halted / Rejected</span>
                      ) : (
                        <span className="text-[var(--text-tertiary)]">Pending</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Block>

          {/* Active Gate Decision Interface */}
          {status?.status === "waiting_approval" && status.gate_payload && (
            <Block>
              <div className="text-sm font-medium mb-3 text-amber-300">
                APPROVAL GATE: {status.gate_payload.gate.replace(/_/g, " ").toUpperCase()}
              </div>
              <div className="rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-transparent p-5">
                <div className="flex flex-col gap-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <h4 className="text-base font-semibold text-[var(--text)]">
                        Mandatory Human Decision Required
                      </h4>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">
                        {status.gate_payload.description}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {status.gate_payload.required_roles.map((role) => (
                        <span
                          key={role}
                          className="rounded bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-300"
                        >
                          Role: {role}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Summary packet details */}
                  {status.gate_payload.summary && (
                    <div className="rounded-lg border border-[var(--hairline)] bg-[var(--surface)] p-3 text-xs">
                      <div className="font-semibold text-[var(--text-secondary)] mb-1">
                        Gate Review Packet:
                      </div>
                      <pre className="max-h-48 overflow-auto font-mono text-[11px] text-[var(--text-secondary)]">
                        {JSON.stringify(status.gate_payload.summary, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Decision submission form */}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <label className="caption text-[var(--text-secondary)]">
                        Acting Stakeholder Role:
                      </label>
                      <select
                        value={selectedRole}
                        onChange={(e) => setSelectedRole(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[var(--hairline)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--focus)]"
                      >
                        <option value="">Select Competent Role...</option>
                        {status.gate_payload.required_roles.map((r) => (
                          <option key={r} value={r}>
                            {r} (Authorized)
                          </option>
                        ))}
                        <option value="developer">developer (Unauthorized)</option>
                        <option value="customer">customer (Unauthorized)</option>
                      </select>
                    </div>

                    <div>
                      <label className="caption text-[var(--text-secondary)]">
                        Reviewer Identity / Email:
                      </label>
                      <input
                        type="text"
                        value={actor}
                        onChange={(e) => setActor(e.target.value)}
                        placeholder="reviewer@bank.example"
                        className="mt-1 w-full rounded-lg border border-[var(--hairline)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--focus)]"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="caption text-[var(--text-secondary)]">
                      Decision Justification / Rationale:
                    </label>
                    <textarea
                      rows={2}
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      placeholder="Verified compliance with Master Directions and banking risk framework..."
                      className="mt-1 w-full rounded-lg border border-[var(--hairline)] bg-[var(--surface)] p-2.5 text-sm text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--focus)]"
                    />
                  </div>

                  {/* Submit buttons */}
                  <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => handleGateDecision("reject")}
                      disabled={actionLoading}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-sm font-medium text-rose-300 hover:bg-rose-500/20 disabled:opacity-50"
                    >
                      <XCircle size={15} />
                      Reject & Halt Pipeline
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGateDecision("approve")}
                      disabled={actionLoading}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                    >
                      <CheckCircle2 size={15} />
                      Approve Gate & Continue
                    </button>
                  </div>
                </div>
              </div>
            </Block>
          )}

          {/* Halted Run Notice */}
          {status?.status === "halted" && (
            <Block>
              <div className="flex items-start gap-3 rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-rose-300">
                <AlertTriangle size={20} className="shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-rose-200">Workflow Halted by Human Decision</h4>
                  <p className="mt-1 text-sm">{status.halt_reason}</p>
                  <p className="mt-2 text-xs text-rose-400">
                    A rejection at an approval gate stops execution permanently for this thread. Requirements remain in DRAFT status. Click &ldquo;Re-run Workflow&rdquo; above to restart when ready.
                  </p>
                </div>
              </div>
            </Block>
          )}

          {/* Completed Run Summary */}
          {status?.completed && (
            <Block>
              <div className="flex items-start gap-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-emerald-300">
                <CheckCircle2 size={20} className="shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-emerald-200">Workflow Fully Completed & Approved</h4>
                  <p className="mt-1 text-sm">
                    All mandatory human gates were satisfied. Requirements have been elevated to APPROVED status, control mappings verified, and traceability links recorded into the immutable ledger.
                  </p>
                  {status.sdlc_recommended && (
                    <p className="mt-2 text-xs text-emerald-400">
                      Recommended SDLC Model: <strong>{status.sdlc_recommended.toUpperCase()}</strong>
                    </p>
                  )}
                </div>
              </div>
            </Block>
          )}

          {/* Approvals History & Audit Ledger */}
          <Block>
            <div className="text-sm font-medium mb-3 text-[var(--text)]">Governance Audit Trail & Gate Decisions</div>
            {approvals.length === 0 ? (
              <Empty>
                No approvals recorded yet. Start the workflow to see human approvals and audit trail events recorded here.
              </Empty>
            ) : (
              <div className="flex flex-col gap-2.5">
                {approvals.map((appr) => (
                  <div
                    key={appr.id}
                    className="flex flex-col justify-between gap-2 rounded-lg border border-[var(--hairline)] bg-[var(--surface)] p-3 text-sm sm:flex-row sm:items-center"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                          appr.status === "approved"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : appr.status === "rejected"
                              ? "bg-rose-500/20 text-rose-400"
                              : "bg-amber-500/20 text-amber-400"
                        }`}
                      >
                        {appr.status === "approved" ? (
                          <CheckCircle2 size={16} />
                        ) : appr.status === "rejected" ? (
                          <XCircle size={16} />
                        ) : (
                          <Clock size={16} />
                        )}
                      </div>
                      <div>
                        <div className="font-medium text-[var(--text)]">
                          {appr.gate.replace(/_/g, " ").toUpperCase()}
                        </div>
                        <div className="caption text-[var(--text-tertiary)]">
                          Required Role: {appr.required_role}
                          {appr.decided_by && ` • Decided by: ${appr.decided_by}`}
                          {appr.comment && ` • "${appr.comment}"`}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 self-end sm:self-center">
                      <Badge tone={getTone(appr.status)}>
                        {appr.status.replace("_", " ").toUpperCase()}
                      </Badge>
                      <span className="caption text-[var(--text-tertiary)]">
                        {new Date(appr.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Block>

          <Rationale>
            <ul className="list-disc pl-4 space-y-1">
              <li>Execution order is deterministic via LangGraph StateGraph, never autonomous swarming.</li>
              <li>Human gates suspend durably at interrupt points; decisions are tamper-evidently logged to the SHA-256 hash-chained ledger.</li>
              <li>Role competence is strictly enforced: an unauthorized role cannot clear a regulatory or security gate.</li>
              <li>Rejections halt the run permanently rather than being advisory or silently ignored.</li>
            </ul>
          </Rationale>
        </>
      )}
    </ModuleShell>
  );
}
