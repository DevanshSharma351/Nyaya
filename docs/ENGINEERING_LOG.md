# Nyaya — Engineering Log

A running record of **what was built, and why**. Entries are append-only and
dated. Where a decision had a plausible alternative, the alternative and the
reason for rejecting it are recorded, so that the reasoning can be audited later
rather than reconstructed from memory.

This document is the narrative counterpart to `docs/adr/`, which holds the
formal single-decision records.

---

## 2026-09-04 — Session 1: Problem framing and foundation

### Starting point

The brief (`Problem Statement.docx`) specifies an agentic LLM system for
requirements engineering in the financial sector: 20 numbered sections, a
13-agent architecture, a regulatory knowledge base, and 12 evaluation metrics.

**First judgement call: the brief is a specification of ambition, not a build
order.** Implementing all 13 agents shallowly — one prompt each — produces a
system that demos as an LLM wrapper and cannot be evaluated meaningfully. The
brief itself points the other way in §18: *"Begin with one financial use case."*

The chosen strategy is therefore **depth in one vertical slice, with a real
evaluation harness**, rather than breadth across all named capabilities.

### Decision 1 — Primary domain: digital onboarding / eKYC

| Considered | Outcome |
|---|---|
| **eKYC / customer onboarding** | **Selected** |
| Loan origination | Retained as the *secondary* domain, used only to test generalization |
| Payments / UPI | Rejected |
| Fraud detection | Rejected |

Reasoning:

1. **The corpus is clause-numbered.** RBI Master Direction on KYC, FATF
   Recommendations, GDPR, DPDP Act 2023 and PMLA rules are public *and*
   structured as numbered clauses. This is the decisive factor: span-level
   citation and a measurable citation-correctness metric are only possible when
   the source has stable, addressable units. PCI-DSS (payments) is licensed and
   less cleanly addressable.
2. **Stakeholder conflict is genuine, not synthetic.** Growth wants minimal
   signup friction; compliance wants document verification; security wants
   liveness detection and device binding; operations wants manual review queues.
   The conflict-detection agent has real contradictions to find.
3. **PII is intrinsic.** Identity documents and biometrics mean the masking
   layer is load-bearing rather than decorative.
4. **The SDLC answer is non-obvious.** Heavily regulated *and* subject to
   frequent UX change — exactly the case where a single-label recommendation is
   wrong and a ranked one is informative.

### Decision 2 — Seven differentiators over a baseline LLM wrapper

Recorded here because they define what "finished" means:

1. **Benchmark against public gold sets** (PROMISE NFR, PURE), not only
   self-authored demos. Highest-leverage single item: it makes results
   comparable to published literature.
2. **Calibrated confidence** — fused from retrieval score, NLI entailment,
   self-consistency across *k* samples, and rule-validator outcome. *Not* model
   self-report, which is known to be poorly calibrated. Reported as a reliability
   diagram and Expected Calibration Error.
3. **Deterministic validator behind every LLM compliance claim** — the cited
   clause must exist verbatim in the versioned KB, must entail the control, and
   mandatory-control coverage must be complete.
4. **Regulatory-change impact analysis** — amending a clause walks the
   traceability graph and reports which requirements are now stale.
5. **SDLC selection by MCDA** — AHP weights (with consistency-ratio check) plus
   TOPSIS ranking. The mathematics ranks; the LLM only explains.
6. **Hash-chained append-only audit ledger.**
7. **Adversarial hardening** — prompt-injection defence demonstrated against a
   poisoned policy document.

Plus an **ablation study** (no-RAG / RAG / RAG+validator; single-agent /
multi-agent) to show the architecture earns its complexity.

### Decision 3 — Collapse 13 agents into 9 nodes

The brief's 13 agents are a *taxonomy*, not a design. Several are a single
prompt; several should not be LLMs at all. The system is modelled as a stateful
graph with typed state and explicit interrupt points.

