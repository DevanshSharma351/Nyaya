"""Anthropic (Claude) adapter.

Not used by default - the project is built to run at zero cost - but present so
that migrating to a paid frontier model is a configuration change rather than a
code change. Structured output is obtained via a forced single-tool call, which
is Anthropic's constrained-output mechanism.
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

_STRUCTURED_TOOL = "emit_result"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str, api_key: str) -> None:
        super().__init__(model)
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set; cannot use the anthropic provider")
        from anthropic import AsyncAnthropic  # lazy import keeps the dep optional

        self._client = AsyncAnthropic(api_key=api_key)

    @staticmethod
    def _split(messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        """Anthropic takes the system prompt as a top-level parameter."""
        system = next((m.content for m in messages if m.role == "system"), None)
        turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        return system, turns

    @staticmethod
    def _usage(response: Any) -> Usage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return Usage()
        return Usage(
            prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
            completion_tokens=getattr(usage, "output_tokens", 0) or 0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def _create(self, **kwargs: Any) -> Any:
        return await self._client.messages.create(**kwargs)

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> Completion:
        system, turns = self._split(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": turns,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
        }
        if system:
            kwargs["system"] = system
        if stop:
            kwargs["stop_sequences"] = stop

        response = await self._create(**kwargs)
        text = "".join(b.text for b in response.content if b.type == "text")
        return Completion(
            text=text,
            model=self.model,
            provider=self.name,
            usage=self._usage(response),
            finish_reason=response.stop_reason,
        )

    async def complete_structured[T: BaseModel](
        self,
        messages: list[Message],
        schema: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> StructuredCompletion[T]:
        system, turns = self._split(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": turns,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            "tools": [
                {
                    "name": _STRUCTURED_TOOL,
                    "description": f"Emit the result as a {schema.__name__} object.",
                    "input_schema": schema.model_json_schema(),
                }
            ],
            # Forcing the tool is what makes the output schema-constrained.
            "tool_choice": {"type": "tool", "name": _STRUCTURED_TOOL},
        }
        if system:
            kwargs["system"] = system

        response = await self._create(**kwargs)
        payload = next((b.input for b in response.content if b.type == "tool_use"), None)
        completion = Completion(
            text=str(payload),
            model=self.model,
            provider=self.name,
            usage=self._usage(response),
            finish_reason=response.stop_reason,
        )
        if payload is None:
            raise SchemaValidationError("Claude returned no tool_use block", str(response.content))
        try:
            value = schema.model_validate(payload)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"Claude output failed {schema.__name__} validation: {exc}", str(payload)
            ) from exc
        return StructuredCompletion(value=value, completion=completion)


__all__ = ["AnthropicProvider"]
