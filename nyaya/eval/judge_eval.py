"""Does the LLM judge recover recall without importing false confirmations?

Measured against the same 49 labelled judgements as the NLI validator, so the
arms are directly comparable.

Four configurations:

    nli          the current validator alone
    judge        the LLM judge alone, on every pair
    cascade      NLI confirms -> accept; otherwise ask the judge
    strict       cascade, but the judge must also quote the obliging text

The cascade is the one that would actually ship: it pays for the model only on
the band NLI could not confirm, which is where the recall was being lost.

The number that decides this is **false confirmations**, not F1. Recovering
recall is worthless if it is bought by trusting wrong citations, because the
whole architecture exists to prevent exactly that.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from nyaya.agents.judge import judge
from nyaya.core.enums import EvidenceRelation
from nyaya.db import session_scope
from nyaya.eval.compliance_eval import ThresholdResult
from nyaya.eval.compliance_gold import JUDGEMENTS, CitationJudgement
from nyaya.retrieval import nli
from nyaya.retrieval.hybrid import load_context, resolve_citation

NLI_THRESHOLD = 0.20


@dataclass(slots=True)
class PairResult:
    """Both validators' opinions on one labelled pair."""

    judgement: CitationJudgement
    nli_entailment: float
    nli_confirms: bool
    judge_relation: EvidenceRelation
    judge_quote_verified: bool
    judge_reasoning: str

    @property
    def judge_confirms(self) -> bool:
        return self.judge_relation is EvidenceRelation.SUPPORTS

    @property
    def judge_confirms_strict(self) -> bool:
        return self.judge_confirms and self.judge_quote_verified

    @property
    def cascade(self) -> bool:
        return self.nli_confirms or self.judge_confirms

    @property
    def cascade_strict(self) -> bool:
        return self.nli_confirms or self.judge_confirms_strict


@dataclass(slots=True)
class JudgeReport:
    pairs: list[PairResult] = field(default_factory=list)
    seconds: float = 0.0

    def arm(self, name: str) -> ThresholdResult:
        picker = {
            "nli": lambda p: p.nli_confirms,
            "judge": lambda p: p.judge_confirms,
            "cascade": lambda p: p.cascade,
            "strict": lambda p: p.cascade_strict,
        }[name]
        result = ThresholdResult(threshold=NLI_THRESHOLD)
        for pair in self.pairs:
            predicted, actual = picker(pair), pair.judgement.supports
            if predicted and actual:
                result.tp += 1
            elif predicted and not actual:
                result.fp += 1
            elif not predicted and actual:
                result.fn += 1
            else:
                result.tn += 1
        return result


async def run() -> JudgeReport:
    report = JudgeReport()
    started = time.perf_counter()

    async with session_scope() as session:
        for item in JUDGEMENTS:
            clause = await resolve_citation(session, item.citation_key)
            if clause is None:
                continue
            await load_context(session, [clause])

            verdict = await nli.check(clause.contextual, item.requirement)
            decision = await judge(clause.contextual, item.requirement)

            report.pairs.append(
                PairResult(
                    judgement=item,
                    nli_entailment=verdict.entailment_score,
                    nli_confirms=verdict.entailment_score >= NLI_THRESHOLD,
                    judge_relation=decision.relation,
                    judge_quote_verified=decision.quote_verified,
                    judge_reasoning=decision.reasoning,
                )
            )

    report.seconds = time.perf_counter() - started
    return report


def render(report: JudgeReport) -> str:
    lines = [
        f"{len(report.pairs)} labelled pairs, {report.seconds:.0f}s "
        f"({report.seconds / max(len(report.pairs), 1):.1f}s/pair)",
        "",
        f"{'arm':<10}{'prec':>7}{'recall':>8}{'F1':>7}{'acc':>7}"
        f"{'TP':>5}{'FP':>5}{'FN':>5}{'TN':>5}",
        "-" * 60,
    ]
    for name in ("nli", "judge", "cascade", "strict"):
        a = report.arm(name)
        lines.append(
            f"{name:<10}{a.precision:>7.3f}{a.recall:>8.3f}{a.f1:>7.3f}{a.accuracy:>7.3f}"
            f"{a.tp:>5}{a.fp:>5}{a.fn:>5}{a.tn:>5}"
        )

    lines.append("")
    lines.append("recall recovered on the band NLI could not confirm:")
    band = [p for p in report.pairs if not p.nli_confirms]
    recovered = [p for p in band if p.judgement.supports and p.judge_confirms]
    imported = [p for p in band if not p.judgement.supports and p.judge_confirms]
    lines.append(f"  band size                      : {len(band)}")
    lines.append(f"  correct citations recovered    : {len(recovered)}")
    lines.append(f"  wrong citations newly confirmed: {len(imported)}  <- the cost")

    if imported:
        lines.append("")
        lines.append("false confirmations introduced by the judge:")
        for p in imported:
            lines.append(f"  {p.judgement.citation_key:<22} {p.judgement.note}")
            lines.append(f"      judge said: {p.judge_reasoning[:100]}")

    conflicts = [p for p in report.pairs if p.judge_relation is EvidenceRelation.CONTRADICTS]
    if conflicts:
        lines.append("")
        lines.append(f"clauses the judge reported as conflicting ({len(conflicts)}):")
        for p in conflicts:
            label = "correct citation" if p.judgement.supports else "wrong citation"
            lines.append(f"  {p.judgement.citation_key:<22} [{label}] {p.judge_reasoning[:80]}")
    return "\n".join(lines)


async def main() -> int:
    print(render(await run()))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
