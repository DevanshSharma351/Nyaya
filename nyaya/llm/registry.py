"""Resolves a model *role* to a concrete provider instance.

Agents ask for `ModelRole.REASONING`; which vendor and model that means is a
deployment decision expressed entirely in configuration. Provider instances are
cached per spec so that HTTP clients and model handles are reused.
"""

from __future__ import annotations

from nyaya.config import ModelRole, ModelSpec, Settings, get_settings
from nyaya.llm.base import LLMError, LLMProvider

_cache: dict[str, LLMProvider] = {}


def _build(spec: ModelSpec, settings: Settings) -> LLMProvider:
    match spec.provider:
        case "ollama":
            from nyaya.llm.providers.ollama import OllamaProvider

            return OllamaProvider(spec.model, base_url=settings.ollama_base_url)

        case "gemini":
            from nyaya.llm.providers.gemini import GeminiProvider

            return GeminiProvider(spec.model, api_key=settings.google_api_key)

        case "groq":
            from nyaya.llm.providers.groq import GroqProvider

            return GroqProvider(spec.model, api_key=settings.groq_api_key)

        case "anthropic":
            from nyaya.llm.providers.anthropic import AnthropicProvider

            return AnthropicProvider(spec.model, api_key=settings.anthropic_api_key)

        case "echo":
            from nyaya.llm.providers.echo import EchoProvider

            return EchoProvider(spec.model)

        case unknown:
            raise LLMError(
                f"Unknown provider {unknown!r}. Supported: ollama, gemini, groq, anthropic, echo."
            )


def get_provider(role: ModelRole, settings: Settings | None = None) -> LLMProvider:
    """Return the provider configured for `role`."""
    settings = settings or get_settings()
    spec = settings.model_for(role)
    key = str(spec)
    if key not in _cache:
        _cache[key] = _build(spec, settings)
    return _cache[key]


def override(role: ModelRole, provider: LLMProvider, settings: Settings | None = None) -> None:
    """Pin `role` to a specific provider instance.

    Used by tests and by the eval harness, which swaps models between arms of
    an ablation without rewriting configuration.
    """
    settings = settings or get_settings()
    _cache[str(settings.model_for(role))] = provider


async def aclose_all() -> None:
    """Close every cached provider. Call on application shutdown."""
    for provider in _cache.values():
        await provider.aclose()
    _cache.clear()


__all__ = ["aclose_all", "get_provider", "override"]
