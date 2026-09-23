"""Prompts for the extraction agent.

The earlier measurement showed that Pydantic field descriptions alone were not
enough: the model echoed the stakeholder's sentence back verbatim instead of
rewriting it as a testable obligation. Exemplars fix this in a way instruction
cannot, because they demonstrate the *transformation* rather than describing it.

Each exemplar is chosen to teach one specific behaviour, listed against it below.
"""

from __future__ import annotations

from nyaya.agents.schemas import ExtractionContext

EXTRACTION_SYSTEM = """\
You are a requirements analyst for a regulated financial institution working on \
{domain}. You convert what stakeholders say into precise, testable requirements.

Rules, in order of importance:

1. Write EACH requirement in EARS form with exactly one "shall":
     The <actor> shall <response>.
     When <trigger>, the <actor> shall <response>.
     While <state>, the <actor> shall <response>.
     If <condition>, then the <actor> shall <response>.

2. NEVER copy the stakeholder's sentence. Rewrite it. The stakeholder describes \
a need in ordinary language; you state an obligation a tester can verify.

3. SPLIT compound statements. One obligation per requirement. If the input \
contains "and" joining two duties, that is two requirements, because each must \
be separately approvable, testable and traceable.

4. BAN unverifiable language: appropriate, adequate, sufficient, reasonable, \
robust, quickly, timely, promptly, as needed, if possible, etc. Where the \
stakeholder used such a word, either state the concrete value they implied or \
raise it in `unclear`.

5. NEVER invent a threshold, duration, or standard the stakeholder did not give. \
A missing number goes in `unclear` as a question. An invented number is a \
fabricated requirement, which is worse than an incomplete one.

6. `quoted_source` must be copied verbatim from the input. It is the provenance \
link an auditor follows back to the original statement.
"""

# Exemplars. Each demonstrates a behaviour that instruction alone failed to
# produce, noted in the comment above it.
_EXEMPLARS: tuple[tuple[str, str], ...] = (
    # Teaches: rewrite rather than echo; split a compound; ask instead of invent.
    (
        "Compliance officer: For anyone we onboard remotely we have to check them "
        "against the sanctions list before the account goes live, and keep proof "
        "of that check for five years.",
        """{
  "requirements": [
    {
      "statement": "When a customer is onboarded through a remote channel, the system shall screen the customer against the designated-persons list before the account is activated.",
      "rationale": "Sanctions screening must complete before the customer can transact, so it is a precondition of activation rather than a background task.",
      "categories": ["regulatory", "security", "functional"],
      "priority": "must",
      "risk_level": "critical",
      "acceptance_criteria": [
        "Given a remote onboarding application, when screening has not completed, then account activation is refused.",
        "Given a screening match, when the operator attempts activation, then the system blocks it and records the match."
      ],
      "assumptions": [],
      "quoted_source": "we have to check them against the sanctions list before the account goes live"
    },
    {
      "statement": "The system shall retain evidence of each sanctions screening for five years from the date of screening.",
      "rationale": "The stakeholder stated a five-year retention duty for screening evidence.",
      "categories": ["regulatory", "audit_reporting", "data_management"],
      "priority": "must",
      "risk_level": "high",
      "acceptance_criteria": [
        "Given a screening performed on a date, when five years have not elapsed, then the evidence is retrievable."
      ],
      "assumptions": [],
      "quoted_source": "keep proof of that check for five years"
    }
  ],
  "unclear": [
    "Does the five-year retention run from the screening date or from closure of the relationship?",
    "Which designated-persons lists are in scope, and how often are they refreshed?"
  ]
}""",
    ),
    # Teaches: refuse to invent a number; convert vagueness into a question.
    (
        "Product owner: The identity check should be fast, users drop off if it takes too long.",
        """{
  "requirements": [
    {
      "statement": "The system shall complete the identity verification check within the performance threshold agreed for the onboarding journey.",
      "rationale": "Verification latency drives onboarding abandonment, so it is a stated performance concern.",
      "categories": ["performance", "usability"],
      "priority": "should",
      "risk_level": "medium",
      "acceptance_criteria": [
        "Given a submitted identity check, when the agreed threshold is exceeded, then the breach is recorded for review."
      ],
      "assumptions": ["A numeric latency target will be supplied before this requirement is baselined."],
      "quoted_source": "The identity check should be fast"
    }
  ],
  "unclear": [
    "What is the maximum acceptable identity-check latency, at which percentile, and measured between which two points?"
  ]
}""",
    ),
)


def build_extraction_messages(text: str, context: ExtractionContext) -> list[tuple[str, str]]:
    """Build the (role, content) turns for an extraction call.

    Exemplars are supplied as prior conversational turns rather than pasted into
    the system prompt, because models follow a demonstrated assistant turn more
    reliably than a described one.
    """
    turns: list[tuple[str, str]] = [
        ("system", EXTRACTION_SYSTEM.format(domain=context.domain.replace("_", " ")))
    ]
    for user_text, assistant_json in _EXEMPLARS:
        turns.append(("user", user_text))
        turns.append(("assistant", assistant_json))
    turns.append(("user", text))
    return turns


REPAIR_INSTRUCTION = """\
Some of your requirements are not testable as written. Rewrite the numbered \
statements below.

Return one entry per problem you fix, each carrying the problem's number and \
the rewritten statement alone. Do not return the other requirements - they are \
kept as they are. Do not restate the problem, the reason or the source inside \
the statement.

{problems}

Apply the fixes literally, with ONE overriding constraint:

DO NOT INVENT A NUMBER, DURATION, THRESHOLD OR STANDARD THE STAKEHOLDER DID NOT \
STATE. If removing vague wording would require a value you were not given, keep \
the statement general, name the missing value as a question in `unclear`, and \
record the gap in `assumptions`. A vague requirement a reviewer can see is \
recoverable; a fabricated threshold reads as precise, passes review, and gets \
built.
"""


REPAIR_SYSTEM = """\
You are a requirements analyst. You rewrite individual requirement statements \
into EARS form with exactly one "shall", and you do nothing else.
"""


def build_repair_messages(problems: list[str]) -> list[tuple[str, str]]:
    """A self-contained repair request.

    Deliberately *not* a continuation of the extraction conversation. It used to
    be: the whole exchange was re-sent - system prompt, both exemplars with
    their JSON, the full first answer - and only then the list of statements to
    fix. On a long brief that put two thousand tokens of context in front of a
    request whose entire subject is a handful of sentences, and the second pass
    ended up costing more than the first.

    It also made the repair slower exactly when it was most likely to be needed,
    because the answer that has the most defects is the longest one.

    The linters have already said precisely what is wrong with each statement,
    so nothing from the original conversation is load-bearing here. The
    statements carry their own problems with them.
    """
    numbered = "\n".join(f"{i}. {p}" for i, p in enumerate(problems, start=1))
    return [
        ("system", REPAIR_SYSTEM),
        ("user", REPAIR_INSTRUCTION.format(problems=numbered)),
    ]


def build_repair_message(problems: list[str]) -> str:
    """The repair instruction alone, without the surrounding turns."""
    numbered = "\n".join(f"{i}. {p}" for i, p in enumerate(problems, start=1))
    return REPAIR_INSTRUCTION.format(problems=numbered)


__all__ = [
    "EXTRACTION_SYSTEM",
    "REPAIR_INSTRUCTION",
    "build_extraction_messages",
    "build_repair_message",
    "build_repair_messages",
]
