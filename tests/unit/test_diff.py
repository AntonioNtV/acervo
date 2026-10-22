from acervo.domain.diff import line_diff


def test_lines_in_reading_order() -> None:
    assert line_diff("# Prazo\nCinco dias\nFim\n", "# Prazo\nDez dias\nFim\nNovo\n") == [
        {"op": "same", "text": "# Prazo"},
        {"op": "del", "text": "Cinco dias"},
        {"op": "add", "text": "Dez dias"},
        {"op": "same", "text": "Fim"},
        {"op": "add", "text": "Novo"},
    ]


def test_from_an_empty_page() -> None:
    assert line_diff("", "Primeira\n") == [{"op": "add", "text": "Primeira"}]
