"""The local models must survive concurrent use.

Both the reranker and the entailment pipeline are loaded once and shared, then
called from worker threads so they do not block the event loop. That
combination is not thread-safe, and on Apple Silicon's Metal backend it does not
degrade - it segfaults the process, taking the API with it.

It was invisible while this machine ran an x86-64 Python under Rosetta, where
MPS was unavailable and everything fell back to CPU. A native arm64 Python
selects `mps:0`, and four concurrent searches killed the server instantly. The
frontend produces exactly that: React double-invokes effects in development, and
the retrieval module seeds a query on mount.

This test fires concurrent work at both models. A regression does not fail an
assertion here - it terminates the test process - which is a blunt signal, but
the alternative is finding out from a browser.
"""

from __future__ import annotations

import asyncio

import pytest

from nyaya.retrieval import SearchOptions, search
from nyaya.retrieval.nli import available as nli_available
from nyaya.retrieval.nli import check
from nyaya.retrieval.rerank import available as reranker_available

QUERIES = [
    "check every new customer against the sanctions list before their account goes live",
    "how long do we keep proof of identity checks after someone closes their account",
    "the selfie step needs to prove the person is actually there, not a photo",
    "can we open an account for someone who will not say who really owns the company",
]


async def test_concurrent_searches_do_not_crash_the_reranker(session, corpus_ingested):
    """Four searches at once, which is what one page load produces."""
    if not reranker_available():
        pytest.skip("reranker model not available")

    async def one(query: str):
        return await search(session, query, options=SearchOptions(top_k=6))

    results = await asyncio.gather(*(one(q) for q in QUERIES))
    assert all(r.results for r in results)


async def test_concurrent_entailment_does_not_crash(corpus_ingested):
    """The validator checks several citations for one requirement at a time."""
    if not nli_available():
        pytest.skip("entailment model not available")

    premise = (
        "The Regulated Entity shall screen the customer against the lists of "
        "designated persons notified by the competent authority."
    )
    hypothesis = "It is required that the customer be screened before activation."

    verdicts = await asyncio.gather(*(check(premise, hypothesis) for _ in range(6)))
    # Identical inputs must give identical verdicts; a race would not.
    assert len({(v.relation, round(v.score, 4)) for v in verdicts}) == 1
