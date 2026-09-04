"""The two-signal obligation checker.

The model calls are not exercised here; what is testable without them is the
tier logic, which is what decides whether a citation is accepted unreviewed.
"""

from __future__ import annotations

import pytest

from nyaya.retrieval.obligation import (
    NLI_AGREE,
    RERANK_AGREE,
    RERANK_STRONG,
    ObligationCheck,
    ObligationTier,
)


def _check(tier: ObligationTier, **kw) -> ObligationCheck:
    return ObligationCheck(
        tier=tier,
        entailment=kw.get("entailment", 0.0),
        relevance=kw.get("relevance", 0.0),
        contradiction=kw.get("contradiction", 0.0),
        verified=kw.get("verified", True),
    )


def test_only_agreement_is_auto_acceptable():
    """Measured: agreement gives precision 1.000 with zero false confirmations,
    where either signal alone admits one."""
    assert _check(ObligationTier.CONFIRMED).auto_acceptable
    assert not _check(ObligationTier.LIKELY).auto_acceptable
    assert not _check(ObligationTier.UNCONFIRMED).auto_acceptable
    assert not _check(ObligationTier.CONFLICTING).auto_acceptable


def test_unverified_is_never_auto_acceptable():
    """A missing model means absent evidence, not evidence of obligation."""
    assert not _check(ObligationTier.CONFIRMED, verified=False).auto_acceptable


def test_review_queue_puts_conflicts_first():
    """A clause the requirement would breach is the most urgent thing a human
    can be shown; an unconfirmed citation is the least."""
    order = sorted(
        [
            _check(ObligationTier.UNCONFIRMED),
            _check(ObligationTier.CONFLICTING),
            _check(ObligationTier.CONFIRMED),
            _check(ObligationTier.LIKELY),
        ],
        key=lambda c: c.review_priority,
    )
    assert [c.tier for c in order] == [
        ObligationTier.CONFLICTING,
        ObligationTier.LIKELY,
        ObligationTier.UNCONFIRMED,
        ObligationTier.CONFIRMED,
    ]


@pytest.mark.parametrize("tier", list(ObligationTier))
def test_every_tier_explains_itself(tier):
    """A reviewer cannot act on a tier label alone."""
    explanation = _check(tier, entailment=0.4, relevance=0.6, contradiction=0.9).explain()
    assert explanation and len(explanation) > 20


def test_thresholds_are_ordered_sensibly():
    """The agreement bar is lower than the solo bar, because requiring both
    signals already supplies the precision a high solo threshold buys."""
    assert RERANK_AGREE < RERANK_STRONG
    assert 0.0 < NLI_AGREE < 1.0
    assert 0.0 < RERANK_AGREE < 1.0
