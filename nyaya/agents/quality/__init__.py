"""Deterministic requirement-quality checks.

These run before any model is consulted. They are free, instant, reproducible,
and they produce *specific* defects with named remedies - which is what makes a
useful repair prompt possible. The LLM is left only with semantic ambiguity that
no rule can catch.
"""

from nyaya.agents.quality.ears import EARSAnalysis, EARSPattern, analyse
from nyaya.agents.quality.lexicon import (
    AmbiguityKind,
    Finding,
    blocking,
    scan,
    summarise,
)

__all__ = [
    "AmbiguityKind",
    "EARSAnalysis",
    "EARSPattern",
    "Finding",
    "analyse",
    "blocking",
    "scan",
    "summarise",
]
