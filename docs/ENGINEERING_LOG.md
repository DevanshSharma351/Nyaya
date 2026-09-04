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

---

## 2026-09-04 — Secret-leak prevention

Requirement from the owner: nothing secret reaches `main`.

### Audit of what is already published

| Check | Result |
|---|---|
| `.env` tracked? | No — ignored, never staged |
| Key/PEM/credential files tracked? | None (`.env.example` only) |
| Secret-shaped strings anywhere in **full history**? | None |
| API keys populated in `.env.example`? | All empty |

The only passwords in `.env.example` are local Docker defaults
(`nyaya_dev_pw`, `admin`) — which is what an example file is for, and they grant
nothing beyond a container on `localhost`.

### Guard installed: pre-commit secret scan

Discipline is not a control. `scripts/check_secrets.py` runs from
`.githooks/pre-commit` and **aborts the commit** on a finding.

Design points worth recording:

- **Scans staged content, not the working tree** (`git show :path`), so it sees
  exactly what would be committed — not a file that was cleaned up after staging.
- **Hooks are version-controlled** via `core.hooksPath = .githooks` rather than
  living untracked in `.git/hooks`, so the guard survives a fresh clone
  (`make hooks`).
- **Deliberately biased toward false positives.** A false positive costs one
  allowlist comment; a leaked key that reaches a public remote must be treated
  as compromised and rotated even after the commit is rewritten. The two costs
  are not comparable.

### Two bugs found by testing the scanner rather than trusting it

Written, then attacked with a file of planted credentials. Both defects were
**false negatives** — the failure mode that matters, since a scanner that misses
things is worse than none for giving false assurance.

**1. Password literals slipped through.** The exemption for bare identifiers —
intended to skip an assignment whose value is another *variable*, which leaks
nothing — also swallowed an assignment of a quoted alphanumeric password, because
such a value is itself a syntactically valid identifier.

*Fix:* the exemption now applies only to **unquoted** values. An unquoted value
is a variable reference; a quoted one is a literal, and a literal credential is a
secret however ordinary its characters look.

*Postscript:* the first draft of this very log entry was **blocked by the hook**,
because it quoted the offending example verbatim. The guard works, and the entry
was reworded to describe the pattern rather than reproduce it.

**3. Third refinement — quoted-vs-unquoted, by file type.** The fix above was
still too blunt: it flagged `token = _surrogate(...)` in the PII shield, where
`token` is a pseudonymisation surrogate rather than a credential.

The underlying rule was wrong. *In source code, an unquoted value is an
expression* — `token = build(x)`, `password = settings.pw` — and carries no
secret. A literal credential in code is quoted. **Config formats are the
exception**: in `.env`, `.yaml`, `.ini` and friends, `KEY=value` is unquoted and
is precisely where a live secret lives.

So the unquoted exemption now applies only outside config files. Verified in
four directions: quoted secrets in code caught, unquoted secrets in `.env`
caught, expressions in code ignored, empty and non-credential config ignored.

Three rounds of correction on a ~150-line script is itself the lesson: a
security control that has not been attacked is an assumption, not a control.

**2. Extensionless files were skipped entirely.** The binary filter keyed on file
extension, so `.githooks/pre-commit` — a shell script, exactly the sort of file a
credential gets pasted into — was never scanned.

*Fix:* binaries are now detected by **content** (a NUL byte in the first 8 KB),
not by extension.

Final state, verified in both directions: 6 findings against the planted-secret
file (Google, OpenAI and Anthropic keys, plus three populated credential
variables), and 0 false positives across the real codebase.

### Also added

`Makefile` with `setup`, `hooks`, `up`, `down`, `db-reset`, `test`, `lint`,
`fmt`, `scan`, `check`. `scripts/reset_db.py` **refuses to run unless
`env == "local"`** — dropping every table should not be one typo away in any
environment holding real data.

---

## 2026-09-04 — Ingestion: clause splitting and the PII shield

### Decision 8 — Split regulatory text on its own structure, not by token count

Regulatory text is not prose to be windowed. It is a numbered tree, and **the
numbering is the citation scheme**: `RBI-MD-KYC:16(a)` means something to a
compliance officer in a way `chunk_47` never will.

Three things structural splitting buys that fixed-size chunking cannot:

1. **Citations that resolve.** A generated requirement cites a key; the
   validator resolves that key back to exactly one row. This is the mechanism
   behind the whole citation-correctness metric.
2. **Retrieval units that are semantically whole.** A clause is a complete
   obligation. A 512-token window routinely severs one mid-sentence, so the
   retrieved span no longer states the duty it is cited for.
3. **Interpretive context on demand.** A leaf such as `(a)` often means nothing
   without its parent; the hierarchy lets retrieval walk upward.

Implemented as a tiered marker grammar covering the conventions actually present
in the corpus — `CHAPTER IV`, `Article 32`, `16.`, dotted `8.2.1`, and
parenthesised `(a)` / `(1)` / `(i)`.

Two sub-problems worth recording:

**Ambiguous roman numerals.** `(i)`, `(v)` and `(x)` are valid under both the
alpha and roman patterns. Resolved by legal drafting convention: read as alpha
unless a roman series is already open at that tier.

**Dotted numbering carries its own depth.** `5.1.2` is two levels below `5`, so
its tier is computed from the number itself rather than assigned by pattern.

**Conservative by design:** text that cannot be attributed to a numbered clause
attaches to the enclosing clause, and material before the first clause is kept
as a `preamble` node. Losing regulatory text is the worst failure available
here — a dropped obligation is one the system can never detect a gap against.
There is a test asserting exactly that no source line disappears.

### Bug found by testing — organisational divisions must be transparent to citation

The first implementation produced `RBI-MD-KYC:Chapter IV.16`.

**Nobody cites a chapter.** They cite section 16. Parts and chapters organise a
document without participating in its citation scheme. Fixed by marking those
styles transparent: they still nest in the tree, because retrieval walks upward
for context, but they contribute nothing to the key.

Worth recording because it is the kind of error that looks harmless and is not —
every citation the system emitted would have been unresolvable against how the
source is actually referenced.

10 tests, all passing, written against text shaped like RBI Master Directions,
GDPR articles and PCI-style dotted clauses.

### Decision 9 — PII shield: validated recognisers, stable surrogates

Nothing sensitive reaches a model. Two properties matter more than raw recall:

**Surrogates are stable within a project, and salted per project.** The same
Aadhaar always maps to the same token, so a model can still reason that two
statements concern the same customer without ever seeing the identifier — a
random surrogate per occurrence would destroy that coreference. The per-project
salt means the same individual is not correlatable across engagements, and the
token cannot be brute-forced back to the value without it.

**Detection is checksum-validated wherever the format allows.** Aadhaar carries
a **Verhoeff** check digit (implemented directly — dihedral group D5) and PAN a
positional structure in which the fourth character encodes holder type. Cards
are Luhn-checked.

*Why validation rather than a looser regex:* a bare 12-digit pattern would mask
transaction references, settlement IDs and account numbers. **Over-masking
destroys the very requirement text the system exists to analyse** — the failure
is silent and corrupts every downstream stage. There is a test pinning this:
`Transaction reference 111111111111` must pass through untouched.

Recognisers cover Aadhaar, PAN, IFSC, Indian phone, passport, email, card and
date of birth. Presidio NER is layered on top for names and locations, but is
**optional**: it needs spaCy, and ingestion must not fail outright when the model
is absent, so callers degrade to pattern-only masking.

9 tests passing, including reversibility, cross-project non-correlation, and a
check that masking leaves the surrounding requirement wording intact.

**Suite total: 24 tests, all passing. Lint clean.**

---

## 2026-09-04 — Correctness audit of everything built so far

Deliberate pause to attack the existing code before building on top of it.
Static analysis first, then targeted probes at the places most likely to hide a
defect. **Five real bugs found, all fixed, each pinned by a regression test.**

Notably, the full test suite was green *before* this audit. Passing tests only
demonstrate the absence of the failures you thought to write down.

### Bug 1 — `ModelSpec` was environment-backed (config)

`ModelSpec` inherited `BaseSettings`, so Pydantic treated `provider` and `model`
as environment-sourced fields. `ModelSpec()` was constructible with **no
arguments**, silently populated from stray `PROVIDER` / `MODEL` variables.

*Why it matters:* model routing is the one thing the whole architecture rests on.
A spec that can materialise from ambient environment state, rather than only from
parsed configuration, undermines the guarantee that agents run on the model the
configuration names.

*Fix:* plain `BaseModel`, with `min_length=1` on both fields.

### Bug 2 — empty provider accepted

`ModelSpec.parse(":model")` yielded `provider=""`, which would fail later at
provider lookup with a confusing error rather than at parse time.
*Fix:* reject an empty provider or model half explicitly.

### Bug 3 — the test double could not build the project's own schemas

`EchoProvider` filled required fields from a scalar-type table, so an enum field
received `""` and failed validation. **Nearly every schema in this project
constrains fields to a closed vocabulary**, which made the double useless as a
fixture — and, more seriously, useless as the eval harness's control arm.

