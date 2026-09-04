"""Batch embedding.

Wraps the configured embedding provider with batching and dimension checking.
The dimension check is not defensive padding: a pgvector column has a fixed
width, so a model swap that changes dimensionality must fail loudly at ingest
rather than produce a confusing insert error much later.
"""

from __future__ import annotations

import asyncio

from nyaya.config import ModelRole, get_settings
from nyaya.db.base import EMBEDDING_DIM
from nyaya.llm import LLMError, get_provider

DEFAULT_BATCH = 32


class EmbeddingDimensionError(LLMError):
    """The configured model does not match the schema's vector width."""


async def embed_texts(
    texts: list[str],
    *,
    batch_size: int = DEFAULT_BATCH,
    expected_dim: int | None = EMBEDDING_DIM,
) -> list[list[float]]:
    """Embed `texts`, preserving input order."""
    if not texts:
        return []

    provider = get_provider(ModelRole.EMBEDDING)
    vectors: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        vectors.extend(await provider.embed(chunk))

    if len(vectors) != len(texts):
        raise LLMError(f"embedder returned {len(vectors)} vectors for {len(texts)} inputs")

    if expected_dim is not None and vectors and len(vectors[0]) != expected_dim:
        spec = get_settings().model_for(ModelRole.EMBEDDING)
        raise EmbeddingDimensionError(
            f"{spec} produces {len(vectors[0])}-dimensional vectors but the schema "
            f"declares {expected_dim}. Changing embedding model requires a migration "
            f"of the vector column and a full re-index."
        )
    return vectors


async def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return (await embed_texts([text]))[0]


def embed_texts_sync(texts: list[str], **kwargs) -> list[list[float]]:
    """Synchronous helper for scripts and one-off tooling."""
    return asyncio.run(embed_texts(texts, **kwargs))


__all__ = [
    "DEFAULT_BATCH",
    "EmbeddingDimensionError",
    "embed_query",
    "embed_texts",
    "embed_texts_sync",
]
