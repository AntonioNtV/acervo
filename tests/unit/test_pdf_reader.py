from pathlib import Path

import pytest

from acervo.pipeline.pdf.reader import PdfMetadata, metadata

PDFS = Path(__file__).parent.parent / "fixtures" / "pdfs"


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [("simple.pdf", PdfMetadata(pages=3, protected=False)), ("protected.pdf", PdfMetadata(pages=3, protected=True))],
)
def test_pages_and_protected_flag(fixture: str, expected: PdfMetadata) -> None:
    assert metadata(PDFS / fixture) == expected