*Fix:* a schema walker honouring `$ref`, `$defs`, `enum`, `const`, `anyOf`/`oneOf`
(preferring the non-null branch) and nested objects, with a recursion guard.

### Bug 4 — clause spans overlapped their successors

`char_end` was taken from the current read position, which had already advanced
past the line that closed the clause. Every clause span therefore swallowed the
first line of the next clause, and **sibling spans overlapped**:

```
X:16(a) [64,124)   span = '(a) first sub;\n(b) second sub;\n'
X:16(b) [ 91,152)
```

*Why it matters:* character spans exist so a citation can be highlighted in the
source document. Overlapping spans mean the highlight shows the wrong text —
a citation that appears to support a claim by quoting its neighbour. This is
precisely the failure the evidence architecture is meant to prevent, and it
would have been invisible until someone read a rendered citation carefully.

*Fix:* a clause ends where its successor *begins*; `close_to` now takes the
boundary offset explicitly. Two regression tests: siblings never overlap, and a
parent's span always contains its children's.

### Bug 5 — bare clause markers were unrecognised

The section pattern demanded text on the same line as the number, so `16.` with
its heading on the following line — **common in typeset regulations** — fell
through to the preamble and became uncitable.

*Fix:* the trailing text is now optional.

### Also fixed

- **MinIO healthcheck was invalid.** It called `mc ready local`, but the server
  image ships no `mc` client, so the container could never become healthy and
  anything waiting on it would hang. Now probes the built-in
  `/minio/health/live` endpoint — verified healthy in 11 s.
- **All 4 mypy errors cleared** (`Callable` typing on the PII validators, and
  Gemini's embedding response, which could return `None` and silently yield
  fewer vectors than inputs — now raises instead).

### Verified rather than assumed

- **Ledger concurrency.** 20 concurrent appends from independent sessions:
  0 errors, chain length 20, chain intact. The per-project advisory lock does
  prevent forking under real contention, which was previously only argued.
- **Clause splitter on degenerate input** — empty, whitespace-only, unnumbered,
  marker-only, deeply dotted, out-of-order numbering: none raise.
- **`mask_with_ner`** leaks no detected value into its output.

### Observation for later

Presidio pulled **`en_core_web_lg` (382 MB)** on first use without being asked.
Worth pinning the spaCy model explicitly before this reaches a container image
or a fresh clone.

**State: 44 tests passing, ruff clean, mypy clean across 25 source files.**

### Fourth scanner refinement

The hook blocked this commit on `${KEYCLOAK_ADMIN_PASSWORD:-admin}` in
`docker-compose.yml`. The interpolation exemption was anchored on a closing
brace, but the value capture stops *at* that brace — so `${VAR:-default}` never
matched the exemption. Anchor removed.

That is four corrections to the scanner, every one found by running it rather
than reading it. The pattern is consistent: each fix was a *narrowing* of an
over-broad exemption or a *widening* of an over-narrow one, and none were
visible by inspection.

---

## 2026-09-04 — The retrieval spine, measured before anything depends on it

Commitment made earlier in the project: build retrieval, then **benchmark it in
isolation before writing a single agent**. Every downstream metric is capped by
whether the governing clause was retrieved at all, so measuring it after agents
exist would mean attributing retrieval's ceiling to the agents' behaviour.

That discipline paid for itself immediately — it refuted one of the project's
own architectural assumptions.

### Built

- `parsers.py` — PDF/DOCX/HTML/text extraction. **Deliberately light
  normalisation**: aggressive de-hyphenation or line reflowing risks corrupting
  clause numbering, and a mangled number is a clause that can never be cited.
- `embedder.py` — batching with a hard dimension check. A model swap that
  changes vector width must fail loudly at ingest, not as a confusing insert
  error later.
- `pipeline.py` — parse → split → embed → persist. **Idempotent by content
  hash**; a changed file creates a *new version* rather than mutating the old
  one, because a clause that has already been cited must never change beneath
  the citation.
- `hybrid.py` — dense (pgvector/cosine) and lexical (`ts_rank_cd`) retrieval,
  weighted RRF, jurisdiction and in-force scoping, exact citation resolution.
- `rerank.py` — cross-encoder (bge-reranker-v2-m3), lazily loaded, degrading to
  unreranked retrieval when absent.
- `search.py` — the single entry point agents call. Agents do not choose a
  retrieval strategy; changing it is one edit here plus a re-run of the harness.
- A **34-query labelled set** over 104 clauses from RBI MD-KYC, DPDP 2023 and
  GDPR, plus MRR / Recall / nDCG / Hit@k implemented directly rather than
  imported, so every reported number has a visible definition.

### Bug found by measurement — the lexical arm was inert

First run: lexical MRR **0.046**, with the governing clause outside the top 10
for **22 of 24** queries. Not "weak" — broken.

Cause: `websearch_to_tsquery` (like `plainto_tsquery`) **conjoins** every term.
A fifteen-word stakeholder question demands one clause containing all nine
stemmed terms, and matched **zero rows**. The same terms OR-ed matched 36.

Fix: rewrite the query to a disjunction, letting `ts_rank_cd` do the
discriminating — recall from the OR, precision from density-and-proximity
ranking. Lexical MRR went **0.046 → 0.249**, a 5× improvement.

Worth dwelling on: this component was fully wired, imported cleanly, returned
plausible-looking results, and was contributing *nothing*. No test would have
caught it, because it failed by returning a well-formed empty list. Only a
labelled set with a known right answer exposes this class of defect.

### The assumption that was wrong

The architecture notes claimed hybrid fusion plus reranking would be "a large,
measurable lift over naive dense retrieval". **Half of that was false.**

Combined results (n=34):

| arm | MRR | R@1 | R@5 | nDCG@10 | Hit@5 |
|---|---|---|---|---|---|
| lexical | 0.406 | 0.225 | 0.441 | 0.446 | 0.706 |
| dense | 0.659 | 0.365 | 0.659 | 0.721 | 0.971 |
| hybrid (RRF) | 0.620 | 0.314 | 0.613 | 0.632 | 0.912 |
| **dense + rerank** | **0.737** | **0.400** | **0.672** | **0.743** | **1.000** |
| hybrid + rerank | 0.737 | 0.400 | 0.672 | 0.743 | 1.000 |

1. **Reranking is the real win.** +11.8 % MRR, and **Hit@5 = 1.000** — after
   reranking, a governing clause is in the top five for *every* query in the set.
   That is precisely the number the fixed-size evidence window depends on.
2. **Fusion is not justified here.** Hybrid scored *below* dense alone. And
   `hybrid + rerank` equals `dense + rerank` **to three decimal places** — the
   lexical arm changes nothing after reranking while adding a query and its
   latency.
3. A weight sweep on paraphrase queries was **monotonic** — 0.579 at
   `w_lex = 0` falling to 0.443 at `w_lex = 1.0`, with no interior optimum. There
   was no tuning that rescued it.

### Guarding against a self-serving benchmark

The gold queries were written in lay stakeholder phrasing deliberately, which
**structurally disadvantages lexical retrieval**. Rather than accept a result my
own test design had produced, a second subset of 10 `term_of_art` queries was
added — naming the precise legal category, the case lexical search exists for.

| arm | paraphrase (24) | term_of_art (10) |
|---|---|---|
| lexical | 0.249 | 0.783 |
| dense | 0.579 | 0.850 |
| hybrid | 0.503 | **0.900** |
| dense + rerank | **0.690** | 0.850 |

The arms *are* genuinely complementary — lexical is **3.1× better** on
term-of-art than on paraphrase, and hybrid wins outright on that subset. But
paraphrase queries dominate real requirement elicitation, and dense+rerank wins
decisively there. The subsets are scored separately and kept separate, because a
blended average would have concealed that the two retrievers succeed on disjoint
query types.

### Decision (ADR-0004)

**Default: dense → cross-encoder rerank. Lexical fusion disabled by weight, not
deleted.** Retained because the result is corpus-dependent: 104 clauses flatters
dense retrieval, and lexical methods characteristically hold up better as a
corpus grows and embedding space crowds. The weight is a config knob so
re-enabling costs nothing, and the ADR records the re-measurement triggers
(corpus > ~1,000 clauses, embedding model change, query-mix shift).

### Honest limitations

- **34 queries over 104 clauses is a small benchmark.** These numbers indicate a
  direction; they are not a general claim about hybrid retrieval.
- The relevance judgements are the author's own. A second annotator and an
  inter-annotator agreement figure would materially strengthen this.
- The corpus is *representative* text written to mirror real clause structure
  and terminology, not the verbatim instruments. Structure and vocabulary are
  faithful; exact wording is not.
- Latency is now reranker-dominated: **~1 s/query** versus ~140 ms without.

### Also

- `asyncio_default_*_loop_scope = "session"` — the DB engine and cached LLM
  providers hold connections bound to their creating loop, and a per-test loop
  closed them out from under session-scoped fixtures.
