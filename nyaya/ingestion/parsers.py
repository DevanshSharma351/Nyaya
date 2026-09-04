"""Document text extraction.

Returns plain text with layout artefacts removed but **character order
preserved**, because the clause splitter records offsets into this text and
those offsets are what let a citation be highlighted in the source.
"""

from __future__ import annotations

import re
from pathlib import Path

# Page furniture that would otherwise be spliced into clause text. Matched on
# whole lines only, so a legitimate sentence containing "Page" survives.
_PAGE_ARTEFACT = re.compile(
    r"^\s*(?:Page\s+\d+\s*(?:of\s+\d+)?|\d+\s*\|\s*P\s*a\s*g\s*e|-\s*\d+\s*-)\s*$",
    re.I,
)
_MULTI_BLANK = re.compile(r"\n{3,}")


class UnsupportedDocumentError(ValueError):
    """The file type has no registered parser."""


def parse(path: str | Path) -> str:
    """Extract text from a document, dispatching on file extension."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        text = _parse_pdf(path)
    elif suffix == ".docx":
        text = _parse_docx(path)
    elif suffix in {".html", ".htm"}:
        text = _parse_html(path)
    elif suffix in {".txt", ".md", ".text"}:
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        raise UnsupportedDocumentError(f"No parser for {suffix!r} ({path.name})")

    return normalise(text)


def normalise(text: str) -> str:
    """Strip page furniture and collapse excess blank lines.

    Deliberately light: aggressive normalisation (de-hyphenation, reflowing
    wrapped lines) risks corrupting clause numbering, and a mangled number is a
    clause that can never be cited.
    """
    lines = [line for line in text.splitlines() if not _PAGE_ARTEFACT.match(line)]
    joined = "\n".join(line.rstrip() for line in lines)
    return _MULTI_BLANK.sub("\n\n", joined).strip() + "\n"


def _parse_pdf(path: Path) -> str:
    import pymupdf

    with pymupdf.open(path) as doc:
        # "text" mode preserves reading order; "blocks" would reorder columns.
        return "\n".join(page.get_text("text") for page in doc)


def _parse_docx(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs]
    # Tables carry obligations in real policy documents; flatten row-wise.
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _parse_html(path: Path) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text("\n")


def content_hash(path: str | Path) -> str:
    """SHA-256 of the raw file, for detecting silent source substitution."""
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


__all__ = ["UnsupportedDocumentError", "content_hash", "normalise", "parse"]
