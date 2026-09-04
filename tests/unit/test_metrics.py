"""Ranking metric definitions."""

from __future__ import annotations

import pytest

from nyaya.eval.metrics import (
    hit_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_reciprocal_rank():
    assert reciprocal_rank(["a", "b", "c"], "a") == 1.0
    assert reciprocal_rank(["a", "b", "c"], "c") == pytest.approx(1 / 3)
    assert reciprocal_rank(["a", "b"], "z") == 0.0


def test_recall_and_precision():
    retrieved = ["a", "x", "b", "y"]
    relevant = {"a", "b", "c"}
    assert recall_at_k(retrieved, relevant, 1) == pytest.approx(1 / 3)
    assert recall_at_k(retrieved, relevant, 4) == pytest.approx(2 / 3)
    assert precision_at_k(retrieved, relevant, 4) == pytest.approx(0.5)


def test_hit_at_k():
    assert hit_at_k(["x", "a"], {"a"}, 2) == 1.0
    assert hit_at_k(["x", "a"], {"a"}, 1) == 0.0


def test_ndcg_rewards_earlier_placement():
    relevant = {"a", "b"}
    good = ndcg_at_k(["a", "b", "x", "y"], relevant, 4)
    poor = ndcg_at_k(["x", "y", "a", "b"], relevant, 4)
    assert good == pytest.approx(1.0)
    assert poor < good


def test_ndcg_handles_no_relevant_items():
    assert ndcg_at_k(["x"], set(), 5) == 0.0
