"""Labelled requirement-to-citation judgements.

The question this set answers is the one the whole grounding architecture rests
on: **can the validator tell a genuine citation from a plausible one?**

Each entry pairs a requirement with a specific clause and a label. The negatives
are the important half, and they are chosen adversarially - not random clauses,
which any method separates, but clauses that are *topically adjacent* to the
requirement. A retention clause cited for a screening duty; a screening clause
cited for a retention duty; the sibling sub-clause that governs a neighbouring
obligation. Those are the citations a language model actually produces when it
is wrong, and a validator that cannot reject them is not doing anything.

Labels are the author's own judgement of whether a regulator would accept the
clause as grounds for the requirement. That is a real limitation, recorded in
the engineering log: a second annotator and an agreement statistic would
strengthen this materially.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CitationJudgement:
    """One (requirement, clause) pair with a ground-truth label."""

    rid: str
    requirement: str
    citation_key: str
    supports: bool
    """True if the clause genuinely obliges the requirement."""

    note: str = ""
    difficulty: str = "normal"
    """`normal` - clearly right or clearly wrong.
    `hard` - topically adjacent, distinguishable only on the substance of the
    obligation. These are the discriminating cases."""


def _pos(rid, req, key, note="", difficulty="normal") -> CitationJudgement:
    return CitationJudgement(rid, req, key, True, note, difficulty)


def _neg(rid, req, key, note="", difficulty="hard") -> CitationJudgement:
    return CitationJudgement(rid, req, key, False, note, difficulty)


# --- requirements under test ---------------------------------------------
R_SCREEN = (
    "When a customer is onboarded through a remote channel, the system shall "
    "screen the customer against the designated-persons list before the account "
    "is activated."
)
R_RETAIN = (
    "The system shall retain customer identification records for five years from "
    "the date the relationship ends."
)
R_LIVENESS = (
    "While a video identification session is active, the system shall verify that "
    "the customer is physically present using liveness detection."
)
R_BENEFICIAL = (
    "The system shall record the identity of the beneficial owner of a legal "
    "person before the account is activated."
)
R_ACCESS_LOG = (
    "When a reviewer opens a customer case, the system shall record the identity "
    "of the reviewer and the time of access."
)
R_ENCRYPT = (
    "The system shall encrypt customer identification documents transmitted over "
    "public networks."
)
R_CONSENT_WITHDRAW = (
    "The system shall allow a customer to withdraw consent using the same number "
    "of steps required to give it."
)
R_PEP = (
    "If a customer is identified as a politically exposed person, then the system "
    "shall require senior-management approval before the account is activated."
)
R_BREACH = (
    "When a personal data breach is confirmed, the system shall notify the "
    "supervisory authority."
)
R_MINIMISE = (
    "The system shall collect only the personal data fields necessary for the "
    "onboarding purpose."
)
R_TIPPING = (
    "The system shall not disclose to the customer that a suspicious transaction "
    "report has been filed."
)
R_GEO = (
    "While a video identification session is active, the system shall record the "
    "geographical coordinates of the customer."
)

JUDGEMENTS: tuple[CitationJudgement, ...] = (
    # --- screening ---
    _pos("R1", R_SCREEN, "RBI-MD-KYC:22", "the governing obligation"),
    _pos("R1", R_SCREEN, "RBI-MD-KYC:22(a)", "states the timing constraint"),
    _neg("R1", R_SCREEN, "RBI-MD-KYC:26(a)", "retention, not screening"),
    _neg("R1", R_SCREEN, "RBI-MD-KYC:10", "identification, not list screening"),
    _neg("R1", R_SCREEN, "RBI-MD-KYC:22(c)", "ongoing re-screening, not pre-activation"),
    _neg("R1", R_SCREEN, "RBI-MD-KYC:17", "risk categorisation", difficulty="normal"),

    # --- retention ---
    _pos("R2", R_RETAIN, "RBI-MD-KYC:26(a)", "exactly this duty"),
    _pos("R2", R_RETAIN, "RBI-MD-KYC:26", "the parent obligation"),
    _neg("R2", R_RETAIN, "RBI-MD-KYC:26(b)", "transaction records, not identity records"),
    _neg("R2", R_RETAIN, "RBI-MD-KYC:22(a)", "screening timing"),
    _neg("R2", R_RETAIN, "DPDP-2023:8(d)", "erasure duty, the opposite direction"),

    # --- liveness ---
    _pos("R3", R_LIVENESS, "RBI-MD-KYC:12(c)", "the liveness obligation"),
    _neg("R3", R_LIVENESS, "RBI-MD-KYC:12(a)", "recording the session, not liveness"),
    _neg("R3", R_LIVENESS, "RBI-MD-KYC:12(b)", "photo matching, not presence"),
    _neg("R3", R_LIVENESS, "RBI-MD-KYC:12(e)", "geolocation, not presence"),

    # --- beneficial owner ---
    _pos("R4", R_BENEFICIAL, "RBI-MD-KYC:16(b)", "the beneficial-owner duty"),
    _neg("R4", R_BENEFICIAL, "RBI-MD-KYC:16(a)", "customer identity, not beneficial owner"),
    _neg("R4", R_BENEFICIAL, "RBI-MD-KYC:16(c)", "purpose of the relationship"),
    _neg("R4", R_BENEFICIAL, "RBI-MD-KYC:11(a)", "valid documents list"),

    # --- access logging ---
    _pos("R5", R_ACCESS_LOG, "RBI-MD-KYC:27(a)", "restrict and log access"),
    _neg("R5", R_ACCESS_LOG, "RBI-MD-KYC:27(b)", "encryption, not access logging"),
    _neg("R5", R_ACCESS_LOG, "RBI-MD-KYC:13(c)", "audit trail of e-verification", difficulty="hard"),
    _neg("R5", R_ACCESS_LOG, "RBI-MD-KYC:26(c)", "record reconstruction"),

    # --- encryption ---
    _pos("R6", R_ENCRYPT, "RBI-MD-KYC:27(b)", "encryption over public networks"),
    _pos("R6", R_ENCRYPT, "GDPR:Article 32.1(a)", "encryption of personal data"),
    _neg("R6", R_ENCRYPT, "RBI-MD-KYC:27(a)", "access control, not encryption"),
    _neg("R6", R_ENCRYPT, "GDPR:Article 32.1(c)", "restoration, not confidentiality"),

    # --- consent withdrawal ---
    _pos("R7", R_CONSENT_WITHDRAW, "DPDP-2023:6(b)", "ease of withdrawal"),
    _neg("R7", R_CONSENT_WITHDRAW, "DPDP-2023:6(a)", "scope of consent"),
    _neg("R7", R_CONSENT_WITHDRAW, "DPDP-2023:5(b)", "notice of how to withdraw", difficulty="hard"),
    _neg("R7", R_CONSENT_WITHDRAW, "DPDP-2023:6(c)", "cessation after withdrawal", difficulty="hard"),

    # --- politically exposed persons ---
    _pos("R8", R_PEP, "RBI-MD-KYC:18(a)", "senior-management approval for PEPs"),
    _neg("R8", R_PEP, "RBI-MD-KYC:18(b)", "source of funds, not approval"),
    _neg("R8", R_PEP, "RBI-MD-KYC:17(a)", "risk factors"),
    _neg("R8", R_PEP, "RBI-MD-KYC:19", "simplified due diligence, the opposite"),

    # --- breach notification ---
    _pos("R9", R_BREACH, "GDPR:Article 33.1", "notification to the authority"),
    _pos("R9", R_BREACH, "DPDP-2023:8(c)", "notice to the Board"),
    _neg("R9", R_BREACH, "GDPR:Article 32.1(b)", "security measures, not notification"),
    _neg("R9", R_BREACH, "GDPR:Article 35.1", "impact assessment"),

    # --- minimisation ---
    _pos("R10", R_MINIMISE, "GDPR:Article 5.1(c)", "data minimisation"),
    _pos("R10", R_MINIMISE, "GDPR:Article 25.2", "by default, only what is necessary"),
    _neg("R10", R_MINIMISE, "GDPR:Article 5.1(b)", "purpose limitation", difficulty="hard"),
    _neg("R10", R_MINIMISE, "GDPR:Article 5.1(e)", "storage limitation", difficulty="hard"),

    # --- tipping off ---
    _pos("R11", R_TIPPING, "RBI-MD-KYC:23(b)", "the tipping-off prohibition"),
    _neg("R11", R_TIPPING, "RBI-MD-KYC:23(a)", "filing deadline, not disclosure"),
    _neg("R11", R_TIPPING, "RBI-MD-KYC:17(b)", "risk-category non-disclosure", difficulty="hard"),

    # --- geolocation ---
    _pos("R12", R_GEO, "RBI-MD-KYC:12(e)", "coordinates and domestic IP"),
    _neg("R12", R_GEO, "RBI-MD-KYC:12(c)", "liveness, not location"),
    _neg("R12", R_GEO, "RBI-MD-KYC:12(a)", "recording and timestamp"),
)


def positives() -> tuple[CitationJudgement, ...]:
    return tuple(j for j in JUDGEMENTS if j.supports)


def negatives() -> tuple[CitationJudgement, ...]:
    return tuple(j for j in JUDGEMENTS if not j.supports)


def hard_negatives() -> tuple[CitationJudgement, ...]:
    """Topically adjacent wrong citations - the discriminating cases."""
    return tuple(j for j in JUDGEMENTS if not j.supports and j.difficulty == "hard")


__all__ = [
    "JUDGEMENTS",
    "CitationJudgement",
    "hard_negatives",
    "negatives",
    "positives",
]
