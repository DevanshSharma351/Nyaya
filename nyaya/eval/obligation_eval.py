"""Measure the two-signal obligation checker against the labelled set.

Reports the tier composition, because the tiers are the actual product: what
matters is not one accuracy figure but whether the auto-accept tier is clean
enough to accept unreviewed, and whether the review queue is ordered usefully.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from nyaya.db import session_scope
from nyaya.eval.compliance_gold import JUDGEMENTS
from nyaya.retrieval.hybrid import load_context, resolve_citation
from nyaya.retrieval.obligation import ObligationTier, check_sync


@dataclass(slots=True)
class TierStats:
    tier: ObligationTier
    genuine: int = 0
    wrong: int = 0
    examples: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.genuine + self.wrong

    @property
    def purity(self) -> float:
        return self.genuine / self.total if self.total else 0.0


async def evaluate() -> dict[ObligationTier, TierStats]:
    stats = {tier: TierStats(tier=tier) for tier in ObligationTier}

    async with session_scope() as session:
        for judgement in JUDGEMENTS:
            clause = await resolve_citation(session, judgement.citation_key)
            if clause is None:
                continue
            await load_context(session, [clause])
            result = check_sync(clause, judgement.requirement)

            bucket = stats[result.tier]
            if judgement.supports:
                bucket.genuine += 1
            else:
                bucket.wrong += 1
                if result.tier is ObligationTier.CONFIRMED:
                    bucket.examples.append(
                        f"{judgement.citation_key} ({judgement.note})"
                    )
    return stats


def render(stats: dict[ObligationTier, TierStats]) -> str:
    total_genuine = sum(s.genuine for s in stats.values())
    lines = [
        f"{'tier':<14}{'n':>4}{'genuine':>9}{'wrong':>7}{'purity':>8}",
        "-" * 44,
    ]
    for tier in (
        ObligationTier.CONFIRMED,
        ObligationTier.LIKELY,
        ObligationTier.UNCONFIRMED,
        ObligationTier.CONFLICTING,
    ):
        s = stats[tier]
        if s.total:
            lines.append(
                f"{tier.value:<14}{s.total:>4}{s.genuine:>9}{s.wrong:>7}{s.purity:>8.3f}"
            )

    confirmed = stats[ObligationTier.CONFIRMED]
    lines.append("")
    lines.append(
        f"auto-accepted: {confirmed.genuine}/{total_genuine} genuine citations, "
        f"{confirmed.wrong} wrong"
    )
    if confirmed.wrong:
        lines.append("FALSE CONFIRMATIONS in the auto-accept tier:")
        lines += [f"  {e}" for e in confirmed.examples]
    else:
        lines.append(
            "no false confirmations in the auto-accept tier - the property the "
            "gate exists to provide"
        )
    return "\n".join(lines)


async def main() -> int:
    print(render(await evaluate()))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