- Two exceptions renamed for the `Error` suffix convention (`N818`).
- README corrected: it still advertised the hybrid claim this work refuted.

**State: 63 tests passing, ruff clean, mypy clean across 36 source files.**

---

## 2026-09-04 — Extraction agent, and a hallucination the repair loop caused

### The problem this had to solve

The earlier measurement showed the model echoing a stakeholder's sentence back
verbatim as a "requirement". That output was well-formed JSON, passed schema
validation, and was useless. **Schema validation checks shape; nothing was
checking whether the content was a requirement at all.**

### Deterministic quality checks, written first

Built before the agent, because they are what tell you whether the agent
improved:

- **`ears.py`** — the EARS grammar (ubiquitous / event-driven / state-driven /
  unwanted / optional / complex). The value is not style enforcement: **a
  statement matching an EARS pattern is structurally testable**, because the
  pattern forces a subject, a modal obligation and an explicit trigger. "The
  system should be secure" matches nothing. Also detects non-binding modals
  (`should`, `may`) and compound requirements, which cannot be separately
  approved, tested or traced.
- **`lexicon.py`** — seven categories of ambiguous language with a named remedy
  each, so feedback is "'appropriate' is unverifiable, state the threshold"
  rather than an unfalsifiable request to be clearer.

These run before any model: free, instant, reproducible, and specific.

**Two false positives found and fixed by testing against well-formed input.** A
linter that fires on good requirements is one reviewers learn to ignore:

1. *Passive voice in a condition clause.* "While a customer **is categorised** as
   high risk, the system shall…" — passive in a trigger describes a state and
   hides no responsible actor. Now exempted inside the leading conditional.
2. *Components of defined terms.* "high risk" is a regulatory category, not a
   vague qualifier; the regulation supplies its meaning. Added a defined-terms
   allowlist covering ~20 such phrases.

Severity was added for the same reason: superlatives like "every high risk
customer" are usually correct once scope is bounded elsewhere, so they are
reported at INFO rather than blocking.

### The agent: model proposes, linters judge, feedback is specific

Few-shot exemplars rather than instructions alone, because exemplars demonstrate
the *transformation* — stakeholder prose in, testable obligation out — which
description had failed to convey. Each exemplar teaches one behaviour: rewrite
rather than echo; split compounds; ask instead of invent.

The repair loop is bounded at two attempts. A requirement that still fails is
kept **with its defects recorded**, not discarded and not silently accepted: a
defective requirement a human can see is worth more than a missing one.

### Verified on held-out inputs, not just the exemplar

The first successful run used an input nearly identical to an exemplar, so it
proved nothing. Three held-out cases were run instead — a security architect on
spoofing, an ops lead on redaction and access logging, and a deliberately vague
product owner.

Results: no echoing, correct and varied EARS patterns (`state_driven`,
`unwanted`, `event_driven`), compounds correctly split (the ops statement became
three separate requirements), and useful clarification questions.

### The finding that mattered: the repair loop induced a fabrication

Given "make onboarding as quick as possible", one repair round produced:

> The system shall limit the onboarding process to no more than **three**
> distinct user actions.

**The stakeholder never said three.** Pressure to eliminate vague language was
satisfied by inventing specificity.

This is worse than the failure it replaced. The vague original is visibly
incomplete; **the fabricated version reads as precise, passes every ambiguity
check, and would be baselined and built.** The mechanism intended to improve
quality manufactured a hallucination — and it is exactly the class of failure
this project exists to prevent.

### Fix — `quantities.py`, a deterministic quantity-provenance guard

Every quantity a requirement asserts must trace to the source text. Comparison is
after normalisation, since a stakeholder writes "five years" and a model writes
"5 years".

Deliberately narrow: quantities are *objectively* present or absent in the
source. Judging invented prose is the LLM reviewer's job; this checks only what
can be checked deterministically.

Two refinements found by testing:

- **Units are separated from their numbers by modifiers.** The first version
  required the unit to follow immediately, so "three **distinct user** actions" —
  the actual fabrication — slipped through. Up to three intervening words are now
  tolerated.
- **Identifiers are not thresholds.** `AES-256`, `ISO 27001` and "section 16"
  name something external rather than asserting a magnitude, and are excluded.

Re-run after the fix, the same input produces:

> The system shall limit the onboarding process to **a defined number** of
> distinct user actions.

with the missing value raised in `unclear`.

**Honest caveat:** the prompt was hardened in the same change, so the observed
improvement cannot be attributed to either alone — this is a confounded fix. The
detector's value is that it is a *guarantee* rather than a hope: if the prompt
fails on some future input, the defect is still caught and recorded.

### Known gaps

- "modern" is not in the ambiguity lexicon and passed the linter. The model
  raised it in `unclear` anyway, which is the right outcome by a different route.
- EARS classification is syntactic. One statement used "If the video session is
  initiated…" where "When" was correct — an ordinary event written as an
  unwanted condition. No pattern matcher can catch that; it needs the semantic
  reviewer.
- Extraction takes **45–100 s** per input on `qwen3:8b`, and a repair round
  roughly doubles it.

**State: 96 tests passing, ruff clean, mypy clean across 44 source files.**

---

## 2026-09-04 — Compliance mapping: the model proposes, the validator disposes

The centrepiece. A requirement is mapped to the regulatory controls it
satisfies, with citations that are **checked rather than trusted**.

The pipeline is deliberately adversarial toward its own model:

1. **Retrieve** candidate clauses, scoped to jurisdiction and to sources in force.
2. **Seed deterministically** — the rule engine proposes which controls a
   requirement appears to satisfy, so the model is asked to *confirm and cite*
   rather than invent from nothing.
3. **The model proposes** a mapping with a citation key and a quotation.
4. **The validator disposes** — the citation must resolve to a real clause, the
   quoted text must actually appear in it, and the clause must entail the
   requirement under NLI.
5. **Confidence is computed** from those independent signals, never reported by
   the model.

The gap between proposed and accepted is a headline metric: it measures directly
how much the grounding machinery is doing.

### Built

- **`nli.py`** — entailment checking. This is what turns "the model says this
  clause supports the requirement" into "the clause was checked and does".
- **`rules/dsl.py` + `rules/engine.py`** — a small declarative rule language and
  its evaluator. Rules live in versioned YAML, not code: diffable, `git blame`-able,
  and readable by the compliance officers accountable for the obligations they
  encode. A control **without a citation is rejected at load time** — an
  unciteable control is an assertion, not an obligation.
- **`rules/compliance/ekyc-in.yaml`** — 21 controls (12 blocker, 9 major), every
  one traced to a clause. `applies_when` and `satisfied_when` are separate,
  because "required here" and "this requirement discharges it" are different
  questions and conflating them hides gaps.
- **`core/confidence.py`** — fusion over four independent signals.
- **`agents/compliance.py`** — the agent.

### The finding that took three fixes: NLI does not transfer to requirements

First end-to-end run: **0 % acceptance on a correct mapping.** The model proposed
the right control with the right citation; the citation resolved; the quote
verified; and the entailment check rejected it at 0.01.

A validator that rejects correct citations is worse than no validator, because it
trains reviewers to override it.

**Fix 1 — the hypothesis was in the wrong register.** MNLI models are trained on
declarative factual pairs. An EARS requirement — "When a customer is onboarded
remotely, the system shall screen…" — reads to such a model as a conditional
prescription about some particular system, not a claim the premise could entail.

Measured on one correct clause-requirement pair:

| hypothesis form | verdict |
|---|---|
| raw EARS | `contradicts` 0.003 |
| "The regulation requires screening…" | `supports` 0.994 |

So requirements are now restated as declarative obligation claims before
checking. **This is necessary, not cosmetic.**

