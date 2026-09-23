"""A failing repair pass must not destroy a good extraction.

The repair pass is an enhancement: it rewrites statements the linters flagged.
When it timed out, the whole request failed with a 500 and a complete first-pass
extraction was discarded - the requirements were correct, they simply still
carried the defects a reviewer would have been shown anyway.
"""

from __future__ import annotations

import httpx
import pytest

from nyaya.agents.extraction import extract
from nyaya.agents.schemas import ExtractionContext, ExtractionOutput
from nyaya.llm.base import Completion, StructuredCompletion, Usage

VAGUE = "The system shall process payments quickly."


class _Provider:
    """First pass succeeds; the repair pass raises."""

    name = "stub"
    model = "stub"

    def __init__(self, failure: Exception) -> None:
        self.failure = failure
        self.calls = 0

    async def complete_structured(self, messages, schema):
        self.calls += 1
        if self.calls > 1:
            raise self.failure
        value = ExtractionOutput(
            requirements=[
                {
                    "statement": VAGUE,
                    "rationale": "payments must be timely",
                    "categories": ["functional"],
                    "priority": "must",
                    "risk_level": "high",
                    "acceptance_criteria": [],
                    "assumptions": [],
                    "quoted_source": "process payments quickly",
                }
            ],
            unclear=[],
        )
        return StructuredCompletion(
            value=value,
            completion=Completion(
                text=value.model_dump_json(),
                model="stub",
                provider="stub",
                usage=Usage(),
            ),
        )


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ReadTimeout("timed out"),
        httpx.ConnectError("refused"),
        RuntimeError("something else"),
    ],
)
async def test_the_extraction_survives_a_failed_repair(monkeypatch, failure):
    provider = _Provider(failure)
    monkeypatch.setattr(
        "nyaya.agents.extraction.get_provider", lambda _role: provider
    )

    result = await extract(VAGUE, context=ExtractionContext())

    # The requirement is still here, and still flagged.
    assert len(result.requirements) == 1
    assert result.requirements[0].defects
    # And the run says what it could not do.
    assert result.notes
    assert "Repair was skipped" in result.notes[0]


async def test_a_clean_run_carries_no_notes(monkeypatch):
    """A degraded result and a good one must be distinguishable."""

    class _Clean(_Provider):
        async def complete_structured(self, messages, schema):
            self.calls += 1
            value = ExtractionOutput(
                requirements=[
                    {
                        "statement": (
                            "When a payment is submitted, the system shall settle it "
                            "within 2 seconds."
                        ),
                        "rationale": "settlement is time-bound",
                        "categories": ["functional"],
                        "priority": "must",
                        "risk_level": "high",
                        "acceptance_criteria": ["settles within 2 seconds"],
                        "assumptions": [],
                        "quoted_source": "settle it within 2 seconds",
                    }
                ],
                unclear=[],
            )
            return StructuredCompletion(
                value=value,
                completion=Completion(
                    text=value.model_dump_json(), model="stub", provider="stub", usage=Usage()
                ),
            )

    provider = _Clean(RuntimeError("never raised"))
    monkeypatch.setattr("nyaya.agents.extraction.get_provider", lambda _role: provider)

    result = await extract(
        "settle it within 2 seconds", context=ExtractionContext()
    )
    assert result.notes == []
