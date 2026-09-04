"""Google AI Studio (Gemini) adapter.

Selected as the default hosted provider for its very large context window,
which matters here because regulatory sources are long documents that benefit
from being reasoned over in large spans rather than narrow chunks.
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


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str, api_key: str) -> None:
        super().__init__(model)
        if not api_key:
            raise LLMError("GOOGLE_API_KEY is not set; cannot use the gemini provider")
        from google import genai  # imported lazily so the dep stays optional

        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    @staticmethod
    def _split(messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        """Separate the system instruction from the conversational turns."""
        system = next((m.content for m in messages if m.role == "system"), None)
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in messages
            if m.role != "system"
        ]
        return system, contents

    @staticmethod
    def _usage(response: Any) -> Usage:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return Usage()
        return Usage(
            prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(meta, "candidates_token_count", 0) or 0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def _generate(self, contents: Any, config: dict[str, Any]) -> Any:
        # The SDK accepts a plain dict here and coerces it internally; the
        # typed config object is not used so that this adapter stays a thin
        # translation layer over the shared interface.
        return await self._client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,  # type: ignore[arg-type]
        )

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> Completion:
        system, contents = self._split(messages)
        config: dict[str, Any] = {"temperature": temperature}
        if system:
            config["system_instruction"] = system
        if max_tokens is not None:
            config["max_output_tokens"] = max_tokens
        if stop:
            config["stop_sequences"] = stop

        response = await self._generate(contents, config)
        return Completion(
            text=response.text or "",
            model=self.model,
            provider=self.name,
            usage=self._usage(response),
        )

    async def complete_structured[T: BaseModel](
        self,
        messages: list[Message],
        schema: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> StructuredCompletion[T]:
        system, contents = self._split(messages)
        config: dict[str, Any] = {
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        if system:
            config["system_instruction"] = system
        if max_tokens is not None:
            config["max_output_tokens"] = max_tokens

        response = await self._generate(contents, config)
        text = response.text or ""
        completion = Completion(
            text=text, model=self.model, provider=self.name, usage=self._usage(response)
        )
        try:
            value = schema.model_validate_json(text)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"Gemini output failed {schema.__name__} validation: {exc}", text
            ) from exc
        return StructuredCompletion(value=value, completion=completion)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.aio.models.embed_content(model=self.model, contents=texts)
        embeddings = response.embeddings or []
        vectors = [list(e.values) for e in embeddings if e.values is not None]
        if len(vectors) != len(texts):
            raise LLMError(f"Gemini returned {len(vectors)} embeddings for {len(texts)} inputs")
        return vectors


__all__ = ["GeminiProvider"]