**Governing principle: determinism wherever determinism is possible.** Quality
linting, conflict clustering, MCDA ranking and approval gating are deterministic;
the LLM is used only where judgement is genuinely required. This is what makes
outputs reproducible, cheap, and auditable — and is itself a finding worth
reporting.

### Decision 4 — Technology stack

| Layer | Choice | Why this and not the obvious alternative |
|---|---|---|
| Orchestration | **LangGraph** | Not CrewAI/AutoGen. Those optimise for autonomous agent-to-agent negotiation, which is a *liability* in a regulated, auditable workflow. LangGraph gives an explicit state machine with checkpointing and **interrupts** — interrupts are precisely the human-approval primitive the brief demands, and the checkpoint history supplies much of the audit trail for free. |
| Datastore | **PostgreSQL 17 + pgvector**, single DB | Not a separate Qdrant/Chroma. One store gives transactional consistency between a requirement row and its evidence rows, one backup and access-control story, and is what a bank would actually approve. |
| Retrieval | Dense (pgvector) + lexical (`tsvector`) fused by **Reciprocal Rank Fusion**, then cross-encoder rerank | On clause-structured legal text, hybrid + rerank is a large and *measurable* precision gain over naive dense retrieval. Citation precision is a headline metric, so this is not premature optimisation. |
| Rule engine | **YAML DSL + own evaluator** | Not Drools. Rules live in git, are diffable and versioned, and the explanation trace is fully controlled. Better auditability story than a black box, at ~300 lines. |
| Backend | FastAPI + Pydantic | Pydantic models double as the schema-forcing contract for LLM structured output. |
| Privacy | Microsoft Presidio + reversible token vault | Masking happens *before* egress; rehydration only after approval. |
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui + React Flow | React Flow for the traceability graph. |
| Auth | Keycloak (OIDC, RBAC, MFA) | Realistic for the domain; cheap in Docker. |

### Decision 5 — Model strategy: hybrid, zero-cost, provider-agnostic

Constraint from the user: **no paid API for now, possibly later.**
Hardware: Apple M3 Pro, 18 GB unified memory, 11 cores.

Resolution — assign models to a **role**, never to a vendor:

| Role | Default | Rationale |
|---|---|---|
| `embedding` | `ollama:bge-m3` (1.2 GB, 1024-dim) | Local, no egress, free. Verified working. |
| `fast` | `ollama:llama3.1:8b` | High-volume classification and routing. |
| `reasoning` | `ollama:qwen3:8b` | Fits comfortably in 18 GB alongside Docker. |

Hosted free tiers (**Gemini** primary — its very large context suits long
regulatory PDFs; **Groq** fallback) and **Claude** are implemented but unused by
default. Switching is a one-line `.env` change, because `ModelRole` →
`ModelSpec` resolution happens in `nyaya/config.py` and agents never name a
vendor.

**Deliberate consequence:** the eval harness can swap models between arms of an
ablation without touching agent code, which is what makes a model-comparison
study cheap to run.

### Decision 6 — Project name

Originally scaffolded as `aegis` (a codename chosen without consultation).
Renamed to **Nyaya** (न्याय) at the user's direction — the Indian school of logic
concerned with *pramāṇa*, the valid means of acquiring knowledge and what counts
as admissible evidence for a claim. This is an unusually exact fit: the system's
central mechanism is evidence-grounded claims carrying citations and calibrated
confidence. Renamed while the cost was 3 files rather than 40.

### Built in this session

- Repository layout, `uv`-managed environment pinned to **Python 3.12**
  (the machine's system Python is 3.14, which is ahead of PyTorch and
  sentence-transformers wheel availability).
- `docker-compose.yml`: Postgres 17 + pgvector, MinIO, Keycloak (behind a
  `full` profile so the default `up` stays light).
- `nyaya/config.py` — role-based model routing; every tunable sourced from env.
- `nyaya/llm/` — provider-agnostic interface plus adapters for Ollama, Gemini,
  Groq, Anthropic, and a deterministic `echo` double for tests and the eval
  control arm.
