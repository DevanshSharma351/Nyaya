# Nyaya

**Agentic requirements engineering, compliance mapping and SDLC selection for regulated financial software.**

Nyaya (न्याय) is the Indian school of logic concerned with *pramāṇa* — the valid
means of acquiring knowledge, and what counts as admissible evidence for a claim.
That is the governing constraint of this system: every requirement, every
regulatory mapping and every lifecycle recommendation it produces must be traceable
to an approved source, scored for confidence, and approved by an accountable human.

---

## Problem

Requirements engineering in financial institutions is manual, slow, and prone to
ambiguity, inconsistency and regulatory omission. Requirements arrive as
unstructured natural language from customers, business teams, compliance officers,
security teams, regulators, policy documents and legacy systems. The cost of getting
it wrong is incorrect scope, compliance gaps, and expensive rework.

Nyaya applies a multi-agent LLM system to elicit, extract, analyse, and validate
those requirements — then recommends and instantiates an appropriate SDLC model.

## Scope

**Primary domain:** Digital customer onboarding and eKYC for a retail bank.
Chosen because its regulatory corpus (RBI Master Direction on KYC, FATF
Recommendations, GDPR, DPDP Act 2023, PMLA) is public and *clause-numbered*, which
makes span-level citation and a measurable citation-correctness metric possible.

**Secondary domain (generalization test):** Loan origination and credit assessment.

## What makes this more than an LLM wrapper

| | |
|---|---|
| **Benchmarked** | Retrieval is measured on a labelled clause set before any agent depends on it; requirement classification will be evaluated against public gold-standard datasets (PROMISE NFR, PURE), not only self-authored demos. |
| **Calibrated confidence** | Confidence is a fusion of retrieval score, NLI entailment, self-consistency and rule-validator outcome — not model self-report. Reported with a reliability diagram and Expected Calibration Error. |
| **Deterministic validation** | Every LLM compliance claim is checked by a non-LLM validator: the cited clause must exist verbatim in the versioned KB, must entail the control, and mandatory-control coverage must be complete. |
| **Regulatory change impact** | Amending a clause walks the traceability graph and reports exactly which requirements, controls and tests are now stale. |
| **SDLC by MCDA** | AHP-derived criterion weights (with consistency-ratio check) + TOPSIS ranking. The LLM writes the justification; the mathematics produces the ranking. |
| **Audit ledger** | Hash-chained, append-only record of every prompt, retrieval, decision, edit and approval. |
| **Adversarial hardening** | Prompt-injection defence via retrieval-source allowlisting and untrusted-content fencing, demonstrated against a poisoned policy document. |

## Architecture

A stateful graph, not a swarm. Deterministic logic sits wherever determinism is
possible, which is what makes the outputs reproducible and auditable.

| Node | Type |
|---|---|
| Orchestrator | Deterministic (graph + checkpointing) |
| Ingestion & PII shield | Deterministic |
| Elicitation | LLM |
| Extraction & structuring | LLM (schema-forced) |
| Quality analysis | Hybrid (lexicon/EARS linters, then LLM for semantic ambiguity) |
| Conflict & duplication | Hybrid (embedding clustering → NLI contradiction → LLM adjudication) |
| Compliance & security mapping | RAG + deterministic rule validator |
| Risk & SDLC engine | Deterministic MCDA + LLM justification |
| Artifact generation | Templated + LLM |
| Human-in-the-loop gate | Deterministic (graph interrupt) |

## Stack

- **Backend** — Python 3.12, FastAPI, Pydantic
- **Orchestration** — LangGraph (chosen for explicit state, checkpointing and *interrupts*, which are the human-approval primitive)
- **Datastore** — PostgreSQL 17 + pgvector, single database for both relational requirements and embeddings
- **Retrieval** — dense (pgvector, bge-m3) then cross-encoder reranking. Lexical `tsvector` search and RRF fusion are implemented but **off by default**: fusion measured *worse* than dense alone on the labelled set (see ADR-0004)
- **Models** — provider-agnostic; local Ollama by default, free-tier Gemini/Groq optional, Claude drop-in
- **Privacy** — Microsoft Presidio detection/masking with a reversible token vault
- **Frontend** — Next.js, TypeScript, Tailwind, shadcn/ui, React Flow
- **Auth** — Keycloak (OIDC, RBAC, MFA)
- **Observability** — Langfuse, structlog

## Getting started

```bash
cp .env.example .env
docker compose up -d postgres minio
uv sync --extra dev
uv run nyaya --help
```

## Layout

```
nyaya/
  config.py        role-based model routing; all tunables
  core/            domain models, audit ledger, confidence fusion
  db/              SQLAlchemy models, migrations
  llm/             provider abstraction (ollama, gemini, groq, anthropic)
  ingestion/       document parsing, clause chunking, PII shield
  retrieval/       hybrid search, reranking, NLI entailment
  agents/          LangGraph nodes
  rules/           YAML rule DSL + deterministic evaluator
  mcda/            AHP + TOPSIS SDLC engine
  api/             FastAPI routers
  eval/            benchmark harness, ablation study, calibration
rules/             versioned compliance and SDLC rule definitions
knowledge_base/    regulatory corpus (raw + clause-chunked)
web/               Next.js frontend
```

## Status

Early development. See `docs/` for the architecture record and scope definition.
