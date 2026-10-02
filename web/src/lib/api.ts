/**
 * Typed client for the Nyaya API.
 *
 * Every call goes through `request`, so a failure surfaces as a thrown error
 * with the server's message rather than a silent `undefined` that renders as an
 * empty panel. In a compliance tool an empty panel and "we could not check" are
 * very different statements, and the interface must never confuse them.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

/**
 * How long a single request may take before the client gives up.
 *
 * Extraction runs an 8B model locally and legitimately takes two to three
 * minutes on a long brief, so this is generous. It exists because the
 * alternative is unbounded: a request with no deadline leaves a spinner turning
 * forever with nothing to tell the reader, which is exactly how a slow model
 * becomes indistinguishable from a broken one.
 *
 * Longer than the server's own model timeout, so a slow generation surfaces as
 * the server's explanation rather than as a bare client abort.
 */
const TIMEOUT_MS = 300_000;

/** The request was abandoned before the server answered. */
export class ApiTimeoutError extends Error {
  constructor() {
    super("The request took too long and was abandoned");
    this.name = "ApiTimeoutError";
  }
}

/**
 * The API could not be reached at all.
 *
 * Distinguished from every other failure because it is the only one the reader
 * can act on, and because the browser gives it the least useful message in
 * existence: a connection refused, a DNS failure and a rejected CORS origin all
 * surface identically as "Failed to fetch". Reported as an error message on
 * six modules at once, that reads as the application being broken, when the
 * actual state is almost always that the backend is not running.
 */
