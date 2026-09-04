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


_SCALAR_DEFAULTS: dict[str, Any] = {
    "string": "",
    "integer": 0,
    "number": 0.0,
    "boolean": False,
    "array": [],
    "object": {},
    "null": None,
}


def _minimal_instance(schema: type[BaseModel]) -> dict[str, Any]:
    """Build the smallest JSON object satisfying a model's required fields.

    Must honour enums and nested models, not just scalars: nearly every schema
    in this project constrains fields to a closed vocabulary, and a default of
    `""` fails validation against one. A test double that cannot instantiate
    the project's own schemas is useless as a fixture or as an eval control arm.
    """
    spec = schema.model_json_schema()
    defs = spec.get("$defs", {})
    props = spec.get("properties", {})
    return {name: _value_for(props.get(name, {}), defs) for name in spec.get("required", [])}


def _value_for(prop: dict[str, Any], defs: dict[str, Any], depth: int = 0) -> Any:
    """Smallest value satisfying one property schema."""
    if depth > 6:  # guard against a self-referential schema
        return None

    if "$ref" in prop:
        return _value_for(defs.get(prop["$ref"].rsplit("/", 1)[-1], {}), defs, depth + 1)

    # anyOf / oneOf is how Optional[...] and unions are emitted. Prefer a
    # non-null branch so a required union still receives a usable value.
    for key in ("anyOf", "oneOf"):
        if key in prop:
            options = prop[key]
            chosen = next((o for o in options if o.get("type") != "null"), options[0])
            return _value_for(chosen, defs, depth + 1)

    if "enum" in prop:
        return prop["enum"][0]
    if "const" in prop:
        return prop["const"]

    kind = prop.get("type")
    if not isinstance(kind, str):
        return None
    if kind == "array":
        return []
    if kind == "object" or "properties" in prop:
        nested = prop.get("properties", {})
        return {n: _value_for(nested.get(n, {}), defs, depth + 1) for n in prop.get("required", [])}
    return _SCALAR_DEFAULTS.get(kind)


__all__ = ["EchoProvider"]
