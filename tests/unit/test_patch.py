from datetime import date
from uuid import UUID

import pytest

from acervo.domain.patch import Patch, Stale, apply, provenance

ORIGIN = "<!-- origem: chat · 2026-10-22 · proposta 8f3a -->"
PAGE = "# Emissão de apólice\n\n## Documentos\n- RG\n- CPF\n\n## Prazos\nCinco dias.\n"


def test_provenance_names_the_source_the_day_and_the_proposal() -> None:
    proposal_id = UUID("8f3a0000-0000-0000-0000-000000000000")

    assert provenance("chat", date(2026, 10, 22), proposal_id) == ORIGIN


def test_append_adds_lines_at_the_end_of_the_section_each_with_its_origin() -> None:
    patched = apply(PAGE, Patch("documentos", "append", ["- Comprovante de residência"]), ORIGIN)

    assert patched == (
        "# Emissão de apólice\n\n## Documentos\n- RG\n- CPF\n"
        f"- Comprovante de residência {ORIGIN}\n\n## Prazos\nCinco dias.\n"
    )


def test_append_to_the_text_before_the_first_heading() -> None:
    assert apply("", Patch("", "append", ["# Prazos", "", "Cinco dias."]), ORIGIN) == (
        f"# Prazos\n\nCinco dias. {ORIGIN}\n"
    )


def test_insert_after_puts_the_lines_right_after_the_line() -> None:
    patched = apply(PAGE, Patch("documentos", "insert_after", ["- CNH"], line="- RG"), ORIGIN)

    assert "- RG\n- CNH " + ORIGIN + "\n- CPF\n" in patched


def test_replace_swaps_the_line_for_the_new_ones() -> None:
    patched = apply(PAGE, Patch("prazos", "replace", ["Sete dias."], line="Cinco dias."), ORIGIN)

    assert patched.endswith(f"## Prazos\nSete dias. {ORIGIN}\n")
    assert "Cinco dias." not in patched


def test_new_section_goes_after_the_section_without_a_comment_on_its_heading() -> None:
    patched = apply(PAGE, Patch("documentos", "new_section", ["## Taxas", "Isento."]), ORIGIN)

    assert f"- CPF\n\n## Taxas\nIsento. {ORIGIN}\n\n## Prazos\n" in patched


def test_rebase_finds_a_moved_anchor() -> None:
    moved = "# Emissão de apólice\n\n## Prazos\nCinco dias.\n\n## Documentos\n- RG\n"

    patched = apply(moved, Patch("documentos", "append", ["- CPF"]), ORIGIN)

    assert patched == f"# Emissão de apólice\n\n## Prazos\nCinco dias.\n\n## Documentos\n- RG\n- CPF {ORIGIN}\n"


def test_a_replace_never_takes_the_heading() -> None:
    page = "# Auto\n\n## Coberturas\n\n- Franquia R$ 500\n"

    with pytest.raises(Stale):
        apply(page, Patch("coberturas", "replace", ["## Coberturas"], "## Coberturas"), ORIGIN)


@pytest.mark.parametrize(
    "change",
    [
        Patch("documentos", "append", ["- CPF"]),
        Patch("prazos", "replace", ["Sete dias."], line="Seis dias."),
        Patch("prazos", "insert_after", ["Úteis."], line="- RG"),
    ],
)
def test_a_gone_anchor_or_line_is_stale(change: Patch) -> None:
    with pytest.raises(Stale):
        apply("# Emissão de apólice\n\n## Prazos\nCinco dias.\n\n## Outros\n- RG\n", change, ORIGIN)
