"""Answers to open questions are folded into the source text, not passed aside.

This is a provenance property, not a formatting one. Every requirement must
quote the text it came from, and every quantity in it is checked against that
text - a threshold appearing in no source is treated as fabricated, which is the
failure this system exists to catch. An answer delivered to the model out of
band would let a real, human-supplied number look exactly like an invented one.
"""

from __future__ import annotations

from nyaya.api.routers.analysis import _with_clarifications
from nyaya.api.schemas import Clarification, ExtractIn


def test_text_is_unchanged_when_nothing_was_answered():
    payload = ExtractIn(text="Screen customers before activation.")
    assert _with_clarifications(payload) == "Screen customers before activation."


def test_an_answer_becomes_part_of_the_source_text():
    """The answer must appear verbatim, or the quantity check cannot see it."""
    payload = ExtractIn(
        text="Keep the evidence for audit.",
        clarifications=[
            Clarification(question="How long must evidence be kept?", answer="eight years")
        ],
    )
    folded = _with_clarifications(payload)

    assert "Keep the evidence for audit." in folded
    assert "eight years" in folded
    assert "How long must evidence be kept?" in folded


def test_a_question_mark_is_not_doubled():
    """Questions arrive with and without one; the folded line reads either way."""
    payload = ExtractIn(
        text="Base text.",
        clarifications=[
            Clarification(question="What is the retention period", answer="five years"),
            Clarification(question="Which lists apply?", answer="the notified list"),
        ],
    )
    folded = _with_clarifications(payload)

    assert "??" not in folded
    assert "What is the retention period? five years" in folded
    assert "Which lists apply? the notified list" in folded


def test_every_answer_survives():
    payload = ExtractIn(
        text="Base text.",
        clarifications=[
            Clarification(question=f"Q{i}?", answer=f"A{i}") for i in range(5)
        ],
    )
    folded = _with_clarifications(payload)
    for i in range(5):
        assert f"A{i}" in folded
