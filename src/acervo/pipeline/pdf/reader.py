import threading
from dataclasses import dataclass
from pathlib import Path

import pymupdf

# PyMuPDF is not thread-safe: every use of it in this process holds this lock.
PYMUPDF = threading.Lock()


@dataclass(frozen=True)
class PdfMetadata:
    pages: int | None
    protected: bool


def _metadata(path: Path) -> PdfMetadata:
    """Page count and whether the PDF needs a password. Never its text (rule 1 of CLAUDE.md)."""
    try:
        with pymupdf.open(path, filetype="pdf") as document:  # type: ignore[no-untyped-call]
            return PdfMetadata(pages=document.page_count, protected=bool(document.needs_pass))
    except (pymupdf.FileDataError, RuntimeError):
        # A broken PDF is still stored as uploaded; only its metadata is unknown.
        return PdfMetadata(pages=None, protected=False)


# What filing reads of a dropped PDF: its first pages and its outline, never the whole file (rule 3).
FIRST_PAGES = 3


def _first_pages(path: Path, pages: int = FIRST_PAGES) -> tuple[str, list[str]]:
    """The text of the first `pages` pages and the outline's titles, in order; nothing of a file that needs a
    password or is no PDF, which is then filed by its name alone."""
    try:
        with pymupdf.open(path, filetype="pdf") as document:  # type: ignore[no-untyped-call]
            if document.needs_pass:
                return "", []
            text = "\n".join(document[number].get_text() for number in range(min(pages, document.page_count)))
            return text, [title for _, title, *_ in document.get_toc()]
    except (pymupdf.FileDataError, RuntimeError):
        return "", []


def _page_text(path: Path, first: int, last: int) -> tuple[list[str], int]:
    """The text of each page from `first` to `last`, counted from 1 and both included, up to the PDF's last page;
    and how many pages it has."""
    with pymupdf.open(path, filetype="pdf") as document:  # type: ignore[no-untyped-call]
        last = min(last, document.page_count)
        return [document[number - 1].get_text() for number in range(first, last + 1)], document.page_count


def metadata(path: Path) -> PdfMetadata:
    with PYMUPDF:
        return _metadata(path)


def first_pages(path: Path, pages: int = FIRST_PAGES) -> tuple[str, list[str]]:
    with PYMUPDF:
        return _first_pages(path, pages)


def page_text(path: Path, first: int, last: int) -> tuple[list[str], int]:
    with PYMUPDF:
        return _page_text(path, first, last)
