"""Ollama adapter - local models, no data egress, no cost.

This is the default provider. Ollama exposes a native `format` parameter that
accepts a JSON Schema and constrains decoding to it, so structured output here
is enforced rather than merely requested.
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from nyaya.llm.base import (
    Completion,
    LLMError,
    LLMProvider,
    Message,
    SchemaValidationError,
    StructuredCompletion,
    Usage,
)


class OllamaProvider(LLMProvider):
    """Talks to a local Ollama daemon over its HTTP API."""

    name = "ollama"

    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=300.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _usage(body: dict[str, Any]) -> Usage:
        return Usage(
            prompt_tokens=body.get("prompt_eval_count", 0) or 0,
            completion_tokens=body.get("eval_count", 0) or 0,
        )

    def _options(self, temperature: float, max_tokens: int | None) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        return options

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> Completion:
        options = self._options(temperature, max_tokens)
        if stop:
            options["stop"] = stop

        body = await self._post(
            "/api/chat",
            {
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
                "options": options,
            },
        )
        return Completion(
            text=body.get("message", {}).get("content", ""),
            model=self.model,
            provider=self.name,
            usage=self._usage(body),
            finish_reason=body.get("done_reason"),
            raw=body,
        )

    async def complete_structured[T: BaseModel](
        self,
        messages: list[Message],
        schema: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> StructuredCompletion[T]:
        # Ollama constrains decoding to the supplied JSON Schema, so the output
        # is structurally valid by construction; only semantic validation
        # (Pydantic field constraints) can still fail.
        body = await self._post(
            "/api/chat",
            {
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
                "format": schema.model_json_schema(),
                "options": self._options(temperature, max_tokens),
            },
        )
        text = body.get("message", {}).get("content", "")
        completion = Completion(
            text=text,
            model=self.model,
            provider=self.name,
            usage=self._usage(body),
            finish_reason=body.get("done_reason"),
            raw=body,
        )
        try:
            value = schema.model_validate_json(text)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"Ollama output failed {schema.__name__} validation: {exc}", text
            ) from exc
        return StructuredCompletion(value=value, completion=completion)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        body = await self._post("/api/embed", {"model": self.model, "input": texts})
        embeddings = body.get("embeddings")
        if not embeddings:
            raise LLMError(f"Ollama returned no embeddings for model {self.model}")
        return embeddings

    async def health(self) -> bool:
        """Check the daemon is up *and* this specific model is pulled."""
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            available = {m["name"] for m in response.json().get("models", [])}
        except Exception:
            return False
        # Ollama reports tagged names; a bare `name` implies the `:latest` tag.
        return self.model in available or f"{self.model}:latest" in available


__all__ = ["OllamaProvider"]
