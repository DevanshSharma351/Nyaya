"""Reading project characteristics out of a brief.

The factor vector used to be derived only from the extracted requirements -
what share are regulatory, what share are high risk, how many questions were
left open. That works when the input is a list of obligations. It fails
completely when the input is what section 13 of the brief actually describes: a
statement of project characteristics.

The failure is easy to see on a real example. A brief saying the team is highly
skilled, the deadline is non-negotiable, stakeholders attend weekly workshops,
the requirements decompose into independent services and the company intends to
build on pre-tested templates is a textbook case for rapid application
development. Extracting requirements from it yields four odd sentences about
microservice templates, and a derivation that reads only their categories
cannot see the deadline, the team, the stakeholders or the reuse at all. Every
one of those is a named factor that the ranking would have used.

So the brief is also read directly. Everything here is a phrase match, and each
one records the words it matched, because a factor that moves for reasons
nobody can inspect is worse than a factor left at its default - an architect
challenging the recommendation has to be able to see why the engine believed
what it believed.

A stated characteristic outranks a floor. The floors in `derive` exist to stop
an *incomplete* brief arguing for lighter process; a brief that says plainly
that failure consequences are low is not incomplete, it is informative.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class Signal:
    """One factor reading, and every phrase that produced it."""

    factor: str
    value: float
    phrases: list[str]
    reasons: list[str]

    @property
    def contested(self) -> bool:
        """Whether the brief said two different things about this factor."""
        return len(self.reasons) > 1


@dataclass(slots=True)
class Cue:
    factor: str
    value: float
    reason: str
    pattern: re.Pattern[str]


def _cue(factor: str, value: float, reason: str, *alternatives: str) -> Cue:
    return Cue(
        factor=factor,
        value=value,
        reason=reason,
        pattern=re.compile("|".join(f"(?:{a})" for a in alternatives), re.IGNORECASE),
    )


# Order is not significant. Where several cues touch one factor they are
# averaged rather than resolved by precedence - see `read`.
CUES: tuple[Cue, ...] = (
    # --- schedule -----------------------------------------------------------
    _cue(
        "schedule_pressure", 0.95,
        "the deadline is stated as fixed and not negotiable",
        r"non-?negotiable deadline", r"hard deadline", r"strict[^.]{0,30}deadline",
        r"must (?:be )?(?:launch|roll(?:ed)? out|deliver)[^.]{0,40}within \d+",
    ),
    _cue(
        "schedule_pressure", 0.8,
        "a delivery window is given in days or weeks",
        r"within \d+(?:\s*(?:to|-)\s*\d+)?\s*(?:days?|weeks?)",
        r"time.to.market", r"ahead of[^.]{0,30}(?:surge|season|peak)",
    ),
    _cue(
        "schedule_pressure", 0.25,
        "the schedule is described as flexible",
        r"no (?:fixed|hard) deadline", r"timeline is flexible", r"no time pressure",
    ),
    # --- team ---------------------------------------------------------------
    _cue(
        "team_experience", 0.9,
        "the team is described as experienced or specialist",
        r"highly skilled", r"well.versed", r"experienced (?:team|squad|engineers?)",
        r"senior (?:team|engineers?)", r"expert(?:s)? in", r"specialist team",
    ),
    _cue(
        "team_experience", 0.25,
        "the team is described as new or unfamiliar with the domain",
        r"junior team", r"inexperienced", r"new to the domain", r"first project",
        r"unfamiliar with",
    ),
    # --- stakeholders -------------------------------------------------------
    _cue(
        "stakeholder_availability", 0.95,
        "stakeholders are committed to regular sessions",
        r"weekly (?:requirement )?workshops?", r"fully committed to attend",
        r"continuous[^.]{0,40}(?:workshops?|review sessions?)",
        r"co-?located", r"available (?:daily|throughout)",
    ),
    _cue(
        "stakeholder_availability", 0.2,
        "stakeholders are described as hard to reach",
        r"stakeholders? (?:are )?(?:rarely|hard to|difficult to) (?:available|reach)",
        r"limited stakeholder (?:time|availability)",
    ),
    # --- requirements -------------------------------------------------------
    _cue(
        "requirement_stability", 0.8,
        "the requirements are described as understood and settled",
        r"(?:largely|well|clearly) understood", r"requirements? are stable",
        r"clearly (?:defined|specified)", r"scope is (?:fixed|agreed)",
    ),
    _cue(
        "requirement_stability", 0.2,
        "the requirements are described as unsettled",
        r"requirements? (?:are |remain )?(?:unclear|evolving|in flux)",
        r"likely to change", r"not yet (?:known|defined|understood)",
        r"exploratory",
    ),
    _cue(
        "change_frequency", 0.85,
        "change is expected to be frequent",
        r"(?:rules|requirements?|regulations?) keep (?:moving|changing)",
        r"frequent(?:ly)? chang", r"rapidly evolving", r"ship(?:ping)? (?:weekly|daily)",
    ),
    # --- shape of the system ------------------------------------------------
    _cue(
        "project_complexity", 0.3,
        "the work decomposes into independent parts and reuses existing components",
        # Reuse is not itself a factor, and this is where it belongs: a project
        # assembling pre-tested components is building less, whatever its
        # ambition. Paired with decomposition so that reuse alone - common in
        # large programmes too - does not pull complexity down on its own.
        #
        # The window spans sentences deliberately. A brief states the
        # decomposition and the reuse intent in separate sentences far more
        # often than in one, and an earlier version using [^.] matched neither.
        r"(?:decoupled|independent|modular)[\s\S]{0,60}services?"
        r"[\s\S]{0,400}(?:templates?|code.generation|reuse|pre-?tested)",
        r"(?:templates?|code.generation|CASE tools?|pre-?tested)"
        r"[\s\S]{0,400}(?:decoupled|independent|modular)",
    ),
    _cue(
        "project_complexity", 0.9,
        "the programme spans many systems or teams",
        r"multiple teams", r"programme of work", r"across (?:many|several) systems",
        r"nationwide[^.]{0,40}(?:infrastructure|platform)", r"enterprise-wide",
    ),
    _cue(
        "legacy_dependence", 0.85,
        "existing systems must be integrated or migrated",
        r"legacy", r"existing systems?", r"migrat(?:e|ion)", r"modernis|moderniz",
        r"integrate with[^.]{0,30}(?:existing|current)",
    ),
    _cue(
        "continuous_delivery_need", 0.85,
        "delivery is expected to be continuous",
        r"continuous (?:delivery|deployment)", r"release (?:weekly|daily|continuously)",
        r"ship (?:changes )?weekly",
    ),
    # --- risk ---------------------------------------------------------------
    _cue(
        "regulatory_criticality", 0.9,
        "the brief names regulation or compliance obligations",
        r"regulat(?:or|ion|ed)", r"compliance", r"\bKYC\b", r"\bAML\b", r"\bGDPR\b",
        r"sanctions", r"audit(?:ed|ing)? requirement", r"supervis(?:or|ion)",
    ),
    _cue(
        "security_risk", 0.85,
        "the brief names security or fraud concerns",
        r"security", r"fraud", r"encrypt", r"authenticat", r"sensitive (?:data|information)",
        r"personal data",
    ),
    _cue(
        "failure_consequence", 0.9,
        "failure is described as costly or customer-affecting",
        r"customer (?:money|funds)", r"financial loss", r"outage",
        r"(?:mission|business).critical", r"reputational",
    ),
    _cue(
        "failure_consequence", 0.2,
        "the work is described as low stakes",
        r"internal (?:tool|dashboard|prototype)", r"proof of concept",
        r"low[- ]risk", r"experiment",
    ),
    _cue(
        "documentation_need", 0.9,
        "formal documentation or sign-off is required",
        r"formal (?:sign-?off|documentation|approval)", r"audit trail",
        r"documented evidence", r"regulatory submission",
    ),
    _cue(
        "formal_verification_need", 0.9,
        "formal verification or certification is required",
        r"formal verification", r"certif(?:y|ication)", r"mathematical(?:ly)? prov",
        r"safety case",
    ),
)


def read(brief: str) -> list[Signal]:
    """Every project characteristic the brief states outright.

    Where several cues touch the same factor their values are averaged and
    every matching phrase is kept. Resolving by precedence instead let the cue
    ordering decide a real question: this brief describes a "nationwide
    depot-routing infrastructure" *and* work that decomposes into independent
    services built from pre-tested templates, which are genuinely opposing
    evidence about complexity. Whichever cue happened to be listed first won,
    and the other was discarded without trace.

    Averaging is not a clever resolution, and it is not meant to be. It keeps
    both readings visible and lands between them, which is the honest position
    when a brief says two things - and `contested` marks the factor so an
    architect can see that the engine was working from mixed evidence rather
    than from a clear statement.
    """
    hits: dict[str, list[Cue]] = {}
    phrases: dict[str, list[str]] = {}

    for cue in CUES:
        match = cue.pattern.search(brief)
        if match is None:
            continue
        hits.setdefault(cue.factor, []).append(cue)
        phrases.setdefault(cue.factor, []).append(" ".join(match.group(0).split())[:80])

    return [
        Signal(
            factor=factor,
            value=sum(c.value for c in cues) / len(cues),
            phrases=phrases[factor],
            reasons=[c.reason for c in cues],
        )
        for factor, cues in hits.items()
    ]


__all__ = ["CUES", "Cue", "Signal", "read"]
