"""A small declarative rule language for mandatory compliance controls.

Rules live in versioned YAML under `rules/`, not in code. Three reasons that
matters here:

1. **They are diffable.** A regulatory change shows up as a reviewable line
   diff, and `git blame` says who changed a control and when.
2. **They are explainable.** The evaluator records which condition matched, so a
   gap report can say *why* a control was required rather than merely asserting
   it. An unexplained compliance finding is not actionable.
3. **A compliance officer can read them.** Rules encode legal obligations; the
   people accountable for those obligations must be able to audit them without
   reading Python.

Deliberately not a general expression language. It supports exactly the
predicates the compliance question needs, so a rule cannot express something the
evaluator cannot explain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class RuleError(ValueError):
    """A rule pack is malformed."""


@dataclass(frozen=True, slots=True)
class Condition:
    """One predicate over a requirement.

    Exactly one field is populated. Combined with the others in its rule by
    logical AND; alternatives are expressed as separate rules, which keeps every
    matched condition independently reportable.
    """

    kind: str
    value: Any

    def evaluate(self, facts: dict[str, Any]) -> bool:
        match self.kind:
            case "category_any":
                return bool(set(facts.get("categories", [])) & set(self.value))
            case "category_all":
                return set(self.value).issubset(set(facts.get("categories", [])))
            case "jurisdiction_any":
                return bool(set(facts.get("jurisdictions", [])) & set(self.value))
            case "text_matches":
                return bool(re.search(self.value, facts.get("statement", ""), re.I))
            case "text_absent":
                return not re.search(self.value, facts.get("statement", ""), re.I)
            case "risk_at_least":
                order = ["low", "medium", "high", "critical"]
                actual = facts.get("risk_level", "low")
                return order.index(actual) >= order.index(self.value)
            case "domain_is":
                return facts.get("domain") in set(self.value)
            case unknown:
                raise RuleError(f"Unknown condition kind {unknown!r}")

    def describe(self) -> str:
        """Human-readable form, used in gap explanations."""
        return {
            "category_any": f"category is any of {self.value}",
            "category_all": f"category includes all of {self.value}",
            "jurisdiction_any": f"jurisdiction is any of {self.value}",
            "text_matches": f"statement matches /{self.value}/",
            "text_absent": f"statement does not mention /{self.value}/",
            "risk_at_least": f"risk level is at least {self.value}",
            "domain_is": f"domain is one of {self.value}",
        }.get(self.kind, f"{self.kind}={self.value}")


@dataclass(frozen=True, slots=True)
class Control:
    """A mandatory control, and the conditions under which it applies."""

    control_id: str
    title: str
    description: str
    citations: tuple[str, ...]
    """Clause keys establishing the control. A control with no citation cannot
    be traced to an authority and is rejected at load time."""

    applies_when: tuple[Condition, ...]
    satisfied_when: tuple[Condition, ...]
    """What a requirement must look like to satisfy this control. Kept separate
    from `applies_when`, because "this control is required here" and "this
    requirement discharges it" are different questions."""

    severity: str = "major"
    jurisdictions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def applies_to(self, facts: dict[str, Any]) -> bool:
        return all(c.evaluate(facts) for c in self.applies_when)

    def satisfied_by(self, facts: dict[str, Any]) -> bool:
        return bool(self.satisfied_when) and all(c.evaluate(facts) for c in self.satisfied_when)

    def why_applies(self) -> str:
        return " AND ".join(c.describe() for c in self.applies_when) or "always"


@dataclass(slots=True)
class RulePack:
    """A versioned collection of controls."""

    name: str
    version: str
    jurisdiction: str
    domain: str
    controls: list[Control] = field(default_factory=list)
    source: str = ""

    def by_id(self) -> dict[str, Control]:
        return {c.control_id: c for c in self.controls}


def _conditions(raw: Any, where: str) -> tuple[Condition, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise RuleError(f"{where}: expected a list of conditions, got {type(raw).__name__}")
    out: list[Condition] = []
    for entry in raw:
        if not isinstance(entry, dict) or len(entry) != 1:
            raise RuleError(f"{where}: each condition must be a single-key mapping")
        ((kind, value),) = entry.items()
        condition = Condition(kind=kind, value=value)
        # Fail at load time, not at first evaluation, so a typo in a rule pack
        # surfaces on startup rather than mid-assessment.
        condition.evaluate({"categories": [], "jurisdictions": [], "statement": ""})
        out.append(condition)
    return tuple(out)


def load_pack(path: str | Path) -> RulePack:
    """Load and validate one rule pack."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuleError(f"{path}: expected a mapping at the top level")

    for required in ("name", "version", "jurisdiction", "domain", "controls"):
        if required not in data:
            raise RuleError(f"{path}: missing required key {required!r}")

    controls: list[Control] = []
    for index, raw in enumerate(data["controls"]):
        where = f"{path}:controls[{index}]"
        for required in ("id", "title", "citations"):
            if required not in raw:
                raise RuleError(f"{where}: missing required key {required!r}")
        if not raw["citations"]:
            raise RuleError(
                f"{where}: control {raw['id']!r} has no citations. A control that "
                f"cannot be traced to an authority must not be enforced."
            )
        controls.append(
            Control(
                control_id=raw["id"],
                title=raw["title"],
                description=raw.get("description", ""),
                citations=tuple(raw["citations"]),
                applies_when=_conditions(raw.get("applies_when"), where),
                satisfied_when=_conditions(raw.get("satisfied_when"), where),
                severity=raw.get("severity", "major"),
                jurisdictions=tuple(raw.get("jurisdictions", [])),
                tags=tuple(raw.get("tags", [])),
            )
        )

    return RulePack(
        name=data["name"],
        version=str(data["version"]),
        jurisdiction=data["jurisdiction"],
        domain=data["domain"],
        controls=controls,
        source=str(path),
    )


def load_all(directory: str | Path) -> list[RulePack]:
    """Load every rule pack in a directory, sorted for deterministic ordering."""
    return [load_pack(p) for p in sorted(Path(directory).glob("*.yaml"))]


__all__ = ["Condition", "Control", "RuleError", "RulePack", "load_all", "load_pack"]
