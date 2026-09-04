"""The deterministic test double must satisfy this project's own schemas."""

from __future__ import annotations

from pydantic import BaseModel

from nyaya.core.enums import Priority, RequirementCategory, RiskLevel
from nyaya.llm.base import Message
from nyaya.llm.providers.echo import EchoProvider


class Nested(BaseModel):
    label: str
    level: RiskLevel


class Extracted(BaseModel):
    requirement_id: str
    statement: str
    categories: list[RequirementCategory]
    priority: Priority
    nested: Nested
    optional_note: str | None = None


async def test_double_can_instantiate_a_schema_with_enums():
    """Regression: enum fields got a `""` default and failed validation.

    Nearly every schema here constrains fields to a closed vocabulary, so a
    double that cannot build one is useless as a fixture or eval control arm.
    """
    provider = EchoProvider()
    result = await provider.complete_structured(
        [Message(role="user", content="anything")], Extracted
    )
    value = result.value
    assert value.priority in set(Priority)
    assert value.nested.level in set(RiskLevel)
    assert value.categories == []


async def test_canned_responses_are_returned_in_order():
    provider = EchoProvider(responses=["first", "second"])
    a = await provider.complete([Message(role="user", content="x")])
    b = await provider.complete([Message(role="user", content="y")])
    assert (a.text, b.text) == ("first", "second")


async def test_embeddings_are_deterministic():
    """Identical text must embed identically, or retrieval tests turn flaky."""
    provider = EchoProvider()
    first = await provider.embed(["step-up authentication"])
    second = await provider.embed(["step-up authentication"])
    assert first == second
