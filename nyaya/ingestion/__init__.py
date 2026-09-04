"""Document ingestion: parsing, clause splitting, PII masking, indexing."""

from nyaya.ingestion.clause_splitter import ClauseNode, flatten, split_clauses
from nyaya.ingestion.parsers import content_hash, parse
from nyaya.ingestion.pii import MaskResult, mask, mask_with_ner, unmask
from nyaya.ingestion.pipeline import IngestionReport, ingest_document

__all__ = [
    "ClauseNode",
    "IngestionReport",
    "MaskResult",
    "content_hash",
    "flatten",
    "ingest_document",
    "mask",
    "mask_with_ner",
    "parse",
    "split_clauses",
    "unmask",
]
