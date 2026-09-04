"""Evaluate requirements against mandatory control packs.

Produces the answer compliance actually cares about: **which mandatory controls
no requirement covers.** A gap is the actionable output; a list of satisfied
controls is reassurance.

Entirely deterministic. Given the same requirements and the same pack version,
it returns the same coverage, with the same explanation for every decision. That
reproducibility is what lets a coverage report be an audit artefact rather than
a model's opinion on the day.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nyaya.rules.dsl import Control, RulePack, load_all

DEFAULT_RULES_DIR = Path("rules/compliance")


@dataclass(slots=True)
class ControlCoverage:
    """Whether one mandatory control is discharged, and by what."""

    control: Control
    satisfied_by: list[str] = field(default_factory=list)
    """Requirement refs that satisfy it."""

    @property
    def is_gap(self) -> bool:
        return not self.satisfied_by

    @property
    def control_id(self) -> str:
        return self.control.control_id


@dataclass(slots=True)
class CoverageReport:
    """Control coverage across a set of requirements."""

    pack: str
    pack_version: str
    coverage: list[ControlCoverage] = field(default_factory=list)

    @property
    def gaps(self) -> list[ControlCoverage]:
        return [c for c in self.coverage if c.is_gap]

    @property
    def blocking_gaps(self) -> list[ControlCoverage]:
        """Gaps in controls whose absence should stop a release."""
        return [c for c in self.gaps if c.control.severity == "blocker"]

    @property
    def coverage_ratio(self) -> float:
        if not self.coverage:
            return 1.0
        return 1.0 - len(self.gaps) / len(self.coverage)

    def explain_gaps(self) -> list[str]:
        """Why each uncovered control was required, for the gap register."""
        return [
            f"{c.control_id} ({c.control.severity}): {c.control.title}. "
            f"Required because {c.control.why_applies()}. "
            f"Authority: {', '.join(c.control.citations)}."
            for c in self.gaps
        ]


def requirement_facts(
    *,
    statement: str,
    categories: list[str],
    risk_level: str = "low",
    jurisdictions: list[str] | None = None,
    domain: str = "ekyc_onboarding",
) -> dict[str, Any]:
    """Build the fact dictionary a rule evaluates against."""
    return {
        "statement": statement,
        "categories": categories,
        "risk_level": risk_level,
        "jurisdictions": jurisdictions or ["IN"],
        "domain": domain,
    }


def evaluate_pack(
    pack: RulePack,
    requirements: list[tuple[str, dict[str, Any]]],
    *,
    project_facts: dict[str, Any] | None = None,
) -> CoverageReport:
    """Assess one pack against `(ref, facts)` requirement pairs.

    `project_facts` decides which controls apply at all; a control that does not
    apply to this project is omitted rather than counted as a gap, because
    reporting inapplicable controls as failures trains reviewers to ignore the
    report.
    """
    scope = project_facts or requirement_facts(statement="", categories=[])

    report = CoverageReport(pack=pack.name, pack_version=pack.version)
    for control in pack.controls:
        if not control.applies_to(scope):
            continue
        satisfied_by = [ref for ref, facts in requirements if control.satisfied_by(facts)]
        report.coverage.append(ControlCoverage(control=control, satisfied_by=satisfied_by))
    return report


def evaluate(
    requirements: list[tuple[str, dict[str, Any]]],
    *,
    domain: str = "ekyc_onboarding",
    jurisdictions: list[str] | None = None,
    rules_dir: str | Path = DEFAULT_RULES_DIR,
) -> list[CoverageReport]:
    """Assess every applicable pack."""
    jurisdictions = jurisdictions or ["IN"]
    scope = requirement_facts(
        statement="", categories=[], domain=domain, jurisdictions=jurisdictions
    )

    reports: list[CoverageReport] = []
    for pack in load_all(rules_dir):
        if pack.domain != domain:
            continue
        if pack.jurisdiction not in jurisdictions and pack.jurisdiction != "GLOBAL":
            continue
        reports.append(evaluate_pack(pack, requirements, project_facts=scope))
    return reports


def controls_for_requirement(
    facts: dict[str, Any], *, rules_dir: str | Path = DEFAULT_RULES_DIR
) -> list[Control]:
    """Controls a single requirement appears to satisfy.

    Used to seed the compliance agent's candidate mappings deterministically,
    so the model is asked to *confirm and cite* a mapping rather than to invent
    one from nothing.
    """
    found: list[Control] = []
    for pack in load_all(rules_dir):
        if pack.domain != facts.get("domain"):
            continue
        found.extend(c for c in pack.controls if c.satisfied_by(facts))
    return found


__all__ = [
    "ControlCoverage",
    "CoverageReport",
    "controls_for_requirement",
    "evaluate",
    "evaluate_pack",
    "requirement_facts",
]
