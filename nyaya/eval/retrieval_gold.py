"""Labelled retrieval set for the eKYC corpus.

Queries are written in **stakeholder phrasing, not clause wording**. That is the
point: a business analyst says "we need to check people against the sanctions
list before the account goes live", and the clause says "screening against the
lists of designated persons notified by the competent authority". If the queries
reused the source vocabulary, lexical search would score near-perfectly and the
benchmark would measure nothing.

`relevant` holds the clause keys a competent analyst would accept as grounds for
the requirement. `primary` is the single clause that most directly states the
obligation, used for Mean Reciprocal Rank.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoldQuery:
    qid: str
    query: str
    primary: str
    relevant: frozenset[str]
    jurisdictions: tuple[str, ...] = ("IN", "EU")
    note: str = ""
    style: str = "paraphrase"
    """`paraphrase` - lay stakeholder wording, no shared vocabulary with the
    clause. `term_of_art` - the query names the precise legal category. Both
    occur in practice, and they stress opposite retrievers, so arms are scored
    on each subset separately rather than on a blend that hides the difference."""


def _q(qid: str, query: str, primary: str, *also: str, **kw) -> GoldQuery:
    return GoldQuery(
        qid=qid,
        query=query,
        primary=primary,
        relevant=frozenset({primary, *also}),
        **kw,
    )


GOLD: tuple[GoldQuery, ...] = (
    _q(
        "Q01",
        "we have to check every new customer against the sanctions list before "
        "their account goes live",
        "RBI-MD-KYC:22(a)",
        "RBI-MD-KYC:22",
        "RBI-MD-KYC:22(b)",
        note="paraphrase: 'sanctions list' vs 'designated persons'",
    ),
    _q(
        "Q02",
        "how long do we need to keep proof of the identity checks after someone "
        "closes their account",
        "RBI-MD-KYC:26(a)",
        "RBI-MD-KYC:26",
    ),
    _q(
        "Q03",
        "the selfie step needs to prove the person is actually there and not "
        "holding up a photo or a recording",
        "RBI-MD-KYC:12(c)",
        "RBI-MD-KYC:12",
        note="liveness detection, described entirely in lay terms",
    ),
    _q(
        "Q04",
        "can we open an account for someone who will not tell us who really owns the company",
        "RBI-MD-KYC:16(b)",
        "RBI-MD-KYC:16",
        "RBI-MD-KYC:9(b)",
        note="beneficial owner, never named in the query",
    ),
    _q(
        "Q05",
        "senior management sign off before we onboard a government minister or their relatives",
        "RBI-MD-KYC:18(a)",
        "RBI-MD-KYC:18",
        note="politically exposed person, described obliquely",
    ),
    _q(
        "Q06",
        "what do we have to tell the customer before we verify their identity electronically",
        "RBI-MD-KYC:13(b)",
        "RBI-MD-KYC:13",
        "RBI-MD-KYC:13(a)",
    ),
    _q(
        "Q07",
        "which documents count for proving where someone lives",
        "RBI-MD-KYC:11(b)",
        "RBI-MD-KYC:11",
        "RBI-MD-KYC:11(a)",
    ),
    _q(
        "Q08",
        "we want to score customers by how risky they are and tell them their rating",
        "RBI-MD-KYC:17(b)",
        "RBI-MD-KYC:17",
        "RBI-MD-KYC:17(a)",
        note="the query proposes something the clause forbids",
    ),
    _q(
        "Q09",
        "if we spot a transaction that looks like laundering, can we warn the "
        "customer we are filing a report",
        "RBI-MD-KYC:23(b)",
        "RBI-MD-KYC:23",
        note="tipping-off prohibition",
    ),
    _q(
        "Q10",
        "the video call has to be from inside the country and we should log where they are",
        "RBI-MD-KYC:12(e)",
        "RBI-MD-KYC:12",
    ),
    _q(
        "Q11",
        "customer wants us to delete everything we hold on them after they withdraw permission",
        "DPDP-2023:8(d)",
        "DPDP-2023:6(c)",
        "DPDP-2023:12(b)",
        "DPDP-2023:12",
    ),
    _q(
        "Q12",
        "who do we have to inform when customer records leak",
        "DPDP-2023:8(c)",
        "GDPR:Article 33.1",
        "GDPR:Article 33",
        note="spans both jurisdictions",
    ),
    _q(
        "Q13",
        "opting out should be as easy as opting in",
        "DPDP-2023:6(b)",
        "DPDP-2023:6",
    ),
    _q(
        "Q14",
        "do we need a parent to approve before a minor uses the app",
        "DPDP-2023:9",
        "DPDP-2023:9(a)",
    ),
    _q(
        "Q15",
        "the consent screen has to be understandable and available in the customer's own language",
        "DPDP-2023:5(c)",
        "DPDP-2023:5",
    ),
    _q(
        "Q16",
        "we should scramble stored personal data so it is useless if the database is stolen",
        "GDPR:Article 32.1(a)",
        "GDPR:Article 32.1",
        "GDPR:Article 32",
        note="pseudonymisation and encryption, in lay phrasing",
    ),
    _q(
        "Q17",
        "only collect the fields we actually need for onboarding, nothing extra",
        "GDPR:Article 5.1(c)",
        "GDPR:Article 25.2",
        "GDPR:Article 25",
        note="data minimisation",
    ),
    _q(
        "Q18",
        "we need to be able to bring the service back up quickly after an "
        "outage without losing customer data",
        "GDPR:Article 32.1(c)",
        "GDPR:Article 32.1",
        "GDPR:Article 32",
    ),
    _q(
        "Q19",
        "before launching the new onboarding flow, do we need a formal privacy risk assessment",
        "GDPR:Article 35.1",
        "GDPR:Article 35",
    ),
    _q(
        "Q20",
        "customers should be able to ask us what data we hold and who we shared it with",
        "DPDP-2023:11",
    ),
    _q(
        "Q21",
        "no anonymous or made-up-name accounts",
        "RBI-MD-KYC:9(a)",
        "RBI-MD-KYC:9",
    ),
    _q(
        "Q22",
        "we must watch account activity for the whole relationship, not just at signup",
        "RBI-MD-KYC:16(d)",
        "RBI-MD-KYC:16",
    ),
    _q(
        "Q23",
        "restrict who inside the bank can pull up a customer's identity "
        "documents and keep a log of it",
        "RBI-MD-KYC:27(a)",
        "RBI-MD-KYC:27",
    ),
    _q(
        "Q24",
        "can we skip the full checks for low value accounts",
        "RBI-MD-KYC:19",
        note="simplified due diligence; single short clause, no sub-clauses",
    ),
)


# --- terms of art ---------------------------------------------------------
#
# Queries naming the exact legal category. These are the case lexical retrieval
# exists for: "beneficial owner" and "politically exposed person" are precise
# categories whose neighbours in embedding space are the wrong obligation.

TERM_QUERIES: tuple[GoldQuery, ...] = (
    _q(
        "T01",
        "beneficial owner identification and ownership structure",
        "RBI-MD-KYC:16(b)",
        "RBI-MD-KYC:16",
        style="term_of_art",
    ),
    _q(
        "T02",
        "politically exposed persons senior management approval",
        "RBI-MD-KYC:18(a)",
        "RBI-MD-KYC:18",
        style="term_of_art",
    ),
    _q(
        "T03",
        "video based customer identification process liveness detection",
        "RBI-MD-KYC:12(c)",
        "RBI-MD-KYC:12",
        style="term_of_art",
    ),
    _q(
        "T04",
        "suspicious transaction report Financial Intelligence Unit",
        "RBI-MD-KYC:23(a)",
        "RBI-MD-KYC:23",
        style="term_of_art",
    ),
    _q(
        "T05",
        "officially valid document for address verification",
        "RBI-MD-KYC:11(b)",
        "RBI-MD-KYC:11",
        "RBI-MD-KYC:11(a)",
        style="term_of_art",
    ),
    _q(
        "T06",
        "pseudonymisation and encryption of personal data",
        "GDPR:Article 32.1(a)",
        "GDPR:Article 32.1",
        "GDPR:Article 32",
        style="term_of_art",
    ),
    _q(
        "T07",
        "data protection impact assessment high risk processing",
        "GDPR:Article 35.1",
        "GDPR:Article 35",
        style="term_of_art",
    ),
    _q(
        "T08",
        "verifiable consent of parent or lawful guardian for a child",
        "DPDP-2023:9",
        "DPDP-2023:9(a)",
        style="term_of_art",
    ),
    _q(
        "T09",
        "enhanced due diligence source of funds and source of wealth",
        "RBI-MD-KYC:18(b)",
        "RBI-MD-KYC:18",
        style="term_of_art",
    ),
    _q(
        "T10",
        "customer acceptance policy approved by the Board",
        "RBI-MD-KYC:9",
        "RBI-MD-KYC:9(a)",
        style="term_of_art",
    ),
)

ALL_QUERIES: tuple[GoldQuery, ...] = GOLD + TERM_QUERIES


def by_id() -> dict[str, GoldQuery]:
    return {g.qid: g for g in ALL_QUERIES}


def by_style(style: str) -> tuple[GoldQuery, ...]:
    return tuple(g for g in ALL_QUERIES if g.style == style)


__all__ = ["ALL_QUERIES", "GOLD", "TERM_QUERIES", "GoldQuery", "by_id", "by_style"]
