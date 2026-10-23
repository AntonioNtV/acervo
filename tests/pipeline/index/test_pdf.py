"""One test per acceptance criterion of the PDF indexer, on PDFs built by `tests/fixtures/pdfs/make.py`."""

import importlib.util
import time
from pathlib import Path
from types import ModuleType

import pytest

from acervo.core.settings import RetrievalLimits
from acervo.domain.index import Section
from acervo.pipeline.index.pdf import NO_TEXT, PROTECTED, index_pdf

PDFS = Path(__file__).resolve().parents[2] / "fixtures" / "pdfs"
LIMITS = RetrievalLimits()


def _make() -> ModuleType:
    """The fixtures folder is not a package: the builder is loaded from its file."""
    spec = importlib.util.spec_from_file_location("make_pdfs", PDFS / "make.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


make = _make()


def _tree(sections: list[Section]) -> list[tuple[str, int | None, int | None, list[object]]]:
    return [(section.title, section.page, section.end_page, _tree(section.children)) for section in sections]


def test_a_200_page_pdf_gives_its_bookmark_tree_with_page_ranges_quickly(tmp_path: Path) -> None:
    path = make.with_bookmarks(tmp_path / "long.pdf", pages=200)

    started = time.monotonic()
    index = index_pdf(path, LIMITS)
    elapsed = time.monotonic() - started

    assert elapsed < 10
    assert _tree(index.sections) == [
        (
            f"Capítulo {chapter + 1}",
            chapter * 20 + 1,
            chapter * 20 + 20,
            [(f"Seção {first}", first, first + 4, []) for first in range(chapter * 20 + 1, chapter * 20 + 21, 5)],
        )
        for chapter in range(10)
    ]
    assert index.stats.pages == 200
    assert index.note is None
    page_137 = next(passage for passage in index.passages if "Página 137." in passage.text)
    assert page_137.page is not None and page_137.end_page is not None
    assert page_137.page <= 137 <= page_137.end_page
    assert page_137.section_id == next(s.id for s in index.sections[6].children if s.title == "Seção 136")


def test_without_bookmarks_big_headings_make_the_sections_else_one_per_page(tmp_path: Path) -> None:
    headings = index_pdf(make.with_headings(tmp_path / "headings.pdf"), LIMITS)
    plain = index_pdf(make.plain(tmp_path / "plain.pdf"), LIMITS)

    assert _tree(headings.sections) == [
        ("Coberturas", 1, 1, []),
        ("Exclusões", 2, 2, [("Exclusões gerais", 2, 2, [])]),
        ("Sinistros", 3, 3, []),
    ]
    assert headings.outline == "Coberturas; Exclusões; Exclusões gerais; Sinistros"
    assert _tree(plain.sections) == [(f"Página {page}", page, page, []) for page in (1, 2, 3)]


@pytest.mark.parametrize(("build", "note"), [(lambda _: PDFS / "protected.pdf", PROTECTED), (make.image_only, NO_TEXT)])
def test_a_password_or_textless_pdf_is_indexed_by_outline_only_and_says_so(
    tmp_path: Path, build: object, note: str
) -> None:
    assert callable(build)
    index = index_pdf(build(tmp_path / "file.pdf"), LIMITS)

    assert index.note == note
    assert (index.sections, index.blocks, index.passages) == ([], [], [])
