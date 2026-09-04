"""Cross-encoder reranking.

Bi-encoders (the dense retriever) embed query and clause *independently*, so
they can only measure geometric proximity in a space built before either was
seen. A cross-encoder reads the pair jointly and scores relevance directly. It
is far too slow to run over a corpus, which is exactly why it runs second: cheap
retrieval proposes a shortlist, the expensive model orders it.

That ordering is what matters here. Retrieval feeds a fixed-size evidence window
to the compliance agent; a clause ranked 8th is usually outside it. Recall is
already high after fusion, so the remaining gains come from precision at the
very top of the list.

The model is loaded lazily and cached, because importing torch and materialising
weights costs seconds that unit tests should not pay.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING

from nyaya.config import get_settings
from nyaya.retrieval.hybrid import Retrieved

if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import CrossEncoder


@lru_cache(maxsize=2)
def _load(model_name: str) -> CrossEncoder:
    from sentence_transformers import CrossEncoder

    # Runs on Apple Silicon's GPU where available; falls back automatically.
    return CrossEncoder(model_name, max_length=512)


def available(model_name: str | None = None) -> bool:
    """Whether the reranker can be loaded.

    Reranking is an enhancement, not a dependency: a deployment without the
    model must still retrieve, just less precisely.
    """
    try:
        _load(model_name or get_settings().reranker_model)
    except Exception:
        return False
    return True


def rerank_sync(
    query: str,
    candidates: list[Retrieved],
    *,
    top_n: int | None = None,
    model_name: str | None = None,
) -> list[Retrieved]:
    """Reorder `candidates` by cross-encoder relevance to `query`."""
    if not candidates:
        return []

    settings = get_settings()
    model = _load(model_name or settings.reranker_model)

    pairs = [(query, c.display) for c in candidates]
    scores = model.predict(pairs, show_progress_bar=False)

    for candidate, score in zip(candidates, scores, strict=True):
        candidate.rerank_score = float(score)

    ordered = sorted(candidates, key=lambda c: c.rerank_score or 0.0, reverse=True)
    limit = top_n if top_n is not None else settings.rerank_top_n
    return ordered[:limit] if limit else ordered


async def rerank(
    query: str,
    candidates: list[Retrieved],
    *,
    top_n: int | None = None,
    model_name: str | None = None,
) -> list[Retrieved]:
    """Async wrapper.

    The cross-encoder is synchronous and CPU/GPU-bound, so it runs in a thread
    to avoid blocking the event loop while an agent graph is mid-flight.
    """
    return await asyncio.to_thread(
        rerank_sync, query, candidates, top_n=top_n, model_name=model_name
    )


__all__ = ["available", "rerank", "rerank_sync"]
