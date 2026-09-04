/**
 * Typed client for the Nyaya API.
 *
 * Every call goes through `request`, so a failure surfaces as a thrown error
 * with the server's message rather than a silent `undefined` that renders as an
 * empty panel. In a compliance tool an empty panel and "we could not check" are
 * very different statements, and the interface must never confuse them.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
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
  version: string;
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

export type SDLC = {
  recommended: string;
  ranked: SDLCRank[];
  close_call: boolean;
  consistency_ratio: number;
  notes: string[];
  explanation: string[];
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
  extract: (text: string) =>
    request<ExtractResult>("/analysis/extract", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  coverage: (text: string) =>
    request<Coverage[]>("/analysis/coverage", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  sdlc: (overrides: Record<string, number>) =>
    request<SDLC>("/analysis/sdlc", {
      method: "POST",
      body: JSON.stringify({ overrides }),
    }),
  knowledgeGraph: () => request<Graph>("/graph/demo/knowledge"),
};
