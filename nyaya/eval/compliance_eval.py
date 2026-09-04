"""Measure the citation validator.

Two questions, answered separately because they have different answers:

1. **Can the validator distinguish a genuine citation from a plausible one?**
   Measured as precision/recall over labelled (requirement, clause) pairs. No
   language model is involved: the labelled citation is fed straight to the
   validator, isolating the validator's own discriminating power from the
   proposing model's accuracy.

2. **Is the confidence score calibrated?** A score of 0.8 should be right about
   80 % of the time. Reported as a reliability table and Expected Calibration
   Error, because an uncalibrated confidence is worse than none - it invites
   reviewers to trust exactly the wrong claims.

The threshold is chosen here rather than guessed. It was previously set from a
single separation observed on four clause pairs; this sweeps the full labelled
set and reports the trade-off.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from nyaya.core.confidence import ConfidenceComponents, fuse
from nyaya.db import session_scope
from nyaya.eval.compliance_gold import JUDGEMENTS, CitationJudgement
from nyaya.retrieval import nli
from nyaya.retrieval.hybrid import load_context, resolve_citation

SWEEP = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.55, 0.60, 0.70, 0.80, 0.90)
BINS = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))


@dataclass(slots=True)
class Scored:
    """One judgement with the validator's measured entailment score."""

    judgement: CitationJudgement
    entailment: float
    resolved: bool
    relation: str


@dataclass(slots=True)
class ThresholdResult:
    threshold: float
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        total = self.tp + self.fp + self.tn + self.fn
        return (self.tp + self.tn) / total if total else 0.0


@dataclass(slots=True)
class CalibrationBin:
    low: float
    high: float
    count: int = 0
    correct: int = 0
    confidence_sum: float = 0.0

    @property
    def accuracy(self) -> float:
        return self.correct / self.count if self.count else 0.0

    @property
    def mean_confidence(self) -> float:
        return self.confidence_sum / self.count if self.count else 0.0

    @property
    def gap(self) -> float:
        return abs(self.mean_confidence - self.accuracy)


@dataclass(slots=True)
class EvalReport:
    scored: list[Scored] = field(default_factory=list)
    thresholds: list[ThresholdResult] = field(default_factory=list)
    bins: list[CalibrationBin] = field(default_factory=list)
    ece: float = 0.0
    unresolved: list[str] = field(default_factory=list)

    def best(self, by: str = "f1") -> ThresholdResult:
        return max(self.thresholds, key=lambda t: getattr(t, by))


async def score_all() -> tuple[list[Scored], list[str]]:
    """Run the validator over every labelled pair."""
    scored: list[Scored] = []
    unresolved: list[str] = []

    async with session_scope() as session:
        for judgement in JUDGEMENTS:
            clause = await resolve_citation(session, judgement.citation_key)
            if clause is None:
                unresolved.append(judgement.citation_key)
                continue
            await load_context(session, [clause])
            verdict = await nli.check(clause.contextual, judgement.requirement)
            scored.append(
                Scored(
                    judgement=judgement,
                    entailment=verdict.entailment_score,
                    resolved=True,
                    relation=verdict.relation.value,
                )
            )
    return scored, unresolved


def sweep(scored: list[Scored]) -> list[ThresholdResult]:
    """Precision/recall across candidate entailment thresholds."""
    results: list[ThresholdResult] = []
    for threshold in SWEEP:
        result = ThresholdResult(threshold=threshold)
        for item in scored:
            predicted = item.entailment >= threshold
            actual = item.judgement.supports
            if predicted and actual:
                result.tp += 1
            elif predicted and not actual:
                result.fp += 1
            elif not predicted and actual:
                result.fn += 1
            else:
                result.tn += 1
        results.append(result)
    return results


def calibrate(scored: list[Scored]) -> tuple[list[CalibrationBin], float]:
    """Reliability bins and Expected Calibration Error.

    Calibration is measured on the claim the score actually makes - *this
    citation supports the requirement* - against whether it does. An earlier
    version binned by "was the accept/reject decision correct", which is a
    different quantity and produced a misleading ECE of 0.225: a correctly
    rejected citation scores low confidence *because* it is wrong, so counting
    that as an underconfident success inflates the apparent miscalibration.

    ECE is the count-weighted mean gap between stated confidence and observed
    frequency. It says whether a score can be acted on: a well-separated but
    badly calibrated model still misleads a reviewer deciding what to check.
    """
    bins = [CalibrationBin(low, high) for low, high in BINS]

    for item in scored:
        confidence = fuse(
            ConfidenceComponents(
                retrieval=0.8,  # held constant: the clause was supplied, not retrieved
                entailment=item.entailment,
                validation=1.0 if item.resolved else 0.0,
                consistency=0.75,
            )
        ).score

        for bucket in bins:
            if bucket.low <= confidence < bucket.high or (bucket.high == 1.0 and confidence == 1.0):
                bucket.count += 1
                bucket.confidence_sum += confidence
                # The event being predicted is "this citation is genuine".
                bucket.correct += int(item.judgement.supports)
                break

    total = sum(b.count for b in bins)
    ece = sum(b.count / total * b.gap for b in bins if b.count) if total else 0.0
    return bins, ece


