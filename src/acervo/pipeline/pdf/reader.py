from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(frozen=True)
class PdfMetadata:
    pages: int | None
    protected: bool


def metadata(path: Path) -> PdfMetadata:
    """Page count and whether the PDF needs a password. Never its text (rule 3 of CLAUDE.md)."""
    try:
        with pymupdf.open(path, filetype="pdf") as document:  # type: ignore[no-untyped-call]
            return PdfMetadata(pages=document.page_count, protected=bool(document.needs_pass))
    except (pymupdf.FileDataError, RuntimeError):
        # A broken PDF is still stored as uploaded; only its metadata is unknown.
        return PdfMetadata(pages=None, protected=False)
