"""The LLM judge's deterministic scaffolding.

The model call is not exercised here; what is testable without one is the
verdict mapping and the quotation check, which is the constraint keeping the
judge to the same standard as the model whose citation it reviews.
"""

from __future__ import annotations

import pytest

from nyaya.agents.judge import JudgeVerdict, judge
from nyaya.config import ModelRole
from nyaya.core.enums import EvidenceRelation
from nyaya.llm import override
from nyaya.llm.providers.echo import EchoProvider

CLAUSE = "Customer information transmitted over a public network shall be protected by encryption."
REQUIREMENT = (
    "The system shall encrypt customer identification documents transmitted over public networks."
)


def _canned(verdict: str, obliging_text: str) -> EchoProvider:
    payload = JudgeVerdict(
        verdict=verdict, obliging_text=obliging_text, reasoning="because"
    ).model_dump_json()
    return EchoProvider(responses=[payload])


async def test_obliging_verdict_with_a_real_quotation_is_accepted():
    override(ModelRole.REASONING, _canned("obliges", "shall be protected by encryption"))
    result = await judge(CLAUSE, REQUIREMENT)
    assert result.relation is EvidenceRelation.SUPPORTS
    assert result.quote_verified
    assert result.obliges


async def test_obliging_verdict_with_a_fabricated_quotation_does_not_oblige():
    """A judge that cannot point at the obliging words has established nothing.

    This is the same standard applied to the proposing model: a claim of
    obligation must be anchored in text that exists.
    """
    override(
        ModelRole.REASONING,
        _canned("obliges", "the controller shall perform quarterly penetration testing"),
    )
    result = await judge(CLAUSE, REQUIREMENT)
    assert result.relation is EvidenceRelation.SUPPORTS
    assert not result.quote_verified
    assert not result.obliges


async def test_conflict_verdict_maps_to_contradicts():
    override(ModelRole.REASONING, _canned("conflicts", "shall be protected by encryption"))
    result = await judge(CLAUSE, REQUIREMENT)
    assert result.relation is EvidenceRelation.CONTRADICTS


async def test_non_obliging_verdict_maps_to_neutral():
    override(ModelRole.REASONING, _canned("does_not_oblige", ""))
    result = await judge(CLAUSE, REQUIREMENT)
    assert result.relation is EvidenceRelation.NEUTRAL
    assert not result.obliges


async def test_unrecognised_verdict_defaults_to_neutral():
    """An unparseable verdict must never be read as an obligation."""
    override(ModelRole.REASONING, _canned("probably fine", "shall be protected"))
    result = await judge(CLAUSE, REQUIREMENT)
    assert result.relation is EvidenceRelation.NEUTRAL


@pytest.mark.parametrize(
    "quotation",
    ["shall be protected by  encryption", "SHALL BE PROTECTED BY ENCRYPTION"],
)
async def test_quotation_check_tolerates_whitespace_and_case(quotation):
    """Models reflow and recase text; that is not fabrication."""
    override(ModelRole.REASONING, _canned("obliges", quotation))
    assert (await judge(CLAUSE, REQUIREMENT)).quote_verified
