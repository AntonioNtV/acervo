from acervo.pipeline.search import questions
from acervo.pipeline.search.menus import bounded, menu, packs
from acervo.pipeline.search.tree import SearchNode


def _nodes(count: int) -> list[SearchNode]:
    return [SearchNode(id=f"n{i}", node_id=None, kind="folder", title=f"Pasta {i}", path=[]) for i in range(count)]


async def test_more_than_a_menu_of_children_are_grouped() -> None:
    groups = bounded(_nodes(100), "big", 64, 1200)

    assert [len(await group.children()) for group in groups] == [64, 36]
    assert groups[0].kind == "group"
    assert groups[0].describe("").startswith("Grupo\nPasta 0; Pasta 1")


async def test_a_huge_folder_is_grouped_at_every_level() -> None:
    groups = bounded(_nodes(10_000), "huge", 64, 1200)

    assert len(groups) <= 64
    for group in groups:
        assert 0 < len(await group.children()) <= 64


def test_a_short_list_is_left_alone() -> None:
    nodes = _nodes(64)
    assert bounded(nodes, "ok", 64, 1200) is nodes


def test_a_menu_ends_with_none_and_cuts_descriptions() -> None:
    nodes = [SearchNode(id="a", node_id=None, kind="file", title="A", path=[], built="x" * 2000)]

    choice = menu("route:a", nodes, "pergunta", 1200)

    assert choice.options[-1] == questions.NONE
    assert len(choice.options[0]) == 1200


def test_menus_are_packed_four_to_a_call() -> None:
    menus = [questions.route(f"route:{i}", ["A", "B"]) for i in range(9)]

    assert [len(pack) for pack in packs(menus, 4)] == [4, 4, 1]
