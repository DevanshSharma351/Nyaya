"""The declarative rule language and its evaluator.

Entirely deterministic, so it is tested exhaustively without a model.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nyaya.ingestion import flatten, parse, split_clauses
from nyaya.rules import RuleError, evaluate, load_pack, requirement_facts
from nyaya.rules.dsl import Condition

PACK = Path("rules/compliance/ekyc-in.yaml")


def test_the_shipped_pack_loads():
    pack = load_pack(PACK)
    assert pack.controls
    assert pack.jurisdiction == "IN"


def test_every_control_cites_an_authority():
    """A control that cannot be traced to a source is an assertion, not an
    obligation. Enforcing one would be the unfounded claim this system exists
    to prevent."""
    sources = set()
    for path in Path("knowledge_base/corpus").glob("*.txt"):
        clauses = flatten(split_clauses(parse(path), short_code=path.stem))
        keys = {clause.citation_key for clause in clauses}
        assert len(keys) == len(clauses)
        assert all(clause.text.strip() for clause in clauses)
        sources.update(keys)
    for control in load_pack(PACK).controls:
        assert control.citations, f"{control.control_id} has no citation"
        assert set(control.citations) <= sources, control.control_id


def test_control_ids_are_unique():
    controls = load_pack(PACK).controls
    ids = [c.control_id for c in controls]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    ("kind", "value", "facts", "expected"),
    [
        ("category_any", ["security"], {"categories": ["security", "functional"]}, True),
        ("category_any", ["privacy"], {"categories": ["security"]}, False),
        (
            "category_all",
            ["security", "functional"],
            {"categories": ["security", "functional"]},
            True,
        ),
        ("category_all", ["security", "privacy"], {"categories": ["security"]}, False),
        ("text_matches", "screen", {"statement": "shall screen the customer"}, True),
        ("text_absent", "screen", {"statement": "shall verify identity"}, True),
        ("risk_at_least", "high", {"risk_level": "critical"}, True),
        ("risk_at_least", "critical", {"risk_level": "high"}, False),
        ("jurisdiction_any", ["IN"], {"jurisdictions": ["IN", "EU"]}, True),
        ("domain_is", ["ekyc_onboarding"], {"domain": "ekyc_onboarding"}, True),
    ],
)
def test_conditions(kind, value, facts, expected):
    assert Condition(kind=kind, value=value).evaluate(facts) is expected


def test_unknown_condition_is_rejected():
    with pytest.raises(RuleError):
        Condition(kind="teleport", value=1).evaluate({})


def test_malformed_pack_is_rejected_at_load(tmp_path):
    """A typo must surface on startup, not mid-assessment."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        yaml.safe_dump(
            {
                "name": "x",
                "version": "1",
                "jurisdiction": "IN",
                "domain": "ekyc_onboarding",
                "controls": [
                    {
                        "id": "A",
                        "title": "t",
                        "citations": ["X:1"],
                        "applies_when": [{"nonsense_kind": ["a"]}],
                    }
                ],
            }
        )
    )
    with pytest.raises(RuleError):
        load_pack(bad)


def test_uncited_control_is_rejected_at_load(tmp_path):
    bad = tmp_path / "uncited.yaml"
    bad.write_text(
        yaml.safe_dump(
            {
                "name": "x",
                "version": "1",
                "jurisdiction": "IN",
                "domain": "ekyc_onboarding",
                "controls": [{"id": "A", "title": "t", "citations": []}],
            }
        )
    )
    with pytest.raises(RuleError, match="citation"):
        load_pack(bad)


def test_gap_analysis_identifies_uncovered_controls():
    reqs = [
        (
            "FR-KYC-001",
            requirement_facts(
                statement=(
                    "The system shall screen the customer against the "
                    "designated-persons list before activation."
                ),
                categories=["regulatory", "security"],
            ),
        )
    ]
    report = evaluate(reqs)[0]
    covered = {c.control_id for c in report.coverage if not c.is_gap}
    assert "KYC.SCREEN.SANCTIONS" in covered
    # A single screening requirement cannot discharge unrelated controls.
    assert "KYC.RECORDS.RETENTION" in {c.control_id for c in report.gaps}
    assert report.blocking_gaps


def test_full_coverage_leaves_no_gaps():
    """Coverage must reach 1.0 when every control is addressed."""
    statements = [
        "Verify the applicant identity with an independent document before opening the account.",
        "Identify the beneficial owner and verify their identity.",
        "Record the purpose and intended nature of the relationship.",
        "Screen applicants against sanctions lists before activation.",
        "Re-screen customers whenever the lists change.",
        "Assign and periodically review the customer risk category.",
        "Do not disclose the risk category to the customer.",
        "Require senior management approval for politically exposed persons.",
        "Run liveness detection in each video identification session.",
        "Record every video session with a timestamp.",
        "Capture geolocation coordinates and restrict sessions to a domestic IP address.",
        "Obtain explicit consent before electronic verification.",
        "Let customers withdraw consent as easily as they gave it.",
        "Retain identification records after the relationship ends.",
        "Restrict access to identity records and log each access.",
        "Encrypt customer information in transit over public networks.",
        "Preserve an audit trail of electronic verification.",
        "Do not inform the customer that a suspicious transaction report was filed.",
        "Notify the board and affected customers of a data breach.",
        "Collect only personal data necessary for the stated purpose.",
        "Erase personal data after consent is withdrawn unless a retention obligation applies.",
    ]
    reqs = [
        (
            f"FR-{i:03d}",
            requirement_facts(
                statement=statement,
                categories=["regulatory", "security", "functional"],
            ),
        )
        for i, statement in enumerate(statements)
    ]
    report = evaluate(reqs)[0]
    assert report.coverage_ratio == 1.0, [g.control_id for g in report.gaps]


def test_unrelated_keywords_do_not_count_as_kyc_controls():
    statements = [
        "The system shall verify the amount and retain the shopping cart.",
        "The system shall erase temporary files at midnight.",
        "The system shall show the initial screen without consent.",
        "The system shall not disclose the email address.",
        "The system shall encrypt report archives at rest.",
    ]
    report = evaluate([
        (str(index), requirement_facts(statement=statement, categories=["security", "functional"]))
        for index, statement in enumerate(statements)
    ])[0]
    assert report.coverage_ratio == 0.0


def test_gap_explanations_name_the_authority():
    """An unexplained compliance finding is not actionable."""
    report = evaluate([("FR-001", requirement_facts(statement="x", categories=[]))])[0]
    for explanation in report.explain_gaps():
        assert "Authority:" in explanation
        assert "Required because" in explanation
