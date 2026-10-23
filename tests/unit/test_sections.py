from acervo.domain.sections import Section, sections


def test_headings_become_anchors() -> None:
    markdown = (
        "# Emissão de apólice\n\n## Documentos\n- RG\n\n### Detalhe\n## Prazos e condições ##\n"
        "```\n## não é título\n```\n## Documentos\n"
    )

    assert sections(markdown) == [
        Section("documentos", "Documentos"),
        Section("prazos-e-condicoes", "Prazos e condições"),
        Section("documentos-2", "Documentos"),
    ]


def test_anchors_are_never_empty_and_never_repeat() -> None:
    markdown = "## ✅\n## Notas\n## Notas 2\n## Notas\n## ✅\n"

    assert [section.anchor for section in sections(markdown)] == ["secao", "notas", "notas-2", "notas-3", "secao-2"]
