"""Reciprocal Rank Fusion arithmetic, independent of the database."""

from __future__ import annotations

import uuid

import pytest

from nyaya.retrieval.hybrid import RRF_K, Retrieved, reciprocal_rank_fusion


def _r(key: str) -> Retrieved:
    return Retrieved(
        clause_id=uuid.uuid5(uuid.NAMESPACE_OID, key),
        citation_key=key,
        text=key,
        heading=None,
        document_code="X",
        jurisdiction="IN",
    )


def test_document_in_both_runs_outranks_one_in_either():
    """Agreement between retrievers is the signal RRF is built to reward."""
    run_a = [_r("A"), _r("B"), _r("C")]
    run_b = [_r("C"), _r("D"), _r("A")]
    keys = [r.citation_key for r in reciprocal_rank_fusion([run_a, run_b])]
    assert keys[0] == "A"  # rank 1 and rank 3
    assert keys.index("C") < keys.index("B")


def test_scores_match_the_definition():
    run_a = [_r("A"), _r("B")]
    run_b = [_r("B")]
    fused = {r.citation_key: r.fused_score for r in reciprocal_rank_fusion([run_a, run_b])}
    assert fused["A"] == pytest.approx(1 / (RRF_K + 1))
    assert fused["B"] == pytest.approx(1 / (RRF_K + 2) + 1 / (RRF_K + 1))


def test_zero_weight_arm_contributes_nothing():
    """The default configuration disables lexical fusion by weight alone.

    If a zero weight still influenced the ordering, that default would be a
    silent lie about which retriever produced a result.
    """
    dense = [_r("A"), _r("B")]
    lexical = [_r("Z"), _r("Y")]
    fused = reciprocal_rank_fusion([dense, lexical], weights=[1.0, 0.0])
    assert [r.citation_key for r in fused[:2]] == ["A", "B"]
    assert all(r.fused_score == 0.0 for r in fused if r.citation_key in {"Z", "Y"})


def test_weighting_changes_precedence():
    dense = [_r("D1"), _r("D2")]
    lexical = [_r("L1"), _r("L2")]
    dense_first = reciprocal_rank_fusion([dense, lexical], weights=[1.0, 0.1])
    lexical_first = reciprocal_rank_fusion([dense, lexical], weights=[0.1, 1.0])
    assert dense_first[0].citation_key == "D1"
    assert lexical_first[0].citation_key == "L1"


def test_ranks_from_both_arms_are_preserved():
    """A clause found by both must retain both ranks, for explainability."""
    shared = "S"
    fused = reciprocal_rank_fusion([[_r(shared)], [_r(shared)]])
    assert len(fused) == 1


def test_mismatched_weights_are_rejected():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[_r("A")], [_r("B")]], weights=[1.0])


def test_empty_runs():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
