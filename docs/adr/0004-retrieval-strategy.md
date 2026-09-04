# ADR-0004 — Retrieval strategy: dense + rerank, fusion off by default

**Status:** Accepted · **Date:** 2026-09-04

## Context

Retrieval bounds every downstream metric. Citation correctness, regulatory
control coverage and hallucination rate are all capped by whether the governing
clause was retrieved at all. So it was benchmarked in isolation, before any agent
was written.

The prior design — recorded in the original architecture notes — asserted that
*hybrid dense + lexical fused by RRF, then reranked* would give "a large,
measurable lift over naive dense retrieval". **That assertion was wrong**, and
this ADR records the measurement that refuted it.

## Evaluation setup

- **Corpus:** 104 clauses across three sources (RBI Master Direction on KYC,
  DPDP 2023, GDPR), clause-split with citation keys.
- **Queries:** 34 labelled, in two deliberately separated styles.
  - `paraphrase` (n=24) — lay stakeholder wording sharing almost no vocabulary
    with the clause. This is how requirements actually arrive.
  - `term_of_art` (n=10) — the precise legal category named directly. This is
    the case lexical retrieval exists for.

  Splitting them matters: a blended average would have hidden the fact that the
  two retrievers succeed on disjoint query types.
- **Metrics:** MRR against the single governing clause, plus Recall/nDCG/Hit@k
  against the full relevant set.

## Measurements

Combined (n=34):

| arm | MRR | R@1 | R@5 | nDCG@10 | Hit@5 |
|---|---|---|---|---|---|
| lexical | 0.406 | 0.225 | 0.441 | 0.446 | 0.706 |
| dense | 0.659 | 0.365 | 0.659 | 0.721 | 0.971 |
| hybrid (RRF) | 0.620 | 0.314 | 0.613 | 0.632 | 0.912 |
| dense + rerank | **0.737** | **0.400** | **0.672** | **0.743** | **1.000** |
| hybrid + rerank | 0.737 | 0.400 | 0.672 | 0.743 | 1.000 |

By style (MRR):

| arm | paraphrase (24) | term_of_art (10) |
|---|---|---|
| lexical | 0.249 | 0.783 |
| dense | 0.579 | 0.850 |
| hybrid | 0.503 | 0.900 |
| dense + rerank | 0.690 | 0.850 |

A fusion-weight sweep on paraphrase queries was monotonic: MRR fell from 0.579
at `w_lex = 0` to 0.443 at `w_lex = 1.0`. There was no interior optimum.

## Decision

**Default retrieval is dense, then cross-encoder rerank. Lexical fusion is
disabled by weight (`DEFAULT_FUSION_WEIGHTS = (1.0, 0.0)`), not deleted.**

Three findings drive this:

1. **Reranking is the real win: +11.8 % MRR** over dense (0.659 → 0.737), and
   **Hit@5 reaches 1.000** — after reranking, at least one governing clause is
   in the top five for *every* query. That is the number the evidence window
   depends on.
2. **Fusion is not justified on this corpus.** Hybrid scored *below* dense alone
   (0.620 vs 0.659). Worse, `hybrid + rerank` and `dense + rerank` are
   **numerically identical to three decimal places** — the lexical arm changes
   nothing after reranking while adding a second query and its latency.
3. **The arms are genuinely complementary, but unequally so.** Lexical is
   3.1× better on term-of-art queries than on paraphrase (0.783 vs 0.249).
   Unweighted RRF assumes comparable arm quality; here dense is more than twice
   as strong overall, so equal fusion imports the weaker arm's errors.

## Why keep the lexical path at all

Three reasons it is disabled rather than removed:

1. **Corpus size.** 104 clauses is small, and dense retrieval flatters itself on
   small, topically coherent corpora. Lexical methods characteristically hold up
   better as a corpus grows and embeddings crowd. This must be re-measured as
   the KB expands — the weight is a config knob precisely so that re-enabling it
   costs nothing.
2. **Exact-match lookup is a separate need.** `resolve_citation` already depends
   on exact key matching, and term-of-art queries are a real usage pattern even
   if they are the minority.
3. **The ablation must exercise shipped code.** The eval harness runs the same
   functions the agents call, so the arms under test cannot drift from the
   implementation.

## Consequences

- Latency is dominated by the reranker (~1 s/query at n=30 candidates on an
  M3 Pro, versus ~140 ms without). Acceptable for an analyst-facing workflow;
  it would need batching for interactive typeahead.
- The reranker adds a **2.3 GB** model download. `search()` degrades to
  unreranked dense retrieval when it is unavailable, rather than failing.
- The evidence window is capped at 8 clauses. A larger window invites a model to
  cite a plausible neighbour rather than the governing clause.

## Revisit when

- The corpus exceeds ~1,000 clauses (re-run the fusion sweep).
- The embedding model changes (all numbers here are bge-m3 specific).
- Query mix shifts materially toward term-of-art phrasing.
