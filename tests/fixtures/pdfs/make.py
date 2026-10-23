"""Builds the indexer's test PDFs with PyMuPDF, into a folder the test gives (a 200-page file is not committed)."""

from pathlib import Path

import pymupdf

BODY = (
    "A apólice cobre danos ao imóvel causados por incêndio, raio e explosão. "
    "O segurado deve comunicar o sinistro em até sete dias."
)
HEADER = ["Modelo", "Ano", "Prêmio"]


def _paragraph(page: pymupdf.Page, y: float, text: str = BODY, size: float = 11) -> float:
    """Writes `text` as a block at `y` and returns the `y` below it."""
    rect = pymupdf.Rect(72, y, page.rect.width - 72, y + 60)
    page.insert_textbox(rect, text, fontsize=size)
    return y + 70


def with_bookmarks(path: Path, pages: int = 200) -> Path:
    """`pages` pages of paragraphs; bookmarks: a chapter every 20 pages, a section every 5 inside it."""
    document = pymupdf.open()
    toc: list[list[int | str]] = []
    for number in range(1, pages + 1):
        page = document.new_page()
        y = 72.0
        for _ in range(4):
            y = _paragraph(page, y, f"Página {number}. {BODY}")
        if number % 20 == 1:
            toc.append([1, f"Capítulo {number // 20 + 1}", number])
        if number % 5 == 1:
            toc.append([2, f"Seção {number}", number])
    document.set_toc(toc)
    document.save(path)
    return path


def with_headings(path: Path) -> Path:
    """Three pages, no bookmarks: big headings, one of them with a smaller sub-heading, over 11 pt paragraphs."""
    document = pymupdf.open()
    for number, title in enumerate(["Coberturas", "Exclusões", "Sinistros"], start=1):
        page = document.new_page()
        page.insert_text((72, 90), title, fontsize=20)
        y = _paragraph(page, 120)
        if number == 2:
            page.insert_text((72, y + 10), "Exclusões gerais", fontsize=15)
            y += 40
        _paragraph(page, y)
    document.save(path)
    return path


def plain(path: Path) -> Path:
    """Three pages of same-size paragraphs: no bookmarks, no headings."""
    document = pymupdf.open()
    for _ in range(3):
        _paragraph(document.new_page(), 72)
    document.save(path)
    return path


def table_across_pages(path: Path, rows: int = 80) -> Path:
    """A ruled table whose header is on the first page only and whose rows continue on the second; a bookmark
    makes the two pages one section."""
    document = pymupdf.open()
    per_page = rows // 2
    for part in range(2):
        page = document.new_page()
        cells = ([HEADER] if part == 0 else []) + [
            [f"Carro-{row}", str(2000 + row % 26), str(1000 + row)]
            for row in range(part * per_page, (part + 1) * per_page)
        ]
        for line, cell_texts in enumerate(cells):
            top = 72 + line * 16
            for column, text in enumerate(cell_texts):
                rect = pymupdf.Rect(72 + column * 150, top, 222 + column * 150, top + 16)
                page.draw_rect(rect, color=(0, 0, 0), width=0.5)
                page.insert_text((rect.x0 + 4, rect.y1 - 4), text, fontsize=9)
    document.set_toc([[1, "Tabela de prêmios", 1]])
    document.save(path)
    return path


def image_only(path: Path) -> Path:
    """One page holding an image and no text, like a scan."""
    document = pymupdf.open()
    page = document.new_page()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    pixmap.clear_with(200)
    page.insert_image(pymupdf.Rect(72, 72, 472, 472), pixmap=pixmap)
    document.save(path)
    return path