export class ApiUnreachableError extends Error {
  readonly base = BASE;
  constructor() {
    super(`Could not reach the API at ${BASE}`);
    this.name = "ApiUnreachableError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (error) {
    // `fetch` rejects on network-level failure and on abort. The two need
    // different messages: one means start the backend, the other means the
    // backend is there and thinking.
    if ((error as Error).name === "AbortError") throw new ApiTimeoutError();
    throw new ApiUnreachableError();
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status}: ${detail.slice(0, 300)}`);
  }
  return response.json() as Promise<T>;
}

export type Health = {
  status: string;
  database: boolean;
  models: Record<string, boolean>;
  corpus_clauses: number;
};

export type Clause = {
  citation_key: string;
  text: string;
  heading: string | null;
  document_code: string;
  jurisdiction: string;
  relevance: number | null;
};

export type SourceDocument = {
  short_code: string;
  title: string;
  issuer: string;
  jurisdiction: string;
  /** The version currently in force. */
  version: string;
  /** Every version held, in order. Two or more means change impact can run. */
  versions: string[];
  effective_from: string | null;
  clauses: number;
};

export type Defect = {
  type: string;
  severity: string;
  detail: string;
  detector: string;
};

export type ExtractedRequirement = {
  statement: string;
  rationale: string;
  categories: string[];
  priority: string;
  risk_level: string;
  acceptance_criteria: string[];
  assumptions: string[];
  quoted_source: string;
  ears_pattern: string;
  is_testable: boolean;
  defects: Defect[];
};

export type UsageInfo = {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
};

export type LLMCallEvent = {
  occurred_at: string;
  actor: string;
  agent: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  repair_rounds: number;
};

export type AgentUsage = {
  agent: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
};

export type ModelUsage = {
  model: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
};

export type ProjectUsage = {
  project_id: string;
  total_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  by_agent: AgentUsage[];
  by_model: ModelUsage[];
  events: LLMCallEvent[];
};

export type ExtractResult = {
  /** The persisted project ID — pass to downstream generate endpoints. */
  project_id: string;
  model: string;
  repair_rounds: number;
  /** What the run could not do. Empty on a clean run. */
  notes: string[];
  testable_fraction: number;
  unclear: string[];
  requirements: ExtractedRequirement[];
  usage?: UsageInfo;
};

export type ControlCoverage = {
  control_id: string;
  title: string;
  severity: string;
  citations: string[];
  satisfied_by: string[];
  is_gap: boolean;
};

export type Coverage = {
  pack: string;
  pack_version: string;
  coverage_ratio: number;
  controls: ControlCoverage[];
  blocking_gaps: string[];
};

export type SDLCRank = {
  model: string;
  percentage: number;
  closeness: number;
  drivers: Record<string, number>;
};

export type Clarification = { question: string; answer: string };

export type UserStory = {
  ref: string;
  text: string;
  role: string;
  trigger: string | null;
  acceptance_criteria: string[];
};

export type UseCase = {
  ref: string;
  name: string;
  actor: string;
  precondition: string;
  main_flow: string[];
  postcondition: string;
  exceptions: string[];
};

export type TraceRow = {
  ref: string;
  statement: string;
  source_quote: string;
  citations: string[];
  controls: string[];
  verification: string[];
  approval_status: string;
  confidence: number | null;
  gaps: string[];
};

export type RiskEntry = {
  ref: string;
  description: string;
  category: string;
  level: string;
  score: number;
  treatment: string;
  owner: string;
};

export type Artefacts = {
  project: string;
  generated_at: string;
  user_stories: UserStory[];
  use_cases: UseCase[];
  traceability: TraceRow[];
  traceability_coverage: number;
  risks: RiskEntry[];
  open_issues: string[];
  assumptions: string[];
};

export type Activity = {
  name: string;
  role: string;
  because: string | null;
  security: boolean;
  compliance: boolean;
};

export type Phase = {
  name: string;
  purpose: string;
  entry_criteria: string[];
  exit_criteria: string[];
  activities: Activity[];
  deliverables: string[];
  roles: string[];
  gate: string | null;
};

export type Workflow = {
  model: string;
  cadence: string;
  phases: Phase[];
  traceability: string[];
  notes: string[];
};

export type SDLCFromBrief = {
  project_id: string;
  recommendation: SDLC;
  factors: Record<string, number>;
  observations: string[];
  requirements_extracted: number;
  unclear: string[];
  workflow: Workflow;
  is_stale?: boolean;
};

export type Project = {
  id: string;
  name: string;
  description?: string;
  domain: string;
  status: string;
  created_at: string;
  requirement_count: number;
};

export type SDLC = {
  recommended: string;
  ranked: SDLCRank[];
  close_call: boolean;
  consistency_ratio: number;
  notes: string[];
  explanation: string[];
};

export type Affected = {
  ref: string;
  statement: string;
  severity: string;
  citation_key: string;
  detail: string;
};

export type Impact = {
  summary: string;
  changed_clauses: string[];
  removed_clauses: string[];
  added_clauses: string[];
  affected: Affected[];
};

export type GraphNode = {
  id: string;
  kind: "requirement" | "clause" | "control" | "document";
  label: string;
  detail: string;
  status: string;
  weight: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  relation: string;
  strength: number;
};

export type Graph = { nodes: GraphNode[]; edges: GraphEdge[] };

export const api = {
  health: () => request<Health>("/health"),
  documents: () => request<SourceDocument[]>("/knowledge/documents"),
  search: (query: string, top_k = 8) =>
    request<Clause[]>("/knowledge/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k }),
    }),
  extract: (text: string, clarifications: Clarification[] = []) =>
    request<ExtractResult>("/analysis/extract", {
      method: "POST",
      body: JSON.stringify({ text, clarifications }),
    }),
  coverage: (text: string) =>
    request<Coverage[]>("/analysis/coverage", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  sdlcFromBrief: (text: string, clarifications: Clarification[] = []) =>
    request<SDLCFromBrief>("/analysis/sdlc/from-brief", {
      method: "POST",
      body: JSON.stringify({ text, clarifications }),
    }),
  sdlc: (overrides: Record<string, number>) =>
    request<SDLC>("/analysis/sdlc", {
      method: "POST",
      body: JSON.stringify({ overrides }),
    }),
  clause: (key: string) =>
    request<Clause>(`/knowledge/clause/${encodeURIComponent(key)}`),
  impact: (short_code: string, from_version: string, to_version: string) =>
    request<Impact>("/analysis/impact", {
      method: "POST",
      body: JSON.stringify({ short_code, from_version, to_version }),
    }),
  artefacts: (text: string, clarifications: Clarification[] = []) =>
    request<Artefacts>("/analysis/artefacts", {
      method: "POST",
      body: JSON.stringify({ text, clarifications }),
    }),
  workflow: (model: string, observations: Record<string, number | boolean> = {}) =>
    request<Workflow>("/analysis/sdlc/workflow", {
      method: "POST",
      body: JSON.stringify({ model, ...observations }),
    }),
  knowledgeGraph: () => request<Graph>("/graph/demo/knowledge"),
  projects: () => request<Project[]>("/projects"),
  projectSdlc: (id: string) => request<SDLCFromBrief>(`/projects/${encodeURIComponent(id)}/sdlc`),

  // Project-based generate endpoints — zero LLM calls, instant results
  generateArtefacts: (projectId: string) =>
    request<Artefacts>(`/projects/${encodeURIComponent(projectId)}/artefacts/generate`, {
      method: "POST",
    }),
  generateSdlc: (projectId: string) =>
    request<SDLCFromBrief>(`/projects/${encodeURIComponent(projectId)}/sdlc/generate`, {
      method: "POST",
    }),
  generateCoverage: (projectId: string) =>
    request<Coverage[]>(`/projects/${encodeURIComponent(projectId)}/coverage/generate`, {
      method: "POST",
    }),
  projectUsage: (projectId: string) =>
    request<ProjectUsage>(`/projects/${encodeURIComponent(projectId)}/usage`),
  updateRequirement: (
    projectId: string,
    reqId: string,
    patch: {
      statement?: string;
      priority?: string;
      risk_level?: string;
      categories?: string[];
      acceptance_criteria?: string[];
      business_justification?: string;
    },
  ) =>
    request<ExtractedRequirement>(
      `/projects/${encodeURIComponent(projectId)}/requirements/${encodeURIComponent(reqId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(patch),
      },
    ),

