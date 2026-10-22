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