- `nyaya/core/enums.py` — closed controlled vocabularies (13 requirement
  categories, 7 SDLC models, 10 defect types). Closed sets are what make
  downstream aggregation and metrics well-defined.

**Verified, not assumed:**
- pgvector 0.8.6, pg_trgm, uuid-ossp all live; `default_text_search_config` set
  to `english` so generated `tsvector` columns resolve identically everywhere.
- All three model roles reachable; `bge-m3` returns 1024-dim vectors;
  schema-constrained decoding genuinely enforces the Pydantic shape (verified by
  round-tripping a `Requirement` model through Ollama's `format` parameter).
- `ruff check` clean.

### Incident — home directory is a git repository

`/Users/devanshsharma/.git` exists with zero commits, making the entire home
folder a repo. A `git add -A` issued from the project directory therefore
targeted all of `~` and hung.

- **Effect:** cleared 22 stale index entries for `~/github/OS-Project/` — files
  already deleted from disk before this session. That directory no longer exists.
- **Recoverability:** 136 loose objects (~9.7 MB) remain in `~/.git/objects`,
  reachable via `git fsck --lost-found`. Nothing was in history; that repo has no
  commits.
- **Fix applied:** the project was given its own repository, isolated from `~`.
- **Outstanding, for the user to decide:** whether to delete `~/.git`. Left in
  place deliberately — removing it is destructive and is the repository owner's decision.
  Recommended, since an accidental `git add -A` there could stage SSH and cloud
  credentials.

### Next

1. SQLAlchemy models + Alembic migration: requirements, evidence, clauses,
   traceability edges, audit ledger.
2. Ingestion pipeline with clause-aware chunking and the PII shield.
3. **The retrieval spine, evaluated in isolation before any agent exists** —
   everything downstream inherits its ceiling, so it is measured first.

---

### Finding — schema constraints hold, prompt quality does not (yet)

First end-to-end extraction test through `qwen3:8b`, converting a compliance
officer's spoken statement into a structured requirement:

**What worked.** Enum constraints are genuinely enforced. The model selected
`categories = [regulatory, data_management]` and `priority = must` — both correct,
both drawn from the closed vocabulary, with no post-hoc parsing or repair.
Constrained decoding via Ollama's `format` parameter is doing real work.

**What did not.** The `statement` field echoed the stakeholder's raw sentence
verbatim instead of being rewritten as a testable *shall* statement. The field
description alone (`"A single testable 'shall' statement"`) is insufficient
instruction.

*Implication:* the extraction agent needs few-shot exemplars and an explicit
**EARS** template rather than relying on Pydantic field descriptions. This is a
prompt-design problem, not an infrastructure one — recorded now so the eval
baseline is honest about where the initial weakness sits.

**Second observation — latency.** The call took **37.9 s / 849 tokens**.
`qwen3` is a reasoning model and emits a thinking trace; the inline `/no_think`
directive did not suppress it. At ~38 s per requirement this is too slow for
batch extraction over a document set.

Options, to be measured rather than guessed:
1. Route extraction to the `fast` role (`llama3.1:8b`) and reserve `reasoning`
   for conflict adjudication and compliance mapping, where the deliberation is
   worth paying for.
2. Suppress thinking correctly (Ollama `think: false` rather than an in-prompt
   directive).
3. Batch and parallelise, accepting per-item latency.

This is exactly the kind of trade-off the role-based routing abstraction exists
to make cheap to explore: changing which model serves extraction is a config
edit, and the eval harness can measure both arms.

---

## 2026-09-04 — Session 1 (continued): Persistence layer

### Housekeeping — repository

Project moved to its own repository at `github.com/DevanshSharma351/Nyaya`,
isolated from the stray repo at `~`. Commit history carries no assistant
attribution, at the owner's direction.

*Note on a distinction that came up:* references to `anthropic` in
`nyaya/llm/providers/`, `config.py` and `.env.example` are **vendor references
for a working provider adapter**, in the same category as the Gemini and Groq
adapters — not authorship attribution. They are functional code and were left
in place. Removing them would delete a supported provider.

### Decision 7 — Schema design

17 tables. Four choices are load-bearing enough to record:

**Clause-level knowledge base, versioned by supersession.** The retrievable
unit is a `Clause` with a `citation_key` (`RBI-MD-KYC:16(a)`), a character span
into its parent document, and a hierarchy pointer. Documents are never mutated;
an amended regulation becomes a new `SourceDocument` row and the old one is
marked superseded. *Rationale:* regulatory-change impact analysis needs to
distinguish "cited the old version" from "cited the current version", which
in-place mutation would erase. A `content_hash` on each document detects silent
substitution of a source.

**Requirements version by supersession, not mutation.** Once a requirement is
APPROVED it is an immutable baseline; a change writes a new row pointing back
via `supersedes_id`. *Rationale:* audit requires that the baseline as it stood
on any past date be reconstructible. In-place updates destroy that.

**Evidence carries a *verified* relation, not an asserted one.** The `relation`
field (`supports` / `contradicts` / `neutral`) is set by the NLI model, not by
the agent that produced the citation. `cited_key` is stored verbatim even when it
resolves to nothing, because an unresolvable citation is itself a finding.
`resolved` records whether the key matched a real clause. *This is the schema-level
expression of the project's central claim: the model proposes, the validator
disposes.*

**Traceability as an untyped edge table.** `TraceLink` uses `(kind, uuid)` pairs
rather than a foreign key per entity type, so one table spans utterance →
requirement → clause → control → test case without a join table per pair. This
is the structure the regulatory-change impact walk traverses.

Also recorded: `confidence_components` is stored alongside `confidence` so a low
score can be explained and each component's calibration measured separately;
`ControlMapping.proposed_by` separates LLM-proposed mappings from rule-derived
ones, and `validator_passed` records the deterministic verdict — the gap between
the two is a headline evaluation metric.

### Verified — the audit ledger's tamper-evidence claim

The ledger is hash-chained: each entry commits to its predecessor's hash.
Appends are serialised per project with a **transaction-scoped advisory lock**
(`pg_advisory_xact_lock`) rather than a table lock, so two concurrent writers
cannot fork the chain while unrelated projects never block each other.

Five tests pass, and the two that matter attack the chain the way a real
adversary would — **raw SQL that bypasses the ORM entirely**, since the threat
model is someone with database access rewriting history:

| Test | Attack | Detected as |
|---|---|---|
| `test_altered_payload_is_detected` | `UPDATE` an earlier entry's payload | `content altered` at seq 2 |
| `test_deleted_entry_is_detected` | `DELETE` an entry mid-chain | `sequence gap` at seq 4 |

A third test pins JSON canonicalisation (sorted keys), without which the same
event could hash differently on two occasions and make verification flaky.

*This claim is now evidence, not assertion.* It was worth testing precisely
because "we have an audit log" is cheap to say and rarely true under adversarial
conditions.

### Schema verified against the live database

Not assumed — built with `create_all` against the running Postgres and
introspected:

- 17 tables created
- **HNSW** index live on `clause.embedding` (cosine ops, `m=16`,
  `ef_construction=64`) — chosen over IVFFlat for better recall-at-latency at
  this corpus size and because it needs no training step
- **GIN** indexes on `clause.search_vector` and `requirement.categories`
- `clause.search_vector` confirmed as a **generated** column — computed by
  Postgres, so it cannot drift out of sync with `text` the way an
  application-maintained column would

### Environment fix

`greenlet` added explicitly. SQLAlchemy's async bridge requires it but does not
pull it in on arm64, and the failure surfaces only at first connection — worth
pinning rather than rediscovering on another machine.

### Testing policy

Integration tests run against **the real Postgres**, not SQLite. The schema
depends on pgvector, generated `tsvector` columns, GIN/HNSW indexes and advisory
locks — none of which SQLite can emulate. A test passing against a substitute
engine would not be evidence about the engine that actually runs.