  // LangGraph Multi-Agent Workflow & Human Approval Gates
  workflowGates: () => request<GateSpec[]>("/projects/workflow/gates"),
  startWorkflow: (projectId: string, payload: WorkflowStartPayload = {}) =>
    request<WorkflowStatus>(`/projects/${encodeURIComponent(projectId)}/workflow/start`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getWorkflowStatus: (projectId: string) =>
    request<WorkflowStatus>(`/projects/${encodeURIComponent(projectId)}/workflow/status`),
  decideWorkflowGate: (projectId: string, decision: GateDecision) =>
    request<WorkflowStatus>(`/projects/${encodeURIComponent(projectId)}/workflow/decide`, {
      method: "POST",
      body: JSON.stringify(decision),
    }),
  listWorkflowApprovals: (projectId: string) =>
    request<Approval[]>(`/projects/${encodeURIComponent(projectId)}/workflow/approvals`),
};

export type GateSpec = {
  name: string;
  description: string;
  required_roles: string[];
  blocking: boolean;
};

export type GateDecision = {
  gate: string;
  decision: "approve" | "reject";
  actor: string;
  role: string;
  comment?: string;
};

export type Approval = {
  id: string;
  project_id: string;
  gate: string;
  required_role: string;
  status: "pending_review" | "approved" | "rejected" | "superseded";
  decided_by: string | null;
  decided_at: string | null;
  comment: string | null;
  created_at: string;
};

export type WorkflowDecision = {
  gate: string;
  decision: string;
  actor: string;
  comment: string;
  at: string;
};

export type WorkflowStatus = {
  project_id: string;
  status: "idle" | "running" | "waiting_approval" | "halted" | "completed";
  current_node: string | null;
  current_gate: string | null;
  gate_payload: {
    gate: string;
    description: string;
    required_roles: string[];
    summary: Record<string, any>;
  } | null;
  halted: boolean;
  halt_reason: string;
  decisions: WorkflowDecision[];
  requirement_count: number;
  compliance_count: number;
  coverage_packs: string[];
  sdlc_recommended: string | null;
  completed: boolean;
};

export type WorkflowStartPayload = {
  source_text?: string;
  domain?: string;
  jurisdictions?: string[];
  stakeholder_role?: string;
};

