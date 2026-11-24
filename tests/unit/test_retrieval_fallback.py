from __future__ import annotations

import asyncio
import uuid
from importlib import import_module
from unittest.mock import AsyncMock

import pytest

from nyaya.config import get_settings
from nyaya.retrieval.hybrid import Retrieved
from nyaya.retrieval.search import search


@pytest.mark.parametrize("slow", [False, True], ids=["unavailable", "timeout"])
async def test_search_returns_candidates_when_reranking_cannot_finish(monkeypatch, slow):
    candidate = Retrieved(uuid.uuid4(), "REG:1", "Verify identity.", None, "REG", "IN")
    search_module = import_module(search.__module__)
    monkeypatch.setattr(search_module, "embed_query", AsyncMock(return_value=[]))
    monkeypatch.setattr(search_module, "dense_search", AsyncMock(return_value=[candidate]))
    monkeypatch.setattr(search_module, "load_context", AsyncMock())
    monkeypatch.setattr(get_settings(), "rerank_timeout_seconds", 0.01)

    async def rerank(query, candidates, *, top_n):
        candidates[0].rerank_score = 0.9
        if slow:
            await asyncio.Event().wait()
        raise OSError("model weights unavailable")

    monkeypatch.setattr(search_module, "rerank", rerank)
    result = await search(None, "identity verification")

    assert result.keys() == ["REG:1"]
    assert result.results[0].rerank_score is None
