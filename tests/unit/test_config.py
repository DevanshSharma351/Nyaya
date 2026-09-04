"""Model-spec parsing.

`ModelSpec` was originally a `BaseSettings`, which made it constructible with no
arguments and silently populated from `PROVIDER` / `MODEL` environment
variables. These tests pin the corrected behaviour.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nyaya.config import ModelRole, ModelSpec, Settings


def test_spec_is_not_environment_backed(monkeypatch):
    """A stray PROVIDER/MODEL in the environment must not populate a spec."""
    monkeypatch.setenv("PROVIDER", "hijacked")
    monkeypatch.setenv("MODEL", "hijacked")

    with pytest.raises(ValidationError):
        ModelSpec()  # type: ignore[call-arg]

    spec = ModelSpec.parse("ollama:qwen3:8b")
    assert (spec.provider, spec.model) == ("ollama", "qwen3:8b")


@pytest.mark.parametrize("raw", ["ollama", "", ":", "ollama:", ":model", "  :  "])
def test_malformed_specs_are_rejected(raw):
    with pytest.raises(ValueError):
        ModelSpec.parse(raw)


def test_only_the_first_colon_separates():
    """Ollama tags contain colons, so the model half must keep them."""
    spec = ModelSpec.parse("ollama:qwen3:8b")
    assert spec.model == "qwen3:8b"
    assert str(spec) == "ollama:qwen3:8b"


def test_every_role_resolves():
    settings = Settings()
    for role in ModelRole:
        spec = settings.model_for(role)
        assert spec.provider and spec.model
