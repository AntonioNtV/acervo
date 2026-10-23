from acervo.domain.index import Block, DocIndex, DocStats, Section
from acervo.pipeline.search.menus import menu
from acervo.pipeline.search.previews import section_previews
from acervo.pipeline.search.tree import SearchNode

FILLER = "O segurado deve manter o veículo em boas condições de uso e conservação durante toda a vigência."


def _index(sections: dict[str, list[str]]) -> DocIndex:
    blocks: list[Block] = []
    found: list[Section] = []
    for number, (title, texts) in enumerate(sections.items(), start=1):
        ids = []
        for text in texts:
            blocks.append(Block(id=f"b{len(blocks)}", kind="paragraph", text=text, page=number))
            ids.append(blocks[-1].id)
        found.append(Section(id=f"s{number}", title=title, level=1, page=number, end_page=number, block_ids=ids))
    return DocIndex(
        version=1,
        source="pdf",
        outline="; ".join(sections),
        sections=found,
        blocks=blocks,
        passages=[],
        stats=DocStats(pages=len(sections), words=0, tables=0, figures=0),
    )


def test_the_excerpts_follow_the_question() -> None:
    index = _index(
        {
            "Condições gerais": [
                "Este capítulo trata das condições gerais do seguro de automóvel.",
                *[FILLER] * 6,
                "A franquia reduzida custa 30% a mais no prêmio anual do seguro.",
                *[FILLER] * 6,
            ],
            "Assistência": ["Guincho em até 200 km e carro reserva por sete dias."],
        }
    )

    preview = section_previews(index, "quanto custa a franquia reduzida?", 1200)["s1"]

    assert preview.startswith("Páginas 1–1\nTrechos (parciais):")
    assert "franquia reduzida custa 30%" in preview
    # The opening is kept too, so Jev knows what the section is about.
    assert "Este capítulo trata das condições gerais" in preview
    # A repeated paragraph is not shown twice.
    assert preview.count("boas condições") <= 1


def test_at_most_three_excerpts() -> None:
    risks = ["incêndio", "roubo", "colisão", "alagamento", "granizo", "vendaval", "furto", "queda", "raio"]
    index = _index(
        {"Coberturas": [f"A cobertura de {risk} protege o veículo contra o risco de {risk}." for risk in risks]}
    )

    preview = section_previews(index, "cobertura risco", 1200)["s1"]

    assert preview.count("\n[Coberturas, p. 1] ") == 3


def test_a_long_section_fits_in_the_description_cap() -> None:
    title = "Cláusulas especiais"
    index = _index({title: [f"Cláusula {i}: " + "texto longo da cláusula " * 80 for i in range(10)]})

    preview = section_previews(index, "cláusula", 1200)["s1"]

    assert len(f"{title}\n{preview}") <= 1200


def test_the_persons_description_comes_first_and_survives_the_cap() -> None:
    node = SearchNode(
        id="s",
        node_id=None,
        kind="file",
        title="Tabela auto 2026.pdf",
        path=[],
        person_description="Preços oficiais do auto, vigentes em 2026.",
        built="x" * 3000,
    )

    option = menu("route:a", [node], "preço", 1200).options[0]

    assert option.startswith("Tabela auto 2026.pdf\nPreços oficiais do auto, vigentes em 2026.\nxxx")
    assert len(option) == 1200