async def evaluate() -> EvalReport:
    scored, unresolved = await score_all()
    thresholds = sweep(scored)
    report = EvalReport(scored=scored, thresholds=thresholds, unresolved=unresolved)
    report.bins, report.ece = calibrate(scored)
    return report


def render(report: EvalReport) -> str:
    lines: list[str] = []
    pos = sum(s.judgement.supports for s in report.scored)
    neg = len(report.scored) - pos
    lines.append(
        f"citation validation: {len(report.scored)} pairs ({pos} positive, {neg} negative)"
    )
    if report.unresolved:
        lines.append(f"UNRESOLVED citation keys: {report.unresolved}")
    lines.append("")

    lines.append(
        f"{'thresh':>7} {'prec':>6} {'recall':>7} {'F1':>6} {'acc':>6} "
        f"{'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4}"
    )
    lines.append("-" * 60)
    for t in report.thresholds:
        lines.append(
            f"{t.threshold:>7.2f} {t.precision:>6.3f} {t.recall:>7.3f} {t.f1:>6.3f} "
            f"{t.accuracy:>6.3f} {t.tp:>4} {t.fp:>4} {t.fn:>4} {t.tn:>4}"
        )

    best = report.best("f1")
    lines.append("")
    lines.append(
        f"best F1 at threshold {best.threshold:.2f}: "
        f"precision={best.precision:.3f} recall={best.recall:.3f} F1={best.f1:.3f}"
    )

    # How the three-way outcome actually lands: what fraction of correct
    # citations is auto-confirmed, versus routed to a human rather than lost.
    confirmed_pos = sum(
        1 for s in report.scored if s.judgement.supports and s.entailment >= best.threshold
    )
    total_pos = sum(1 for s in report.scored if s.judgement.supports)
    review_pos = total_pos - confirmed_pos
    confirmed_neg = sum(
        1 for s in report.scored if not s.judgement.supports and s.entailment >= best.threshold
    )
    lines.append("")
    lines.append("three-way outcome at the selected threshold:")
    lines.append(f"  auto-confirmed correct citations : {confirmed_pos}/{total_pos}")
    lines.append(f"  correct citations sent to review : {review_pos}/{total_pos} (not discarded)")
    lines.append(f"  wrong citations auto-confirmed   : {confirmed_neg} (the number that matters)")

    lines.append("")
    lines.append("calibration (reliability of 'this citation is genuine'):")
    lines.append(f"{'bin':>12} {'n':>4} {'mean conf':>10} {'accuracy':>9} {'gap':>7}")
    for b in report.bins:
        if b.count:
            lines.append(
                f"  [{b.low:.1f},{b.high:.1f}) {b.count:>4} {b.mean_confidence:>10.3f} "
                f"{b.accuracy:>9.3f} {b.gap:>7.3f}"
            )
    lines.append(f"Expected Calibration Error: {report.ece:.3f}")

    false_accepts = [
        s for s in report.scored if s.entailment >= best.threshold and not s.judgement.supports
    ]
    if false_accepts:
        lines.append("")
        lines.append(f"FALSE CONFIRMATIONS ({len(false_accepts)}) - wrong citations trusted:")
        for s in false_accepts:
            lines.append(
                f"  {s.judgement.citation_key:<22} entail={s.entailment:.3f}  {s.judgement.note}"
            )

    unconfirmed = [
        s for s in report.scored if s.entailment < best.threshold and s.judgement.supports
    ]
    if unconfirmed:
        lines.append("")
        lines.append(
            f"unconfirmed correct citations ({len(unconfirmed)}) - routed to review, not lost:"
        )
        for s in unconfirmed:
            lines.append(
                f"  {s.judgement.citation_key:<22} entail={s.entailment:.3f}  {s.judgement.note}"
            )
    return "\n".join(lines)


async def main() -> int:
    print(render(await evaluate()))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
