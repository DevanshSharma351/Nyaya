"""Provider-agnostic LLM interface.

Agents depend on this module, never on a vendor SDK. Adding a provider means
adding one subclass and one registry entry; it never means touching an agent.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(slots=True)
class Message:
    """A single conversational turn."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(slots=True)
class Usage:
    """Token accounting for one call.

    Recorded on every completion so that cost and volume are auditable even
    when the underlying provider is free-tier or local.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(slots=True)
class Completion:
    """The result of one generation call."""

    text: str
    model: str
    provider: str
    usage: Usage = field(default_factory=Usage)
    raw: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None


@dataclass(slots=True)
class StructuredCompletion[SchemaT: BaseModel]:
    """A generation call that was constrained to, and validated against, a schema."""

    value: SchemaT
    completion: Completion


class LLMError(RuntimeError):
    """Base class for provider failures."""


class SchemaValidationError(LLMError):
    """The model produced output that did not satisfy the requested schema."""

    def __init__(self, message: str, raw_output: str) -> None:
        super().__init__(message)
        self.raw_output = raw_output


class LLMProvider(abc.ABC):
    """The contract every provider adapter implements."""

    name: str

    def __init__(self, model: str) -> None:
        self.model = model

    @abc.abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> Completion:
        """Generate free-form text."""

    @abc.abstractmethod
    async def complete_structured[T: BaseModel](
        self,
        messages: list[Message],
        schema: type[T],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> StructuredCompletion[T]:
        """Generate output constrained to `schema` and return it validated.

        Implementations should prefer a native constrained-decoding or
        JSON-schema mode where the provider offers one, and fall back to
        prompt-level instruction plus repair only where it does not.
        """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts. Only embedding-capable providers implement this."""
        raise NotImplementedError(f"{self.name} does not provide embeddings")

    async def health(self) -> bool:
        """Report whether the provider is reachable and the model is available."""
        try:
            await self.complete([Message(role="user", content="ping")], max_tokens=1)
        except Exception:
            return False
        return True

    async def aclose(self) -> None:
        """Release any held resources (HTTP clients, sessions)."""
        return None
