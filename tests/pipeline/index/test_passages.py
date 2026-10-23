import importlib.util
from pathlib import Path

from acervo.core.settings import RetrievalLimits
from acervo.pipeline.index.pdf import index_pdf

PDFS = Path(__file__).resolve().parents[2] / "fixtures" / "pdfs"
HEADER = "| Modelo | Ano | Prêmio |\n| --- | --- | --- |"


def test_a_table_across_two_pages_is_cut_between_rows_and_every_passage_starts_with_its_header(
    tmp_path: Path,
) -> None:
    spec = importlib.util.spec_from_file_location("make_pdfs", PDFS / "make.py")
    assert spec is not None and spec.loader is not None
    make = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make)
    limits = RetrievalLimits(passage_chars=700, passage_overlap=100)

    index = index_pdf(make.table_across_pages(tmp_path / "table.pdf", rows=80), limits)

    assert len(index.passages) > 3
    assert {(passage.page, passage.end_page) for passage in index.passages} >= {(1, 2), (2, 2)}
    rows: list[str] = []
    for passage in index.passages:
        assert passage.text.startswith(HEADER + "\n")
        assert len(passage.text) <= limits.passage_chars
        rows += passage.text.removeprefix(HEADER + "\n").split("\n")
    assert rows == [f"| Carro-{row} | {2000 + row % 26} | {1000 + row} |" for row in range(80)]
    assert index.stats.tables == 1
