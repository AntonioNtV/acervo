from collections.abc import Callable
from typing import Any

from acervo.domain.decisions import Choice
from acervo.model_clients.fakes import FakeDecider
from acervo.pipeline.curator.descent import MAX_DEPTH, descend, placement
from acervo.pipeline.curator.options import RECENT, label, pdf_options, text_options

Make = Callable[[Any], Any]
TREE = {
    "Bradesco": {"Residencial": ["Emissão de apólice.md"], "Auto": []},
    "Itaú": {"Residencial": ["Coberturas.md"]},
    "Porto": [],
}


async def test_the_beam_keeps_two_paths(make_snapshot: Make, fake_decider: FakeDecider) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {
        "descent:": {"Bradesco (pasta)": 0.5, "Itaú (pasta)": 0.3, "Porto (pasta)": 0.2},
        "descent:Bradesco": {"Auto (pasta)": 0.9, "Residencial (pasta)": 0.1},
        "descent:Itaú": {"Residencial (pasta)": 1.0},
        "descent:Bradesco/Auto": {"nova página aqui": 1.0},
        "descent:Itaú/Residencial": {"Coberturas (página)": 1.0},
    }

    descent = await descend("Franquia do auto", snap.tree, fake_decider, text_options, "descent", "Onde?")

    # Both of the two best paths are asked about, in one call per level; Porto is dropped.
    assert [[q.id for q in questions] for _, questions in fake_decider.calls] == [
        ["descent:"],
        ["descent:Bradesco", "descent:Itaú"],
        ["descent:Bradesco/Auto", "descent:Itaú/Residencial"],
    ]
    first, second = descent.ranked[:2]
    assert (first.node, first.landing, first.probability) == (snap["Bradesco/Auto"], "new_page", 0.45)
    assert (second.node, second.landing) == (snap["Itaú/Residencial/Coberturas.md"], "node")
    assert second.probability == 0.3


async def test_it_stops_at_a_leaf_page(make_snapshot: Make, fake_decider: FakeDecider) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {
        "descent:": {"Bradesco (pasta)": 1.0},
        "descent:Bradesco": {"Residencial (pasta)": 1.0},
        "descent:Bradesco/Residencial": {"Emissão de apólice (página)": 1.0},
    }

    descent = await descend("Prazo de emissão", snap.tree, fake_decider, text_options, "descent", "Onde?")

    assert descent.ranked[0].node == snap["Bradesco/Residencial/Emissão de apólice.md"]
    assert descent.ranked[0].landing == "node"
    assert len(fake_decider.calls) == 3


async def test_it_stops_at_save_here(make_snapshot: Make, fake_decider: FakeDecider) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {"descent:": {"Bradesco (pasta)": 1.0}, "descent:Bradesco": {"salvar aqui": 1.0}}

    descent = await descend("CG Bradesco", snap.tree, fake_decider, pdf_options, "descent", "Onde?")

    assert (descent.ranked[0].node, descent.ranked[0].landing) == (snap["Bradesco"], "here")
    # A PDF's options are folders and "save here": never a page.
    assert fake_decider.calls[1][1][0] == Choice(
        id="descent:Bradesco",
        question="Onde? Em: Bradesco.",
        options=("Residencial (pasta)", "Auto (pasta)", "salvar aqui"),
    )


async def test_it_stops_at_depth_six(make_snapshot: Make, fake_decider: FakeDecider) -> None:
    names = ["A", "B", "C", "D", "E", "F", "G", "H"]
    spec: Any = []
    for name in reversed(names):
        spec = {name: spec}
    snap = make_snapshot(spec)
    fake_decider.table = {f"descent:{'/'.join(names[:i])}": [1.0, 0] for i in range(len(names))}

    descent = await descend("Fundo", snap.tree, fake_decider, text_options, "descent", "Onde?")

    assert len(fake_decider.calls) == MAX_DEPTH
    assert (descent.ranked[0].node, descent.ranked[0].landing) == (snap["A/B/C/D/E/F"], "here")


async def test_past_255_children_the_recent_60_and_none_of_these(
    make_snapshot: Make, fake_decider: FakeDecider
) -> None:
    snap = make_snapshot({"Apólices": [f"Apólice {n:03d}.md" for n in range(300)]})
    fake_decider.table = {"descent:": {"Apólices (pasta)": 1.0}, "descent:Apólices": {"nenhuma destas": 1.0}}

    descent = await descend("Apólice 007", snap.tree, fake_decider, text_options, "descent", "Onde?")

    options = fake_decider.calls[1][1][0].options
    assert options[:RECENT] == tuple(f"Apólice {n:03d} (página)" for n in range(299, 299 - RECENT, -1))
    assert options[RECENT:] == ("nova página aqui", "nenhuma destas")
    assert descent.ranked[0].landing == "none"


async def test_text_descends_into_a_page_with_children(make_snapshot: Make, fake_decider: FakeDecider) -> None:
    snap = make_snapshot({"Bradesco": {"Auto.md": ["Franquias.md"]}})
    fake_decider.table = {
        "descent:": {"Bradesco (pasta)": 1.0},
        "descent:Bradesco": {"Auto (página)": 1.0},
        "descent:Bradesco/Auto": {"ficar neste nível": 1.0},
    }

    descent = await descend("Auto cobre vidros", snap.tree, fake_decider, text_options, "descent", "Onde?")

    # A page with children is gone into; there, staying is writing to that page. At a folder, staying is a new page.
    assert [choice.options for _, [choice] in fake_decider.calls] == [
        ("Bradesco (pasta)", "nova página aqui"),
        ("Auto (página)", "nova página aqui"),
        ("Franquias (página)", "ficar neste nível", "nova página aqui"),
    ]
    assert (descent.ranked[0].node, descent.ranked[0].landing) == (snap["Bradesco/Auto.md"], "node")


async def test_a_pdf_is_saved_under_a_page(make_snapshot: Make, fake_decider: FakeDecider) -> None:
    snap = make_snapshot({"Bradesco": {"Auto.md": ["Franquias.md"], "Residencial": []}})
    fake_decider.table = {
        "descent:": {"Bradesco (pasta)": 1.0},
        "descent:Bradesco": {"Auto (página)": 1.0},
        "descent:Bradesco/Auto": {"Franquias (página)": 1.0},
    }

    descent = await descend("Tabela de franquias", snap.tree, fake_decider, pdf_options, "descent", "Onde?")

    assert fake_decider.calls[1][1][0].options == ("Auto (página)", "Residencial (pasta)", "salvar aqui")
    # A page with no children stops the descent; the PDF goes under it, as a file.
    assert (descent.ranked[0].node, descent.ranked[0].landing) == (snap["Bradesco/Auto.md/Franquias.md"], "here")
    assert placement(snap.tree, descent.ranked[0]).landing == "here"


def test_an_option_shows_the_persons_description_first_then_the_built_one(make_snapshot: Make) -> None:
    snap = make_snapshot({"Bradesco": ["Auto.md", "Vida.md"]})
    folder = snap["Bradesco"].model_copy(update={"description": "Seguradora", "built": "Contém:\nAuto\nVida"})
    page = snap["Bradesco/Auto.md"].model_copy(update={"built": "Franquias; Vidros"})

    assert label(folder) == "Bradesco (pasta) — Seguradora — Contém:\nAuto\nVida"
    assert label(page) == "Auto (página) — Franquias; Vidros"
    assert label(snap["Bradesco/Vida.md"]) == "Vida (página)"
