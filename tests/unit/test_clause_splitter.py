"""Clause splitting, tested against text shaped like the real corpus.

The samples imitate the numbering conventions of the actual sources - RBI
Master Directions, GDPR articles, ISO/PCI-style dotted clauses - because the
splitter's whole purpose is to survive those conventions.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from nyaya.ingestion.clause_splitter import flatten, split_clauses

RBI_STYLE = """\
CHAPTER IV
CUSTOMER DUE DILIGENCE

16. Customer Due Diligence Procedure
The Regulated Entity shall undertake customer due diligence measures.
(a) identify the customer and verify identity using reliable documents;
(b) verify the identity of the beneficial owner;
(c) obtain information on the purpose of the business relationship.

17. Enhanced Due Diligence
Enhanced measures shall apply to higher risk categories.
(a) accounts of politically exposed persons;
(b) cross-border correspondent relationships.
"""

GDPR_STYLE = """\
Article 32
Security of processing
1. The controller shall implement appropriate technical measures.
(a) the pseudonymisation and encryption of personal data;
(b) the ability to ensure ongoing confidentiality and integrity;
2. In assessing the appropriate level of security account shall be taken.
"""

DOTTED_STYLE = """\
8. Identify and Authenticate Access
8.1 Define and implement policies for proper user identification.
8.2 Ensure proper user identification management.
8.2.1 Using strong cryptography, render all authentication factors unreadable.
8.2.2 Verify user identity before modifying any authentication factor.
8.3 Establish strong authentication for users.
"""


def test_rbi_hierarchy_and_nesting():
    roots = split_clauses(RBI_STYLE, short_code="RBI-MD-KYC")
    all_nodes = flatten(roots)

    keys = [n.citation_key for n in all_nodes]
    assert "RBI-MD-KYC:16" in keys
    assert "RBI-MD-KYC:16(a)" in keys
    assert "RBI-MD-KYC:16(c)" in keys
    assert "RBI-MD-KYC:17(b)" in keys

    s16 = next(n for n in all_nodes if n.citation_key == "RBI-MD-KYC:16")
    assert len(s16.children) == 3, "section 16 should own exactly its three sub-clauses"
    assert s16.heading == "Customer Due Diligence Procedure"

    # Section 17's sub-clauses must not be absorbed into section 16.
    s17 = next(n for n in all_nodes if n.citation_key == "RBI-MD-KYC:17")
    assert len(s17.children) == 2


def test_chapter_wraps_sections():
    roots = split_clauses(RBI_STYLE, short_code="RBI-MD-KYC")
    chapter = roots[0]
    assert chapter.number == "Chapter IV"
    section_numbers = {c.number for c in chapter.children}
    assert section_numbers == {"16", "17"}


def test_gdpr_article_numbering():
    roots = split_clauses(GDPR_STYLE, short_code="GDPR")
    keys = [n.citation_key for n in flatten(roots)]
    assert "GDPR:Article 32" in keys
    assert "GDPR:Article 32.1" in keys
    assert "GDPR:Article 32.1(a)" in keys
    assert "GDPR:Article 32.2" in keys


def test_dotted_numbering_infers_depth():
    roots = split_clauses(DOTTED_STYLE, short_code="PCI")
    nodes = {n.citation_key: n for n in flatten(roots)}

    assert "PCI:8.1" in nodes
    assert "PCI:8.2.1" in nodes
    # 8.2.1 nests under 8.2, which nests under 8.
    assert nodes["PCI:8.2.1"].depth > nodes["PCI:8.2"].depth > nodes["PCI:8"].depth
    assert len(nodes["PCI:8.2"].children) == 2
    # 8.3 must close the 8.2.x series rather than nesting inside it.
    assert nodes["PCI:8.3"].depth == nodes["PCI:8.2"].depth


def test_clause_text_is_captured_not_dropped():
    roots = split_clauses(RBI_STYLE, short_code="RBI-MD-KYC")
    nodes = {n.citation_key: n for n in flatten(roots)}
    assert "reliable documents" in nodes["RBI-MD-KYC:16(a)"].text
    assert "beneficial owner" in nodes["RBI-MD-KYC:16(b)"].text
    assert "due diligence measures" in nodes["RBI-MD-KYC:16"].text


def test_no_regulatory_text_is_lost():
    """Every non-empty source line must survive into some clause.

    Losing regulatory text is the worst failure this component can have: a
    dropped obligation is one the system can never detect a gap against.
    """
    roots = split_clauses(RBI_STYLE, short_code="RBI-MD-KYC")
    captured = " ".join(n.text for n in flatten(roots))
    captured += " ".join(n.heading or "" for n in flatten(roots))

    for line in RBI_STYLE.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("CHAPTER", "CUSTOMER DUE")):
            continue
        # strip the marker itself, then check the substance survived
        body = stripped.split(") ", 1)[-1].split(". ", 1)[-1]
        assert body[:30] in captured, f"lost text: {body[:40]!r}"


def test_char_offsets_index_into_source():
    roots = split_clauses(RBI_STYLE, short_code="RBI-MD-KYC")
    for node in flatten(roots):
        assert 0 <= node.char_start < node.char_end <= len(RBI_STYLE)
        # the span must actually contain the clause's own number
        if node.number and node.style != "preamble":
            span = RBI_STYLE[node.char_start : node.char_end]
            assert node.number.split()[-1] in span


def test_preamble_is_preserved():
    """Text before any numbered clause is kept, not discarded."""
    text = "This Direction is issued under section 35A.\n\n1. Short title\nThese shall be called.\n"
    roots = split_clauses(text, short_code="X")
    assert roots[0].style == "preamble"
    assert "section 35A" in roots[0].text


@pytest.mark.parametrize(
    ("marker", "expected"),
    [("(a)", "X:1(a)"), ("(1)", "X:1(1)")],
)
def test_paren_styles(marker, expected):
    text = f"1. Heading\n{marker} the sub-clause text here;\n"
    keys = [n.citation_key for n in flatten(split_clauses(text, short_code="X"))]
    assert expected in keys


# --- regressions ----------------------------------------------------------


def test_sibling_spans_do_not_overlap():
    """A clause ends where its successor begins.

    Regression: `char_end` was taken from the current read position, which had
    already advanced past the line that closed the clause - so every span
    swallowed the first line of the next clause and siblings overlapped. A
    citation highlighted in the source would have shown the wrong text.
    """
    doc = "16. Heading\nBody line.\n(a) first sub;\n(b) second sub;\n17. Next\n"
    nodes = flatten(split_clauses(doc, short_code="X"))

    by_depth: dict[int, list] = {}
    for n in nodes:
        by_depth.setdefault(n.depth, []).append(n)

    for siblings in by_depth.values():
        ordered = sorted(siblings, key=lambda n: n.char_start)
        for a, b in pairwise(ordered):
            assert a.char_end <= b.char_start, (
                f"{a.citation_key} [{a.char_start},{a.char_end}) overlaps "
                f"{b.citation_key} [{b.char_start},{b.char_end})"
            )


def test_parent_span_contains_children():
    doc = "16. Heading\nBody.\n(a) one;\n(b) two;\n17. Next\n"
    for node in flatten(split_clauses(doc, short_code="X")):
        for child in node.children:
            assert node.char_start <= child.char_start
            assert child.char_end <= node.char_end


def test_bare_marker_with_heading_on_next_line():
    """Typeset regulations often put the number alone on its own line.

    Regression: the section pattern required trailing text on the same line, so
    such clauses fell through to the preamble and became uncitable.
    """
    doc = "16.\nCustomer Due Diligence\nThe RE shall undertake CDD.\n"
    nodes = flatten(split_clauses(doc, short_code="X"))
    assert "X:16" in [n.citation_key for n in nodes]
    section = next(n for n in nodes if n.citation_key == "X:16")
    assert "Customer Due Diligence" in section.text


@pytest.mark.parametrize(
    "doc",
    ["", "   \n\n  \n", "prose with no numbering\n", "16.\n", "5. Five\n2. Two\n"],
)
def test_degenerate_documents_do_not_raise(doc):
    split_clauses(doc, short_code="X")
