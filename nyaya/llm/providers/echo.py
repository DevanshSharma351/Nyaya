"""A deterministic test double.

Used by unit tests and by the eval harness's control arm, so that agent logic
can be exercised without a model server and without network access.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from nyaya.llm.base import (
    Completion,
    LLMProvider,
    Message,
    StructuredCompletion,
    Usage,
)


class EchoProvider(LLMProvider):
    """Returns canned responses supplied at construction time."""

    name = "echo"

    def __init__(self, model: str = "echo", responses: list[str] | None = None) -> None:
        super().__init__(model)
        self._responses = list(responses or [])
        self.calls: list[list[Message]] = []

    def _next(self, default: str) -> str:
        return self._responses.pop(0) if self._responses else default

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> Completion:
        self.calls.append(messages)
        return Completion(
            text=self._next(messages[-1].content if messages else ""),
            model=self.model,
            provider=self.name,
            usage=Usage(prompt_tokens=0, completion_tokens=0),
        )

    async def complete_structured[T: BaseModel](
        self,
        messages: list[Message],
        schema: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> StructuredCompletion[T]:
        self.calls.append(messages)
        raw = self._next(json.dumps(_minimal_instance(schema)))
        completion = Completion(text=raw, model=self.model, provider=self.name, usage=Usage())
        return StructuredCompletion(value=schema.model_validate_json(raw), completion=completion)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Stable, content-derived pseudo-embeddings: identical text always maps
        # to an identical vector, which keeps retrieval tests deterministic.
        return [[float((hash(t) >> i) & 0xFF) / 255.0 for i in range(8)] for t in texts]

    async def health(self) -> bool:
        return True


def _minimal_instance(schema: type[BaseModel]) -> dict[str, Any]:
    """Build the smallest JSON object satisfying a model's required fields."""
    defaults: dict[str, Any] = {
        "string": "",
        "integer": 0,
        "number": 0.0,
        "boolean": False,
        "array": [],
        "object": {},
    }
    spec = schema.model_json_schema()
    required = spec.get("required", [])
    props = spec.get("properties", {})
    return {k: defaults.get(props.get(k, {}).get("type", "string")) for k in required}


__all__ = ["EchoProvider"]