**Fix 2 — the actor must be dropped, decided by measurement.** A requirement
names the software ("the system"); a regulation names the institution ("the
Regulated Entity"). Those subjects differ *by design*, and NLI reads the mismatch
as evidence against entailment. Over matched and mismatched pairs:

| framing | correct (min) | wrong (max) | separation |
|---|---|---|---|
| keep the actor | 0.404 | 0.046 | +0.358 |
| **drop the actor** | **0.769** | 0.043 | **+0.726** |

Dropping it doubles the margin without raising any wrong citation's score. The
result reads ungrammatically ("It is required that screen the customer"), which
does not trouble the model and is never shown to a user. The threshold (0.55)
now sits in a measured gap rather than being guessed.

**Fix 3 — sub-clauses need their parent.** `22(a)` reads "screening shall be
performed prior to activation" and never says *what is screened against* — that
is in the parent. Alone it entailed the requirement at **0.004**; with its
parent, at **0.996**.

The clause splitter's docstring had claimed the hierarchy exists so "retrieval
can walk upward for interpretive context". It was designed for and never
implemented. Now it is: `load_context` walks ancestors level by level, so query
count is bounded by hierarchy depth rather than result count.

**Fix 3a — organisational divisions must be transparent to context too.**
Attaching a chapter prepends a bare title like "SCREENING AND REPORTING" to the
premise, which obliges nothing and dilutes the signal: clause 22 scored
`supports` 0.646 alone and `neutral` 0.427 with its chapter attached. Parts and
chapters were already transparent to *citation* for the same underlying reason;
they are now transparent to context as well.

### Bug found along the way — clause text was duplicated and hard-wrapped

`Clause.display` repeated its own opening sentence: for a sub-clause the splitter
records the remainder of the marker line as `heading`, and that same text also
opens `text`, so concatenating them duplicated it. Source documents are also
hard-wrapped, leaving newlines mid-sentence.

Both wasted tokens and degraded the embedding and the entailment premise. Fixed
in the ingestion pipeline: the heading is recorded only when genuinely distinct,
and clause text is unwrapped.

### After the fixes

| requirement | outcome |
|---|---|
| screening before activation | **2 proposed, 2 accepted**, confidence 0.94 / 0.78 |
| retention of screening evidence | 1 proposed, **rejected** at 0.39 entailment |
| display risk rating to customer | 1 proposed, **rejected**; **conflict detected** |

The second is arguably a *correct* rejection: the cited clause obliges retention
of **identity records from cessation of the relationship**, while the requirement
concerns **screening evidence from the screening date**. Different artefact,
different clock. A compliance officer would make exactly that distinction.

The third is the behaviour the design is for. The model declined to map the
requirement to a control it does not satisfy, *and* reported that displaying a
risk rating would **breach** `RBI-MD-KYC:17(b)`, which prohibits disclosing the
category to the customer. Detecting that a requirement violates a regulation is
worth more than mapping one that complies.

### Honest notes

- Three requirements is an anecdote, not an evaluation. A labelled
  requirement-to-control set is needed before any acceptance-rate number means
  anything, and that is the next measurement to build.
- The 0.55 threshold is set from **one** measured separation on four clause
  pairs. It needs a proper sweep with a precision/recall curve.
- Compliance mapping costs **40–95 s** per requirement locally.
- Confidence weights are reasoned, not fitted. Fitting them requires the
  labelled set above, after which the calibration curve becomes meaningful.

**State: 128 tests passing, ruff clean, mypy clean across 50 source files.**

---

## 2026-09-04 — Measuring the citation validator, and two things it revealed

Built a labelled set of **49 (requirement, clause) judgements** over 12
requirements — 17 genuine citations and 32 wrong ones, of which 31 are
**topically adjacent**: a retention clause cited for a screening duty, the
sibling sub-clause governing a neighbouring obligation. Random negatives would
prove nothing; these are the citations a model actually produces when it errs.

No language model is involved. The labelled citation goes straight to the
validator, isolating the validator's own discriminating power from the
proposing model's accuracy.

### Result — precise, but not sensitive

| threshold | precision | recall | F1 |
|---|---|---|---|
| 0.10 | 0.769 | 0.588 | 0.667 |
| **0.20** | **0.909** | **0.588** | **0.714** |
| 0.55 | 0.909 | 0.588 | 0.714 |
| 0.80 | 0.889 | 0.471 | 0.615 |

The validator rejects almost every wrong citation (1 false accept in 32) and
**rejects 7 of 17 correct ones**. The 0.20–0.55 plateau also shows the previously
guessed 0.55 threshold was not harmful, but was chosen on no evidence.

### Why the false rejections happen — and why reversing direction does not help

The seven failures score near *zero*, not near the threshold. That is not a
tuning problem. Inspecting them shows a pattern:

> clause: "the pseudonymisation and encryption of personal data"
> requirement: "encrypt customer identification documents transmitted over public networks"

**The requirement is more specific than the clause.** A general duty does not
logically entail a particular implementation — though the implementation plainly
*satisfies* the duty. Regulatory compliance is a satisfaction relation, not
logical entailment, and MNLI measures the latter.

The obvious fix — reverse the direction and ask whether the requirement entails
the clause — was tested and **rejected on measurement**: it lifted a wrong
citation (`GDPR:Article 5.1(e)`, 0.012 → 0.634) as much as a right one
(`5.1(c)`, 0.015 → 0.633). It shifts scores without discriminating.

Excluding the preamble from the context chain was also tested, and made no
difference (0.004 → 0.003).

**Conclusion: a general-purpose MNLI model cannot be the sole citation
validator.** That is a limitation of the method, not a bug to be tuned away.

### Design change — objective checks reject, probabilistic checks route to review

The error profile is usable if the architecture stops treating all checks alike.
Validation now has **three outcomes**, not two:

| check | kind | on failure |
|---|---|---|
| citation resolves to a real clause | objective fact | **reject** |
| quotation copied, not composed | objective fact | **reject** |
| clause confidently contradicts | substantive finding | **reject** |
| clause does not confirm entailment | probabilistic judgement | **needs review** |

An unconfirmed citation is *not* discarded. Treating a 0.588-recall signal as
rejection would throw away two in five correct compliance mappings and train
reviewers to override the validator — the failure mode that makes a checker
worse than none.

At the selected threshold:

- **10/17** correct citations auto-confirmed
- **7/17** correct citations routed to a human, not lost
- **1** wrong citation auto-confirmed — the number that actually matters

This also fits the human-in-the-loop design the brief requires, rather than
fighting it.

### Second finding — the confidence score was badly calibrated, and the structure was why

First measurement: **ECE 0.276**. The [0.4, 0.6) band held 38 citations of which
only **18 %** were genuine — confidently wrong exactly where a reviewer would
trust the number.

The cause was structural, not a weighting mistake. A weighted sum let retrieval,
validation and consistency supply a **floor of 0.522 regardless of entailment**,
so a citation whose clause obliged nothing still scored 0.52.

Replaced with a gated form that mirrors what the signals actually mean:

- **validation is a gate** — objective facts; failure means zero.
- **entailment bounds the score** — the only signal testing the claim against its
  cited authority. A citation the clause does not oblige cannot be confident
  however well it was retrieved.
- **retrieval and consistency corroborate** — they modulate within the range
  entailment permits and cannot establish confidence alone.

| | ECE | high-confidence band [0.8,1.0) |
|---|---|---|
| weighted sum | 0.276 | — |
| **gated** | **0.143** | stated 0.907 vs actual 0.889 (gap 0.018) |

ECE roughly halved, and the band that matters most — where auto-confirmation
happens — is now near-perfectly calibrated. The residual error is in the
low-confidence band, which is *under*confident: correct citations the NLI model
scores near zero. That is the recall limitation above, showing up honestly in
the calibration rather than being hidden.

### A methodological note

The earlier calibration figure binned by "was the accept/reject decision
correct". That is a different quantity from the one the score claims, and it
flattered the result: a correctly rejected citation scores low *because* it is
wrong, so counting it as an underconfident success understates miscalibration.
Calibration is now measured against the claim the score actually makes — *this
citation is genuine*.

### Honest limitations

- **49 judgements over 12 requirements** is small, and the labels are the
  author's own. A second annotator and an inter-annotator agreement statistic
  would materially strengthen this; without one, the negatives in particular
  reflect a single reading of what a regulator would accept.
- The single false confirmation (`RBI-MD-KYC:22(c)`, ongoing re-screening cited
  for a pre-activation duty, entailment 0.910) is a genuine miss: the clauses are
  near-identical in wording and differ in *when* the duty applies. Temporal
  scope is precisely what NLI does not model.
- The obvious next step is an LLM judge as a second opinion on the
  `needs_review` band, measured against the same labelled set to see whether it
  recovers recall without importing the fabrication risk the whole design exists
  to contain.

**State: 144 tests passing, ruff clean, mypy clean across 52 source files.**

---

## 2026-09-04 — The SDLC selection engine

The brief asks for a **justified, ranked** lifecycle recommendation, not a
label. This is the piece where the design commitment "the mathematics decides,
the model only explains" is actually cashed out.

An LLM asked directly to pick a lifecycle produces a plausible paragraph that
cannot be re-derived, cannot be challenged on its inputs, and cannot be compared
across projects. Here the factor scores, the weights (with their consistency
ratio) and the arithmetic are all inspectable, so an architect who disagrees can
point at the specific factor score they dispute rather than arguing with prose.

### AHP for the weights

Weights cannot be asserted. "Regulatory criticality matters more than delivery
speed" is defensible; "regulatory criticality has weight 0.23" is not, unless
something derives it.

AHP derives weights from pairwise comparisons, which people make far more
reliably than direct weight assignment — an architect can say regulatory
criticality is *strongly* more important than team familiarity without being
able to put a number on it.

The property that earns AHP its place is the **Consistency Ratio**. If A > B and
B > C but C > A, CR exposes it. Verified: coherent judgements give CR 0.004; a
deliberately cyclic set is rejected at CR 2.381. A hand-assigned weight vector
can never be inconsistent, and therefore can never warn you.

The principal eigenvector is used rather than the row-geometric-mean
approximation, because the eigenvalue it produces is what the consistency
measure is defined on — approximating the weights would leave CR unfounded.

### TOPSIS for the ranking

Produces a graded closeness coefficient rather than a winner, which is what the
brief asks for: a margin of 0.02 and a margin of 0.30 mean very different things
to an architect, and only a graded method shows that. Near-ties are flagged
explicitly as decisions belonging to humans.

Vector normalisation is used rather than min-max, so the *ratio* between
alternatives is preserved; min-max would force the worst alternative to zero on
every criterion regardless of how good it actually was.

### The modelling error, found by testing scenarios

First implementation returned an **Agile–DevSecOps hybrid for a low-risk
exploratory internal dashboard**. Wrong: the whole advantage of plain Agile
there is its lightness.

Two compounding causes, both worth recording:

**1. Not every criterion is "more is better".** Process ceremony has a *cost*. A
model demanding heavy documentation and formal verification is a **poor** fit for
a low-risk tool, not a neutral one — the ceremony is paid for whether needed or
not. Criteria were split: capability criteria (security, complexity handling)
score on capability; ceremony criteria score on **proximity to the need**, so
over-serving is penalised exactly as under-serving is.

**2. The subtler one — match criteria must not be weighted by the factor.**
Scaling every criterion's weight by how strongly the project exhibits it is
right for capability, and **exactly wrong** for match. A project needing light
process cares about not being burdened just as much as a regulated one cares
about rigour — but scaling by the factor gave the anti-ceremony criterion almost
no weight precisely when it mattered most. The criterion that should have
penalised excess ceremony was discounted away by its own low factor score.

After both fixes, all five scenarios return the lifecycle the brief's own
guidance table prescribes:

| project profile | result | brief's guidance |
|---|---|---|
| regulated + fast-changing UX (eKYC) | agile-devsecops hybrid **84 %** | "high regulation with evolving requirements" |
| stable + strict verification (payments switch) | v_model **79 %** | "strict verification and validation" |
| stable + heavy approvals (ledger migration) | v_model **80 %**, waterfall 65 % | "stable requirements and extensive approvals" |
| high uncertainty + complexity (fraud platform) | spiral **72 %** *(close call flagged)* | "high uncertainty or technical risk" |
| low risk + exploratory (dashboard) | agile **80 %** | "frequently changing requirements" |

That agreement is a check, not a proof — the guidance informed the candidate
profiles, so this shows the engine encodes the intended judgement consistently,
not that the judgement is correct. **Validating it against practising architects
is the outstanding work**, and the profile table is the part most in need of it.

### Also

- `MATCH_CRITERIA`, `SALIENCE_FLOOR` and the profile table are all module-level
  and documented, so the parts a practitioner would want to argue with are the
  parts that are easiest to find and change.
- 20 tests, including one scenario test per row of the guidance table.

**State: 171 tests passing, ruff clean, mypy clean across 58 source files.**

---

## 2026-09-04 — Does an LLM judge recover the recall NLI loses? Measured: no.

The obvious response to the NLI validator's 0.588 recall is to ask a language
model instead. It was built, measured against the **same 49 labelled pairs**, and
the answer changed the design — in the opposite direction from the one intended.

### Result

| arm | precision | recall | F1 | false confirmations |
|---|---|---|---|---|
| NLI alone | **0.909** | 0.588 | 0.714 | **1** |
| judge alone | 0.714 | **0.882** | 0.789 | 6 |
| cascade (NLI, then judge) | 0.714 | 0.882 | 0.789 | 6 |
| judge, quotation required | 0.786 | 0.647 | 0.710 | 3 |

On the 38 pairs NLI could not confirm, the judge **recovered 5 correct citations
and newly confirmed 5 wrong ones**. A one-for-one trade.

### Why F1 is the wrong metric here

F1 improves from 0.714 to 0.789, and taking that at face value would be a
mistake. **F1 assumes the two error types cost the same.** In this system they
do not:

- a **false confirmation** is a fabricated compliance claim, marked verified,
  relied upon by people who cannot re-check it;
- a **false rejection** is a correct citation shown to a human.

Six times the false confirmations, to save five human reviews, is a bad trade in
a system whose entire purpose is that its outputs can be trusted.

### The failures are instructive

The judge confirmed `RBI-MD-KYC:16(a)` (customer identity) for a
**beneficial-owner** requirement, reasoning that identification "is part of due
diligence". It confirmed `GDPR:Article 32.1(c)` (restoration of availability) for
an **encryption** requirement, reasoning from "a general duty to implement
security measures".

Both are the same error: **generalising from a parent duty to any obligation
within its scope.** And it was invited by the prompt's own concession — the
instruction that a general duty discharged by a specific implementation still
counts, which was written precisely to fix the NLI failure mode. Loosening the
criterion to catch the general-to-specific case also opened the door to
topic-to-obligation drift. The two are harder to separate than they look.

### Design change — the judge annotates, it does not decide

The judge no longer confirms anything. It attaches an **advisory opinion** to
citations in the `needs_review` band, for the human deciding, and is explicitly
labelled as unverified machine opinion. An unattributed machine opinion sitting
in a review queue is indistinguishable from a verified finding, and a reviewer
who cannot tell them apart will eventually stop checking — which would give away
the property the whole architecture is built to protect.

It is **off by default**: 19 s per citation for context, not authority.

### One thing that did work

Requiring the judge to **quote the obliging text** halved its false
confirmations, 6 to 3, at a cost of some recall. That is the same
quote-verification constraint applied to the proposing model, doing the same
work in a different place: a claim of obligation that cannot be anchored in text
that exists is not an established obligation.

### Where this leaves citation validation

Honestly: **partly solved.** Objective checks (resolution, quotation) are
reliable. Entailment is precise but insensitive, and no cheap second opinion
fixed it without importing the failure mode the system exists to prevent. The
current design accepts that and routes the difference to humans, which is
defensible and matches the brief's human-in-the-loop requirement rather than
pretending to more automation than the evidence supports.

Options not yet tried, in rough order of promise: a cross-encoder fine-tuned on
regulatory obligation pairs; a stronger reasoning model as judge (the measured
one is `qwen3:8b`, and this may be a capability limit rather than a method
limit); and decomposing the requirement into atomic obligations before checking,
so general-to-specific and topic-to-obligation stop being confusable.

**State: 175 tests passing, ruff clean, mypy clean across 58 source files.**

---

## 2026-09-04 — Finishing citation validation: two signals, and the agreement gate

The module was left "partly solved": objective checks reliable, entailment
precise but insensitive at 0.588 recall, and an LLM judge measured and rejected
for importing false confirmations.

Three options had been listed. A fourth turned out to be sitting in the
codebase already.

### The cross-encoder was a better validator than the NLI model

The reranker loaded for *retrieval* had never been asked whether it also
discriminates obligation. Measured over the same 49 labelled pairs:

| signal | AUC | precision | recall | false confirmations |
|---|---|---|---|---|
| NLI entailment (DeBERTa-MNLI) | 0.796 | 0.909 | 0.588 | 1 |
| **cross-encoder relevance** | **0.910** | **0.923** | **0.706** | 1 |
| embedding cosine | 0.748 | — | — | — |

The purpose-picked entailment model was **beaten by a component chosen for a
different job**. In hindsight it is not surprising: `bge-reranker-v2-m3` is a
large cross-encoder trained on relevance across many domains, where the MNLI
model is trained on a narrow task in a register regulatory text does not share.

Worth recording as a methodological point: the earlier work assumed the *type*
of model determined suitability, and never measured the alternative that was
already loaded and free.

### Agreement is worth more than either signal alone

The two models fail **differently** - NLI on general-to-specific obligations,
the cross-encoder on topical adjacency. Requiring both:

| configuration | precision | recall | false confirmations |
|---|---|---|---|
| NLI alone | 0.909 | 0.588 | 1 |
| cross-encoder alone | 0.923 | 0.706 | 1 |
| **both agreeing** | **1.000** | 0.529 | **0** |

Zero false confirmations is the property an auto-accept gate actually needs. A
tier that is *usually* right still ships fabricated compliance claims, and one
wrong claim marked verified costs more than several correct ones sent for review.

### Three tiers, because the useful question is what happens next

| tier | rule | measured purity | outcome |
|---|---|---|---|
| `confirmed` | both signals agree | **1.000** (9 genuine, 0 wrong) | accept unreviewed |
| `likely` | one signal confident | 0.667 (4 of 6) | review, ranked high |
| `unconfirmed` | neither | 0.118 (4 of 34) | review, ranked low |
| `conflicting` | confident contradiction | — | reject, surface as a finding |

The review queue is now *ordered* rather than a flat list: conflicts first,
then citations one model supports, then the rest. Same total human effort,
spent on the cases most likely to matter.

### A bug found by disagreeing with my own offline analysis

The first live run reported 11 confirmed with **1 false confirmation**, where the
offline sweep had given 9 with none. That discrepancy was the finding.

Cause: **a double sigmoid.** `bge-reranker` applies a sigmoid internally, so its
output is already a probability. Squashing it again collapsed the range from
[0, 1] to [0.50, 0.73], which made the 0.30 agreement threshold pass
*everything* - the second signal was effectively disabled, and the gate admitted
a wrong citation while appearing to work.

The same bug was present in the confidence calculation's `_normalise` and fixed
there too.

This is the kind of defect that survives every test: no exception, plausible
numbers, a working-looking pipeline. It was caught only because two independent
computations of the same quantity disagreed. Worth doing more often.

### Where citation validation now stands

**Finished, in a defensible sense.** There is an auto-accept tier with no
measured false confirmations, a ranked review queue for the rest, and every
threshold derived from a labelled sweep rather than chosen.

What it does *not* claim: 9 of 17 genuine citations are auto-accepted, so a
little over half the human effort is removed, not all of it. The honest summary
is that the system now knows *which* citations it can vouch for, which is the
property that matters more than how many.

Limitations unchanged and still real: 49 judgements, single annotator, one
corpus. The thresholds are fitted on the same set they are reported on, so these
numbers are optimistic; a held-out set is needed before quoting them as
performance.

**State: 183 tests passing, ruff clean, mypy clean across 60 source files.**

---

## 2026-09-04 — Next phase: orchestration, gates, persistence, change impact

With the agents measured individually, this phase makes them a system.

### The workflow graph

```
ingest -> extract -> [gate: requirement_baseline]
       -> map_compliance -> [gate: regulatory_interpretation]
       -> assess_coverage -> [gate: compliance_gap]
       -> recommend_sdlc -> [gate: sdlc_selection] -> persist
```

A state graph, not a swarm. This is where the LangGraph decision recorded at the
start of the project earns itself: execution order is explicit, every transition
is checkpointed, and the approval gates are `interrupt` points that **suspend the
run durably** rather than prompting inline.

The distinction matters. With a checkpointer, "resume" can mean days later, in a
different process, after a compliance officer has read the evidence. Verified by
test: a run suspended by one compiled handle is resumed by a **separate handle**
over the same store. That is the difference between a gate and a prompt.

### Gates enforce competence, not just consent

Each of the six gates declares which stakeholder roles may clear it. A product
owner cannot sign off a regulatory interpretation - the authority rests with
compliance or legal - and encoding that here makes it a property of the workflow
rather than a convention someone remembers.

**A rejection halts the run.** A gate whose refusal is noted and then ignored is
not a gate; there is a test asserting the pipeline never reaches the SDLC
recommendation after a rejected baseline.

Decisions **accumulate** rather than replace, so the record shows every decision
a reviewer made, not only the last.

### SDLC factors are derived, not asked for

`_derive_factors` computes the decision vector from what the pipeline actually
found - the share of requirements that are regulatory, that are security, that
carry elevated risk, and how many open questions remain. A factor vector supplied
by hand is a conclusion dressed as an input; deriving it means the lifecycle
recommendation is traceable to evidence like everything else here.

### Regulatory-change impact analysis

The capability the clause-level, version-by-supersession design was built for.
When a regulator amends a clause, "which of our requirements are now wrong" is a
**graph walk**, not a re-read of the specification.

Three severities, because they demand different responses:

| finding | meaning |
|---|---|
| `stale` | the cited clause was amended; the requirement may still be correct but must be re-verified |
| `orphaned` | the cited clause no longer exists; the requirement has lost its authority |
| control losing authority | a control whose supporting clause is gone must stop counting as covered |

Tested against a real amendment: a modified sub-clause is detected, its unchanged
sibling is **not** reported, a deleted clause orphans the requirement citing it,
and an unaffected requirement stays out of the report. There is also a test that
**re-wrapped text is not reported as an amendment** - reporting formatting as
change would flood the report and train reviewers to skim it.

### Bug found: enum columns were loading as plain strings

`Mapped[ApprovalStatus]` stored correctly and returned `str`. The type annotation
was a lie, and any caller reaching for `.value` on a loaded row raised
`AttributeError` — confirmed by reproduction, on a compliance decision path.

**Why it survived this long:** `StrEnum` members compare equal to their string
form, so every equality check in the codebase kept passing. The defect appears
only on *attribute access*, which no test had exercised until persistence
round-tripped a row.

Fixed with a `StrEnumType` decorator applied to all 15 enum columns, so the
annotations are now honest. It returns an unrecognised value as-is rather than
raising, so a record written before a vocabulary change stays readable.

Worth noting the pattern: this is the second defect this project has produced by
**two representations of the same thing quietly disagreeing** - the first was the
double sigmoid. Both were invisible to tests and found only when something forced
the two representations into contact.

### Persistence

A requirement is never written without its provenance edges. Rejected and
unconfirmed citations are persisted too: an unresolvable citation is a *finding*,
and discarding it would erase the evidence that the model proposed something
unfounded. Approval status reflects what humans actually decided - a halted run
persists DRAFT rather than silently baselining work a reviewer declined.

**State: 208 tests passing, ruff clean, mypy clean across 66 source files.**

---

## 2026-09-04 — API and interface

### The API

13 endpoints over the existing engines — retrieval, extraction, coverage, SDLC
ranking, change impact, and the traceability graph. Verified against the running
service rather than by inspection: a paraphrased query returns `RBI-MD-KYC:22`,
a regulated fast-changing profile returns `agile_devsecops_hybrid` at 77 %, and
four seed statements return 14 % control coverage with 9 blocking gaps.

Two decisions worth recording:

**API schemas are separate from the ORM.** A response model that is also a
database row leaks storage decisions to every client and freezes the schema.

**Health reports what is actually reachable, per model.** A run with retrieval
but no reranker, or citation checking without entailment, produces weaker
guarantees than a full one. A client should be able to *see* that rather than
infer it from worse answers.

### The interface

Apple's depth comes from **material, not ornament** — layered translucency, one
consistent light source, motion with real physics. The design follows that
rather than imitating its surface: a specular edge on every raised panel from
the same direction, backdrop blur with saturation, spring easing.

One constraint was applied deliberately, and it is a judgement the owner may
want to overrule. **This is a compliance tool, and decoration on a data surface
costs credibility** — a finding that animates like a marketing page invites the
reader to discount it. So depth and motion live in the ambient layers
(background, hero, the 3D graph) while anything carrying a citation, a score or
a gap is flat, still and legible. Numbers do not count up; gauges draw once and
stop.

The 3D graph shows the **real corpus** — 137 clause and document nodes, 211
edges, force-directed with documents pinned so the layout is stable across
reloads and a reader's spatial memory is worth something. It is 3D because the
data is: clauses nest inside clauses inside documents. A decorative 3D scene
beside a 2D list would have been ornament.

### The bug I nearly introduced by trusting a screenshot

The hero rendered, then stopped rendering, and the copy sat at **opacity 0.187**
mid-animation. I made three "fixes" — moving the background layers, weakening
the force layout, replacing the instanced mesh — before instrumenting properly.

The console said the scene mounted with 137 nodes and `useFrame` **never fired
once**. The browser pane was hidden, so `requestAnimationFrame` was paused.
Framer Motion animations stalled mid-flight, and the WebGL loop never ran.

Two things made this hard to see, both worth remembering:

- **Framer Motion uses the Web Animations API** for simple opacity and transform
  work, which runs on the compositor. Some animations completed while rAF was
  paused, which looked like proof that rAF was running.
- **`readPixels` on a canvas without `preserveDrawingBuffer` returns a cleared
  buffer**, so my "nothing was drawn" measurement was meaningless.

The code was correct throughout. Two of the three changes were unnecessary; the
instanced-mesh replacement is arguably better and was kept, and the layout
weakening was reverted after it collapsed every node onto one point.

The lesson is narrow and useful: **a rendering environment can be the thing
under test.** Instrument before changing anything whose failure mode is
"nothing appears".

### Also fixed — my own secret scanner crashed

Staging the frontend's `favicon.ico` aborted the pre-commit scan with
`UnicodeDecodeError`: staged content was read with `text=True`, and a binary is
not UTF-8. **A guard that crashes on an ordinary commit gets disabled**, which is
worse than one that skips a file it cannot read. Now decodes leniently. That is
the fifth correction to this script, every one found by running it.

### React Compiler and imperative rendering

Next 16's compiler lint rejects the mutation an animation loop requires. The
exception is file-scoped with a written justification: nothing in that file
participates in React's rendering model beyond mounting the canvas, and routing
137 positions per frame through state would re-render the tree sixty times a
second to no purpose. No other component carries the exception.

**State: 208 tests passing, ruff clean, mypy clean across 75 source files;
frontend builds clean with tsc and eslint clean.**

---

## Session: the frontend becomes an application, and the palette gets cut back

Two instructions drove this, and the second contradicted part of the first.

The first: divide the interface into modules rather than one page, put 3D
throughout rather than only in a hero, drive it from scroll, add a responsive
cursor, and cut clutter. The second, arriving mid-build: *remove these
unnecessary colours, looks bad, find a better cursor, be simplistic*, alongside
a reference screenshot of a near-monochrome light interface and the source of a
Dynamic Island component to use.

### One page became seven routes

`page.tsx` had stacked five panels on a single scroll. It is now an App Router
application: a landing page and six modules — Corpus, Retrieval, Requirements,
Coverage, Lifecycle, Impact — each with its own route, its own scene, and one
question it answers, stated in the navigation next to its name.

The rail and the pointer live in the root layout, so navigation preserves them.
That is what lets the rail's selection indicator travel from the module you left
to the one you arrived at: a `layoutId` on a single element rather than two
highlights cross-fading. A shared element tells you where you came from as well
as where you are.

`modules.ts` is a plain data file that the rail, the landing grid and the
previous/next links all read. Duplicating that list is how navigation and
content drift apart.

### The palette was doing too much

The dark theme carried five accents at once — blue, purple, green, amber, red.
Cut to a neutral ground with exactly three saturated colours left, and all three
mean *act on this*: a gap, a warning, a confirmation. Interactive is near-black
rather than a hue, because weight and contrast already do that job. Citation
keys lost their purple: a citation key is an identifier, not a category needing
its own colour.

This was the right call for a reason beyond taste. When everything is coloured,
colour stops carrying information, and a compliance finding printed in the same
palette as a decorative gradient reads as decoration.

The same logic reshaped every scene. Relevance is now drawn as darkness on a
continuous ramp rather than three colour bands, which invented three kinds of
result where there is only one kind with a score. Coverage spends colour only on
gaps — a covered control is the absence of a problem, and the absence of a
problem does not need a colour. Risk levels are shades with one exception:
critical, the only level at which a reader is being asked to stop.

### Two bugs the repaint exposed

`Badge` and `Failure` built their tinted borders as `` `${tone}44` `` where
`tone` was a CSS custom property. `var(--gap)44` is not a colour, so the browser
dropped the declaration and **those borders and backgrounds had never rendered
at all**. It looked deliberate, because the text colour on its own still worked.
Replaced with `color-mix`.

The API's CORS origins were hardcoded to `:3000`. A production build served on
any other port could not reach its own backend — which is exactly how it failed
the first time one was served. Now configurable, still listed rather than
wildcarded, because this API returns compliance findings.

### Scenes: from backdrop to figure

The first attempt put each module's scene full-bleed behind the content. On a
white ground that cannot be won: dark enough to see collides with the text,
washed out enough to protect the text leaves nothing to look at. Both were
tried, including a graduated white veil.

Each scene now has a bounded panel of its own below the module header, with a
border, its own ground and a caption saying what it shows. The conflict
disappears, and the scene stops being decoration behind content it was competing
with — it becomes a figure the reader can look at directly. Only the landing
page keeps a full-bleed scene, where the copy takes one half of the frame and
the particles the other.

### The rendering environment was the thing under test, again

Verifying 3D cost most of this session. The in-app browser pane reports
`document.hidden` and never runs `requestAnimationFrame`, so nothing draws in
it. Headless Chrome with `--virtual-time-budget` races hydration and the dynamic
import of the 3D bundle: some runs captured three rendered frames, some captured
none, and the difference looked exactly like a code change working or not
working. Screenshots are now taken over the DevTools Protocol with a real wait,
which is deterministic.

Instrumenting rather than guessing found three real defects that a screenshot
alone would have kept hidden:

- **The canvas was stuck at 300×150.** An absolutely positioned wrapper inside
  an `overflow: hidden` panel left React Three Fiber's own measurement at zero,
  so it never sized the drawing buffer. A plain full-size block measures
  reliably.
- **My visibility gate broke the thing it was optimising.** `frameloop="never"`
  while `document.hidden` meant a scene mounting in a background tab never
  rendered, never took its size, and stayed blank. It was also solving a problem
  the platform already solves — browsers suspend rAF in background tabs on their
  own. Removed.
- **Entrance animations gated content visibility.** Motion components animating
  from `opacity: 0` leave content invisible whenever the animation does not run,
  and motion suspends while the document reports itself hidden. A fully
  populated DOM sat at zero opacity. Headers, blocks and result lists are now
  revealed by CSS keyframes, which run without hydration and end in the final
  state regardless of when they ran. Scene entrances grow from a third of full
  size rather than from nothing, for the same reason.

The `Ring` and the lifecycle bars were converted from animated sweeps to drawn
values in the same pass. They had the same failure mode, and they also
contradicted the rule the rest of the interface follows: data does not animate.
A reader should not have to wait to learn a coverage ratio they are acting on.

### The Dynamic Island

Built the component the reference demo was written against, and put it to a real
use: extraction runs on a local model for forty to a hundred seconds, and a
still page is indistinguishable from a broken one. A single surface that changes
shape is easier to follow than a toast stack, because there is only ever one of
it.

It is transient. The first version idled with corpus size and model
reachability in it, which parked a pill over the middle of every page — on the
impact module it covered a form field. Persistent state moved to the rail, which
is always in the same place and never on top of anything. The island is for
things that are happening now and then stop.

### The pointer got quieter

The first custom cursor had a coloured ring, a blend mode and a text label, and
was the loudest thing on screen. A pointer that announces itself competes with
what it is pointing at. Now a small neutral disc trailing slightly behind the
true position, which is what gives it apparent mass.

Two fixes worth recording. It painted at the viewport centre before the pointer
had ever moved, which read as a rendering artefact — it now renders nothing
until it knows where it is. And the media queries moved to
`useSyncExternalStore`: reading `matchMedia` in an effect samples once at mount
and never notices a change, so someone turning on Reduce Motion kept whatever
was true when the page loaded.

### Test isolation — fixtures were leaking into the corpus

The corpus module showed twenty `TEST-MD-*` documents beside the three real
sources. The suite ran against the development database, and several fixtures
commit — an amendment scenario is only meaningful if both versions persist — so
the session fixture's rollback did not undo them. Forty-two documents and
fifty-five projects had accumulated, and the API served them.

**The tests passed throughout.** This was only ever visible as junk in a
listing.

Tests now run against a dedicated `nyaya_test` database, created with its
extensions on first use. That immediately exposed a second problem: the
retrieval tests guarded on "does the database contain any clauses at all" and
skipped otherwise. Against a shared database that worked by accident. Against a
clean one it passed on fifty-six rows of unrelated fixture data and then failed
looking for `RBI-MD-KYC:16(b)`. The corpus is now ingested by a session fixture,
so the suite is self-contained and the dependency is explicit rather than a line
in a README.

### Impact reported the same work item eleven times

With the demo data seeded, the impact walk reported eleven affected
requirements — all the same requirement and clause. Two separate causes, both
real:

- The walk emitted one entry per evidence row. A requirement carries several
  edges to the same clause, one per relation and one per extraction run that
  re-derived it. Now deduplicated on the pair, which is the actual unit of
  review work, and ordered orphaned-first so the queue is stable between runs.
- The rest were distinct requirement rows with the same ref, leaked from test
  runs — the isolation problem above, seen from the other end.

A regression test covers the first. The count is what a reviewer plans against,
so an inflated count is not a cosmetic problem.

### Seeded data, and why it is honest

`/impact` needs two versions of a source and some requirements to break.
`make seed` now ingests the corpus, then an amendment as version 2, then a
baseline project.

The amendment is expressed as the edits themselves rather than as a second copy
of the file — a duplicated corpus drifts the first time either is touched, and
the amendment *is* the diff. Its three edits exercise all three cases the walk
distinguishes: a clause amended, a quantity changed inside a clause, and a
clause removed outright.

Every seeded requirement cites a clause that is really in the corpus and quotes
text that really appears in it, resolved against the version in force when the
baseline was approved. Seeding a demo with invented citations would make the one
module whose subject is citation integrity the only one running on citations
nobody checked. Two of the five cite clauses the amendment leaves alone: if they
ever appear in an impact report, the walk is over-reporting.

The result is the report it should be — one orphaned, two stale, and silence
about the two untouched.

### Also corrected

`corpus_clauses` in the health response counted every clause row including
superseded versions. Ingesting the amendment made it jump from 104 to 160 while
the corpus a reader can actually cite had not grown at all. Now scoped to
in-force sources.

**State: 209 tests passing against an isolated test database, ruff clean, mypy
clean across 75 source files; frontend builds with tsc and eslint clean across
seven routes.**

---

## Session: the modules answer the questions they promised

Six pieces of feedback, and four of them were defects rather than preferences.

### Retrieval was scoring fragments

The reported complaint was that relevance scores were tiny — 0.077 for the
clause that was in fact correct. Two separate problems sat behind it.

The first was real and substantial. `load_context` ran **after** reranking, so
the cross-encoder scored every candidate as a bare sub-clause. This was already
a known failure in this codebase: supplying a clause's parent moved an
entailment score on one pair from 0.004 to 0.994, because "screening shall be
performed prior to activation" never says what is being screened against. The
same omission had been left in the reranking step.

Measured on the 34-query labelled set, attaching context before reranking moves
**MRR 0.723 → 0.819**, recall@10 0.779 → 0.824, nDCG@10 0.734 → 0.758. The
failure it fixes is systematic, not noise: without a parent the reranker prefers
the general parent clause over the specific sub-clause that governs, because the
parent is the half that reads like a complete statement. Nine of the fourteen
queries whose top result changed were exactly that shape.

**The eval harness had been measuring the wrong arm.** It reranked without
loading context, so it reported 0.723 while the shipping path scored 0.855 in a
standalone check. Its own docstring says the arm under test must be the code
that ships; it was not. Fixed, and the harness now agrees with the pipeline.

The second problem was presentation. The raw cross-encoder value was printed as
"relevance 0.077", which reads as "8% relevant" and is not what it means. So the
score was measured for what it actually predicts: banded by precision on the
labelled set, ≥0.5 meant 7 in 10 were the governing clause, 0.05–0.5 meant 4 in
10, below that under 2 in 10. **Rank turned out to be the far stronger signal**
— the top result is the governing clause 82% of the time and the second only
29% — so rank leads and the band supports it.

### Results were inert

Six clauses printed with nothing to do with them. They now expand to the full
clause text fetched from the corpus, carry their rank and what that rank is
worth, and offer a link that deep-links into the corpus module and a copy of the
citation key. The corpus module reads `?clause=` so those links land on the
selected clause, which also means one clause can be sent to a colleague.

### Impact returned 404 because the interface offered impossible work

Nothing was broken in the walk. The source selector listed every document,
including the two that hold a single version, and change analysis needs two — so
picking one returned a 404 the reader had done nothing to cause. `/knowledge/documents`
now reports every version it holds, and the selector offers only sources that
can actually be compared, with the versions themselves as dropdowns rather than
free text.

### The lifecycle module never answered its own question

It ranked hand-set factor profiles. Setting those sliders is choosing the answer
and then computing it — the arithmetic downstream only launders the choice.

`POST /analysis/sdlc/from-brief` now takes a project brief in plain language,
extracts requirements from it, derives the factor vector from what was actually
found, and ranks. The derivation moved out of the workflow into `nyaya/mcda/derive.py`
so the graph and the API share one implementation, and it returns the
observations behind each number: how much of the brief is regulatory, how much is
high risk, how many questions it left open. Measured end to end at 45 seconds on
a five-sentence brief, producing agile/V-model hybrid at 74% with DevSecOps at 70
— correctly flagged as a close call.

Floors, not defaults, on four factors. A brief that mentions no security
requirement is far more often one where nobody wrote it down than one where
security does not matter, and letting a factor fall to zero would let an
incomplete brief argue for a lighter process.

### Open questions can now be answered

Extraction surfaced them and stopped there. Each is now an input, and answering
any of them re-runs extraction with the answers **folded into the source text**
rather than passed as a side channel. That is a provenance property, not a
convenience: every quantity is checked against the source, so an answer supplied
out of band would let a real human-supplied number look exactly like an invented
one. Folded in, an answered question is simply more stated input and the same
checks apply to it.

### A retry that made a slow call catastrophic

Chasing an extraction that appeared to hang for seven minutes turned up a real
bug, though not the one being looked for. Extraction is fine — 37 seconds
measured directly; the requests had been queuing behind each other, since Ollama
serialises per model.

But the retry predicate covered `httpx.TransportError`, which includes
`ReadTimeout`. The read timeout is 300 seconds, so a stalled request burned
fifteen minutes across three attempts before surfacing anything, and the caller
could not distinguish that from a hang. A timeout also carries information a
retry destroys — the server is busy or the request is too large — and repeating
the identical request immediately is the one response guaranteed not to help.
Connection errors are still retried.

### Scenes: two rebuilt, one reframed

**Coverage** was drawing the result — covered or not — without the thing that
produces it. A control is a gap for exactly one reason: nothing points at it. It
is now the bipartite graph it always was, requirements on the left, the control
pack on the right, an edge where a requirement satisfies a control. The gaps are
the rings with no thread reaching them. Four threads against a wall of seventeen
unconnected controls says more than 19% ever did.

**Retrieval** had a translucent floor disc seventeen units across, which in a
wide short panel filled the frame and produced a pale grey dome with the data
invisible against it — it read as a rendering failure, which is the worst thing
an empty state can do. Gone. The corpus is a band of marks and the results are
columns in rank order, the first dark. The module also runs its first example on
arrival: retrieval is a vector lookup and a rerank, not a language model, and a
module that opens empty gives a reader nothing to judge.

**Requirements** now uses the scroll-driven particle assembly from the landing
page, which is the interaction that worked. The field starts scattered, which is
what stakeholder language is, and scroll resolves it into one column per
extracted requirement — column height is acceptance criteria, shade is risk
level, and the red share is how much of it is defective. Before extraction there
is nothing to assemble into, so it stays scattered, which is a truthful empty
state rather than a blank one.

Column heights use a square root. Cross-encoder scores on this corpus are small
and unevenly spread, and mapping them linearly made every column the same stub.

### The architecture, drawn

The honest shape of this system is not a swarm of agents conferring. It is a
fixed graph with language models at four points, non-model machinery checking
every one of them, and a human gate after each stage. The landing page now says
so in three lanes — proposes, verifies, decides — across the four stages. Read
down a column and you have the answer to "why should I believe this?".

Drawing it as a mesh of chatting agents would look more impressive and would
misrepresent it, and the difference is the entire argument: the reason to trust
an output here is precisely that a model did not get the last word on it.

Laid out with CSS grid rather than SVG so the text is real text. The first
attempt used `auto-fit, minmax(180px, 1fr)` for a lane label plus four stages;
with five items that wraps, and the fourth stage dropped onto a second row under
the lane label, reading as though it belonged to a different lane. An explicit
five-column template cannot do that, and the narrow case is a genuinely
different arrangement rather than a squeezed one.

### Also

The rail collapses, and remembers it. The preference is read through
`useSyncExternalStore` rather than hydrated from an effect — the effect version
is a cascading render and samples once at mount, so a second tab toggling the
rail would never be noticed. The width is published as a custom property so
content follows without every page subscribing to navigation state.

The landing scene fades out once scrolled past. It is fixed, so without that the
particle field followed the reader down the page and sat behind the architecture
diagram — five hundred moving dots behind body text, which is the exact
ornament-over-content failure this interface is meant to avoid.

**State: 219 tests passing against an isolated database, ruff and mypy clean
across 76 source files; frontend builds with tsc and eslint clean across seven
routes.**

---

## Session: the hero assembly, restored and kept

Feedback: the landing scene used to show particles spiralling into a structure,
that was the good part, and it had stopped doing it. Then, separately: it should
not vanish on scroll.

Both were my regressions, and the first was a straightforward arithmetic
collision. Convergence ran over scroll fraction 0 → 0.70. The fade I had added
to stop the fixed canvas following the reader down the page ran 0.22 → 0.40. So
**the field went fully transparent at 40% scroll with the structure only 57%
formed** — the three tiers never finished assembling on screen at all. Two
numbers picked separately, neither checked against the other.

Measuring the page instead of guessing: 1,956px of scroll travel at a 900px
viewport, hero section accounting for the first 42% of it. The assembly now runs
to 0.38 — nearly the whole hero — and the recede is defined as starting exactly
where the assembly ends, so the two cannot drift apart again.

### It recedes rather than leaves

The fade existed for a real reason: a fixed canvas follows the reader, and a
thousand moving dots behind body text is the ornament-over-content failure this
interface is built to avoid. Deleting it brings that back; fading to nothing
throws away the thing worth keeping.

So the field stays and gets out of the way. It holds half its opacity, and every
tier lightens towards a resting grey — opacity alone is not enough, because a
`#52525b` particle at half opacity over white still lands near body-text weight,
and a dot that dark inside a paragraph reads as a full stop in the wrong place.

The links recede much further, to 18%. A dot behind a word is a speck; a line is
a strike-through. The filaments run for hundreds of pixels and cross whole
sentences, so at the particles' resting opacity they were the one part of the
field genuinely competing with the text.

### The links were chords, not strands

Fixing the timing exposed a real defect in the structure itself. Each group of
three consecutive particles is one trace — source text, the requirement drawn
from it, the clause that obliges it — but the ring angle was taken from the
*particle* index, and golden-angle placement puts consecutive particles 137°
apart. Every link was therefore a long chord straight across the structure.
Nine hundred of those is a web, not a lattice, and on a page with centred
content those chords swept across whole paragraphs.

Taking the angle from the chain index instead gives all three members of a trace
the same angle, so each becomes a near-vertical strand leaning inward as it
rises through the tiers. Same data, and it now looks like what it represents.
The density went back up too — 520 particles to 1,100 — since the earlier
thinning was part of what had been lost.

The scatter is biased right rather than centred. The copy occupies the left of
the frame and a symmetric scatter puts a third of the field behind it.

**State: 219 tests passing, ruff and mypy clean across 76 source files; frontend
builds with tsc and eslint clean.**
