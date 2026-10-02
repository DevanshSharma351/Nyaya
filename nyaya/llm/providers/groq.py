"""Groq adapter - free-tier hosted inference, used as the hosted fallback.

Groq serves open-weight models over an OpenAI-compatible API with structured
output via JSON-schema response formats.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from nyaya.llm.base import (
    Completion,
    LLMError,
    LLMProvider,
    Message,
    SchemaValidationError,
    StructuredCompletion,
    Usage,
)


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, model: str, api_key: str) -> None:
        super().__init__(model)
        if not api_key:
            raise LLMError("GROQ_API_KEY is not set; cannot use the groq provider")
        from groq import AsyncGroq  # lazy import keeps the dep optional

        self._client = AsyncGroq(api_key=api_key)

    def _usage(self, response: Any) -> Usage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return Usage(model=self.model)
        return Usage(
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            model=self.model,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def _create(self, **kwargs: Any) -> Any:
        return await self._client.chat.completions.create(**kwargs)

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> Completion:
        response = await self._create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )
        choice = response.choices[0]
        return Completion(
            text=choice.message.content or "",
            model=self.model,
            provider=self.name,
            usage=self._usage(response),
            finish_reason=choice.finish_reason,
        )

    async def complete_structured[T: BaseModel](
        self,
        messages: list[Message],
        schema: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> StructuredCompletion[T]:
        response = await self._create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            },
        )
        text = response.choices[0].message.content or ""
        completion = Completion(
            text=text, model=self.model, provider=self.name, usage=self._usage(response)
        )
        try:
            value = schema.model_validate_json(text)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"Groq output failed {schema.__name__} validation: {exc}", text
            ) from exc
        return StructuredCompletion(value=value, completion=completion)


__all__ = ["GroqProvider"]
