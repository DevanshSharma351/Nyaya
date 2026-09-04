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
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    // `fetch` rejects only on network-level failure; anything the server
    // answered - including a 500 - resolves and is handled below.
    throw new ApiUnreachableError();
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

export type ExtractResult = {
  model: string;
  repair_rounds: number;
  testable_fraction: number;
  unclear: string[];
  requirements: ExtractedRequirement[];
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

export type SDLCFromBrief = {
  recommendation: SDLC;
  factors: Record<string, number>;
  observations: string[];
  requirements_extracted: number;
  unclear: string[];
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
  knowledgeGraph: () => request<Graph>("/graph/demo/knowledge"),
};
