"""Split a regulatory document into a hierarchy of addressable clauses.

Regulatory text is not prose to be chunked by token count. It is a numbered
tree, and its numbering *is* the citation scheme: `RBI-MD-KYC:16(a)` is
meaningful to a compliance officer in a way that `chunk_47` never is.

Splitting on the document's own structure rather than on a fixed window buys
three things that fixed-size chunking cannot:

1. **Citations that resolve.** A generated requirement cites a clause key; the
   validator resolves that key back to exactly one row.
2. **Retrieval units that are semantically whole.** A clause is a complete
   obligation. A 512-token window routinely severs one mid-sentence, so the
   retrieved span no longer states the duty it is being cited for.
3. **Interpretive context on demand.** A leaf sub-clause such as `(a)` often
   means nothing without its parent; the hierarchy lets retrieval walk upward.

The splitter is deliberately conservative: text it cannot attribute to a
numbered clause is attached to the enclosing clause rather than silently
dropped, because losing regulatory text is a far worse failure than an
imperfectly attributed span.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- marker grammar -------------------------------------------------------
#
# Each pattern captures one numbering style. `tier` orders the styles from
# outermost to innermost; a marker of a lower tier closes every open clause at
# or above its own tier. Dotted numbering is handled separately, because its
# depth is carried by the number itself (`5.1.2` is three levels deep).

_ROMAN = "(?=[MDCLXVI])M{0,3}(?:C[MD]|D?C{0,3})(?:X[CL]|L?X{0,3})(?:I[XV]|V?I{0,3})"


@dataclass(frozen=True, slots=True)
class MarkerStyle:
    name: str
    tier: int
    pattern: re.Pattern[str]


MARKER_STYLES: tuple[MarkerStyle, ...] = (
    MarkerStyle(
        "part",
        0,
        re.compile(
            rf"^\s*(?P<label>PART|CHAPTER|TITLE)\s+(?P<num>{_ROMAN}|\d+)\b[.:]?\s*(?P<rest>.*)$",
            re.I,
        ),
    ),
    MarkerStyle(
        "article",
        1,
        re.compile(
            r"^\s*(?P<label>Article|Regulation|Rule)\s+(?P<num>\d+[A-Za-z]?)\b[.:]?\s*(?P<rest>.*)$",
            re.I,
        ),
    ),
    MarkerStyle(
        "section",
        2,
        # `rest` is optional: typeset regulations frequently place the clause
        # number alone on one line with its heading on the next.
        re.compile(r"^\s*(?:Section\s+)?(?P<num>\d+[A-Za-z]?)\.(?:\s+(?P<rest>\S.*))?$"),
    ),
    MarkerStyle(
        "dotted",
        3,
        re.compile(r"^\s*(?P<num>\d+(?:\.\d+)+)\.?\s+(?P<rest>\S.*)$"),
    ),
    MarkerStyle(
        "paren_num",
        4,
        re.compile(r"^\s*\((?P<num>\d{1,2})\)\s+(?P<rest>\S.*)$"),
    ),
    MarkerStyle(
        "paren_alpha",
        5,
        re.compile(r"^\s*\((?P<num>[a-z]{1,2})\)\s+(?P<rest>\S.*)$"),
    ),
    MarkerStyle(
        "paren_roman",
        6,
        re.compile(r"^\s*\((?P<num>[ivxl]{1,5})\)\s+(?P<rest>\S.*)$"),
    ),
)

# `(i)`, `(v)` and `(x)` are valid under both the alpha and roman patterns.
# Convention in legal drafting is that the roman series begins only after the
# alpha series has been used at a deeper level, so an ambiguous marker is read
# as alpha unless a roman series is already open at that tier.
_AMBIGUOUS = {"i", "v", "x", "l"}

# Divisions that organise a document without forming part of a citation.
_TRANSPARENT_STYLES = {"preamble", "part"}


@dataclass(slots=True)
class ClauseNode:
    """One clause in the parsed hierarchy."""

    number: str | None
    heading: str | None
    text: str
    depth: int
    ordinal: int
    char_start: int
    char_end: int
    style: str
    citation_key: str = ""
    children: list[ClauseNode] = field(default_factory=list)

    def walk(self):
        """Depth-first traversal, yielding self then descendants."""
        yield self
        for child in self.children:
            yield from child.walk()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ClauseNode {self.citation_key or self.number!r} d={self.depth}>"


@dataclass(slots=True)
class _Open:
    """A clause currently open on the parse stack."""

    node: ClauseNode
    tier: int
    body: list[str]


def _match_marker(line: str, roman_open: bool) -> tuple[MarkerStyle, str, str] | None:
    """Return (style, number, remainder) if `line` begins a new clause."""
    for style in MARKER_STYLES:
        m = style.pattern.match(line)
        if not m:
            continue
        num = m.group("num")

        if style.name == "paren_alpha" and num.lower() in _AMBIGUOUS and roman_open:
            continue  # let the roman pattern claim it
        if style.name == "paren_roman" and num.lower() in _AMBIGUOUS and not roman_open:
            continue  # read as alpha until a roman series is established

        label = m.groupdict().get("label")
        number = f"{label.title()} {num}" if label else num
        return style, number, (m.group("rest") or "").strip()
    return None


def _dotted_tier(number: str) -> int:
    """Depth of a dotted number: `5.1.2` sits two levels below `5`."""
    return MARKER_STYLES[3].tier + number.count(".") - 1


def split_clauses(text: str, *, short_code: str) -> list[ClauseNode]:
    """Parse `text` into a clause tree.

    `short_code` prefixes every citation key, e.g. `RBI-MD-KYC:16(a)`.
    Character offsets index into `text` exactly as supplied, so a citation can
    be highlighted in the original document.
    """
    roots: list[ClauseNode] = []
    stack: list[_Open] = []
    offset = 0
    counters: dict[int, int] = {}

    def close_to(tier: int, boundary: int) -> None:
        """Close every open clause at or below `tier` in specificity.

        `boundary` is the offset at which the closing clause *starts*, not the
        current read position: a clause ends where its successor begins. Using
        the read position would extend every span over the first line of the
        next clause and make sibling spans overlap.
        """
        while stack and stack[-1].tier >= tier:
            done = stack.pop()
            done.node.text = "\n".join(done.body).strip()
            done.node.char_end = boundary

    def roman_series_open() -> bool:
        return any(o.node.style == "paren_roman" for o in stack)

    for raw_line in text.splitlines(keepends=True):
        line_start = offset
        offset += len(raw_line)
        line = raw_line.rstrip("\n")

        if not line.strip():
            if stack:
                stack[-1].body.append("")
            continue

        matched = _match_marker(line, roman_series_open())
        if matched is None:
            # Unattributed text belongs to the innermost open clause. If none is
            # open the document has a preamble, which is preserved as a root
            # clause so that no regulatory text is lost.
            if not stack:
                preamble = ClauseNode(
                    number=None,
                    heading=None,
                    text="",
                    depth=0,
                    ordinal=len(roots),
                    char_start=line_start,
                    char_end=offset,
                    style="preamble",
                    citation_key=f"{short_code}:preamble",
                )
                roots.append(preamble)
                stack.append(_Open(preamble, tier=-1, body=[]))
            stack[-1].body.append(line.strip())
            continue

        style, number, rest = matched
        tier = _dotted_tier(number) if style.name == "dotted" else style.tier

        close_to(tier, line_start)

        depth = len(stack)
        counters[depth] = counters.get(depth, 0) + 1
        parent = stack[-1].node if stack else None

        node = ClauseNode(
            number=number,
            heading=rest or None,
            text="",
            depth=depth,
            ordinal=len(parent.children) if parent else len(roots),
            char_start=line_start,
            char_end=offset,
            style=style.name,
        )
        node.citation_key = _citation_key(short_code, parent, node)

        if parent is not None:
            parent.children.append(node)
        else:
            roots.append(node)

        # The heading line is part of the clause body: in most regulatory text
        # the obligation begins on the same line as its number.
        stack.append(_Open(node, tier=tier, body=[rest] if rest else []))

    close_to(-1, offset)
    return roots


def _citation_key(short_code: str, parent: ClauseNode | None, node: ClauseNode) -> str:
    """Build a citation key from the clause's position in the hierarchy.

    Parenthesised sub-clauses append to the parent (`16(a)`), while numbered
    divisions extend it with a separator (`Article 32.1`) - matching how each is
    written in the source, so that a key can be looked up by a human reading the
    PDF.

    Organisational divisions are *transparent* to citation. Nobody cites
    "Chapter IV, section 16"; they cite section 16. Parts and chapters still
    nest in the tree, because retrieval walks upward for interpretive context,
    but they contribute nothing to the key.
    """
    if parent is None or parent.style in _TRANSPARENT_STYLES:
        return f"{short_code}:{node.number}"

    base = parent.citation_key
    if node.style.startswith("paren"):
        return f"{base}({node.number})"
    if node.style == "dotted":
        return f"{short_code}:{node.number}"
    return f"{base}.{node.number}"


def flatten(roots: list[ClauseNode]) -> list[ClauseNode]:
    """All clauses in document order."""
    return [n for root in roots for n in root.walk()]


__all__ = ["MARKER_STYLES", "ClauseNode", "flatten", "split_clauses"]
