"""The extraction agent.

Converts a stakeholder statement or document span into structured, testable
requirements.

The design point is the **repair loop**. The model proposes; deterministic
linters judge; failures are fed back as named defects with named remedies. This
matters because the earlier measurement showed the model would happily echo a
stakeholder's sentence back as a "requirement" - output that is well-formed
JSON, passes schema validation, and is useless. Schema validation checks shape;
only the linters check whether the content is a requirement at all.

Repair is bounded. If the model cannot produce a testable statement in two
attempts, the requirement is kept **with its defects recorded** rather than
discarded or silently accepted. A defective requirement that a human can see is
worth more than a missing one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from nyaya.agents.prompts import build_extraction_messages, build_repair_message
from nyaya.agents.quality import consistency, ears, lexicon
from nyaya.agents.quality.quantities import unsupported_quantities
from nyaya.agents.schemas import (
    ExtractedRequirement,
    ExtractionContext,
    ExtractionOutput,
    RepairOutput,
)
from nyaya.config import ModelRole
from nyaya.core.enums import DefectType, Severity
from nyaya.llm import Message, get_provider

MAX_REPAIR_ATTEMPTS = 2


@dataclass(slots=True)
class RequirementDefect:
    """A quality problem found in an extracted requirement."""

    defect_type: DefectType
    severity: Severity
    detail: str
    detector: str
    span_start: int | None = None
    span_end: int | None = None


@dataclass(slots=True)
class AnalysedRequirement:
    """An extracted requirement together with what the linters found in it."""

    requirement: ExtractedRequirement
    defects: list[RequirementDefect] = field(default_factory=list)
    ears_pattern: str = "none"
    repair_attempts: int = 0

    @property
    def is_testable(self) -> bool:
        return not any(d.severity in {Severity.MAJOR, Severity.BLOCKER} for d in self.defects)


@dataclass(slots=True)
class ExtractionResult:
    requirements: list[AnalysedRequirement] = field(default_factory=list)
    unclear: list[str] = field(default_factory=list)
    model: str = ""
    repair_rounds: int = 0

    @property
    def testable_fraction(self) -> float:
        if not self.requirements:
            return 0.0
        return sum(r.is_testable for r in self.requirements) / len(self.requirements)


def inspect(requirement: ExtractedRequirement) -> tuple[list[RequirementDefect], str]:
    """Run every deterministic check over one requirement."""
    defects: list[RequirementDefect] = []
    statement = requirement.statement

    analysis = ears.analyse(statement)
    for issue in analysis.issues:
        defects.append(
            RequirementDefect(
                defect_type=(
                    DefectType.INCONSISTENCY if "compound" in issue else DefectType.UNTESTABLE
                ),
                severity=Severity.MAJOR,
                detail=issue,
                detector="ears_template",
            )
        )

    for finding in lexicon.scan(statement):
        defects.append(
            RequirementDefect(
                defect_type=DefectType.AMBIGUITY,
                severity=finding.severity,
                detail=f"{finding.term!r}: {finding.remedy}",
                detector="weak_word_lexicon",
                span_start=finding.start,
                span_end=finding.end,
            )
        )

    if not requirement.acceptance_criteria:
        defects.append(
            RequirementDefect(
                defect_type=DefectType.UNTESTABLE,
                severity=Severity.MAJOR,
                detail="no acceptance criteria: nothing states how conformance is demonstrated",
                detector="completeness_check",
            )
        )

    if not requirement.quoted_source.strip():
        defects.append(
            RequirementDefect(
                defect_type=DefectType.MISSING_SOURCE,
                severity=Severity.MAJOR,
                detail="no quoted source: the requirement cannot be traced to a stakeholder statement",
                detector="provenance_check",
            )
        )

    return defects, analysis.pattern.value


def verify_quantities(
    requirement: ExtractedRequirement, source_text: str
) -> list[RequirementDefect]:
    """Flag thresholds the requirement asserts but the source never supplied.

    Guards a failure the repair loop *causes*. Pressed to remove vagueness from
    "make onboarding as quick as possible", the model produced "no more than
    three distinct user actions" - a number the stakeholder never gave. The
    fabricated version is more dangerous than the vague original: it reads as
    precise, satisfies every ambiguity check, and would be baselined and built.

    An unsupported quantity is not necessarily wrong, but it is an *assumption*
    rather than a requirement, and it must be visible as one.
    """
    return [
        RequirementDefect(
            defect_type=DefectType.MISSING_SOURCE,
            severity=Severity.MAJOR,
            detail=(
                f"unsupported quantity {quantity.raw!r}: the source text does not "
                f"state this value. Remove it, or record it as an explicit "
                f"assumption and raise the missing value in `unclear`."
            ),
            detector="quantity_provenance",
            span_start=quantity.start,
            span_end=quantity.end,
        )
        for quantity in unsupported_quantities(requirement.statement, source_text)
    ]


def verify_provenance(
    requirement: ExtractedRequirement, source_text: str
) -> RequirementDefect | None:
    """Check that `quoted_source` actually appears in the input.

    A quotation the model composed rather than copied is a fabricated provenance
    link - the most damaging failure available here, because it looks like
    evidence. Compared on normalised whitespace, since models reflow text.
    """
    quoted = " ".join(requirement.quoted_source.split()).lower()
    haystack = " ".join(source_text.split()).lower()
    if not quoted:
        return None
    if quoted in haystack:
        return None
    return RequirementDefect(
        defect_type=DefectType.MISSING_SOURCE,
        severity=Severity.MAJOR,
        detail=(
            f"quoted source not found in the input text: {requirement.quoted_source!r}. "
            "The quotation must be copied verbatim, not paraphrased."
        ),
        detector="provenance_check",
    )


async def extract(
    text: str,
    *,
    context: ExtractionContext | None = None,
    repair: bool = True,
    role: ModelRole = ModelRole.REASONING,
) -> ExtractionResult:
    """Extract testable requirements from `text`."""
    context = context or ExtractionContext()
    provider = get_provider(role)

    turns = build_extraction_messages(text, context)
    messages = [Message(role=r, content=c) for r, c in turns]

    completion = await provider.complete_structured(messages, ExtractionOutput)
    output = completion.value

    requirements = list(output.requirements)
    unclear = list(output.unclear)
    analysed = [_analyse(r, text) for r in requirements]
    rounds = 0

    if repair:
        for _ in range(MAX_REPAIR_ATTEMPTS):
            # `flagged` keeps the position of each problem, so a returned
            # rewrite can be matched back to the requirement it belongs to.
            problems, flagged = _problem_list(analysed)
            if not problems:
                break
            rounds += 1

            repair_messages = [
                *messages,
                Message(role="assistant", content=completion.completion.text),
                Message(role="user", content=build_repair_message(problems)),
            ]
            repair_completion = await provider.complete_structured(
                repair_messages, RepairOutput
            )

            # Splice, never replace.
            #
            # This step used to hand back a whole ExtractionOutput and overwrite
            # the previous one. The instruction says "rewrite only the statements
            # listed below", so a model that followed it returned only those -
            # and a thirteen-requirement extraction silently became two. The
            # repair schema can no longer express a set, and the merge below only
            # ever rewrites a statement in place.
            applied = 0
            for fix in repair_completion.value.repairs:
                position = fix.index - 1
                if not 0 <= position < len(flagged):
                    continue
                target = flagged[position]
                cleaned = _clean_repair(
                    fix.statement, requirements[target].statement
                )
                if cleaned is None:
                    continue
                requirements[target] = requirements[target].model_copy(
                    update={"statement": cleaned}
                )
                applied += 1

            unclear.extend(
                question
                for question in repair_completion.value.unclear
                if question not in unclear
            )

            if not applied:
                # Nothing changed, so another identical round would not either.
                break

            analysed = [_analyse(r, text) for r in requirements]
            for item in analysed:
                item.repair_attempts = rounds

    # Cross-requirement checks last, because they are properties of the set and
    # the set is only final once repair has stopped changing it.
    _attach_set_defects(analysed)

    return ExtractionResult(
        requirements=analysed,
        unclear=unclear,
        model=f"{provider.name}:{provider.model}",
        repair_rounds=rounds,
    )


_SET_DEFECT_TYPE = {
    "duplication": DefectType.DUPLICATION,
    "conflict": DefectType.CONFLICTING_EXPECTATION,
    "incompleteness": DefectType.INCOMPLETENESS,
}

# A conflict is a stakeholder decision and blocks; a duplicate wastes review
# time but nothing downstream is wrong; an unverified quantity is a gap in the
# test plan rather than in the requirement.
_SET_DEFECT_SEVERITY = {
    "duplication": Severity.MAJOR,
    "conflict": Severity.BLOCKER,
    "incompleteness": Severity.MAJOR,
}


def _attach_set_defects(analysed: list[AnalysedRequirement]) -> None:
    """Run the cross-requirement checks and hang them on the right statement.

    These are not sent to the repair loop. A duplicate cannot be fixed by
    rewriting one of the pair - deleting one is a decision about scope - and a
    conflict is two stakeholders disagreeing, which is not a defect in a
    sentence. Both belong in front of a person.
    """
    statements = [item.requirement.statement for item in analysed]
    criteria = [list(item.requirement.acceptance_criteria) for item in analysed]

    for found in consistency.analyse_set(statements, criteria):
        analysed[found.left].defects.append(
            RequirementDefect(
                defect_type=_SET_DEFECT_TYPE[found.kind],
                severity=_SET_DEFECT_SEVERITY[found.kind],
                detail=found.detail,
                detector=f"requirement_set.{found.kind}",
            )
        )


def _analyse(requirement: ExtractedRequirement, source_text: str) -> AnalysedRequirement:
    defects, pattern = inspect(requirement)
    provenance = verify_provenance(requirement, source_text)
    if provenance is not None:
        defects.append(provenance)
    defects.extend(verify_quantities(requirement, source_text))
    return AnalysedRequirement(requirement=requirement, defects=defects, ears_pattern=pattern)


# A requirement is one sentence containing exactly one "shall". Repairs that
# run past that are the model narrating its own fix - "... The quoted source for
# this requirement is: ..." - appended to an otherwise correct statement.
_SENTENCE = re.compile(r"^(.*?[.!?])(?:\s|$)", re.DOTALL)
_META = re.compile(
    r"\b(quoted source|unclear|assumption|rationale|this requirement is|"
    r"the reason|problem \d)\b",
    re.IGNORECASE,
)


def _clean_repair(statement: str, original: str) -> str | None:
    """Trim a repaired statement to the obligation, or reject it.

    The repair prompt asks for the statement alone and mostly gets it, but a
    model that has just been told *why* a sentence was wrong has a strong pull
    towards explaining itself inside the answer. Instruction alone did not stop
    it, so this is the deterministic half: keep the first sentence, and if what
    remains is not a requirement, keep the original.

    Rejecting is safe. The original statement is still flagged and still shown
    to a reviewer with its defect attached; a mangled statement that *looks*
    repaired is the worse outcome, because the defect is gone from the record
    while the problem is not.
    """
    candidate = statement.strip()

    match = _SENTENCE.match(candidate)
    if match:
        candidate = match.group(1).strip()

    if _META.search(candidate) or "shall" not in candidate.lower():
        return None
    # A repair that changed nothing is not a repair.
    return candidate if candidate != original.strip() else None


def _problem_list(
    analysed: list[AnalysedRequirement],
) -> tuple[list[str], list[int]]:
    """Blocking defects as repair instructions, with the position of each.

    The positions are what make the repair splice-able: problem *n* in the
    rendered list belongs to requirement `flagged[n - 1]`, so a rewrite can be
    put back exactly where it came from instead of replacing the whole set.
    """
    problems: list[str] = []
    flagged: list[int] = []
    for position, item in enumerate(analysed):
        blocking_defects = [
            d for d in item.defects if d.severity in {Severity.MAJOR, Severity.BLOCKER}
        ]
        if not blocking_defects:
            continue
        details = "; ".join(d.detail for d in blocking_defects)
        problems.append(f'Statement "{item.requirement.statement}" — {details}')
        flagged.append(position)
    return problems, flagged


def new_ref(domain: str, index: int) -> str:
    """Mint a human-facing requirement reference, e.g. `FR-KYC-001`."""
    tag = {"ekyc_onboarding": "KYC", "loan_origination": "LOAN"}.get(domain, "GEN")
    return f"FR-{tag}-{index:03d}"


__all__ = [
    "MAX_REPAIR_ATTEMPTS",
    "AnalysedRequirement",
    "ExtractionResult",
    "RequirementDefect",
    "extract",
    "inspect",
    "new_ref",
    "verify_provenance",
    "verify_quantities",
]
