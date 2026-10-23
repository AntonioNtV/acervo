from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from acervo.domain.index import DocIndex, DocStats
from acervo.repositories.node_index import NodeIndexRepository

MakeTree = Callable[..., Awaitable[Any]]


def _index(outline: str) -> DocIndex:
    return DocIndex(
        version=1,
        source="pdf",
        outline=outline,
        sections=[],
        blocks=[],
        passages=[],
        stats=DocStats(pages=1, words=0, tables=0, figures=0),
    )


@pytest.fixture
def indexes(session: AsyncSession) -> NodeIndexRepository:
    return NodeIndexRepository(session)


async def test_a_build_swaps_in_and_the_old_index_stays_readable(
    indexes: NodeIndexRepository, make_tree: MakeTree
) -> None:
    tree = await make_tree({"Bradesco": ["CG 2026.pdf", "Renovação.md"]})
    pdf, page = tree["Bradesco/CG 2026.pdf"].id, tree["Bradesco/Renovação.md"].id

    await indexes.start(pdf, "v1")
    building = await indexes.get(pdf)
    assert building is not None and (building.status, building.parsed) == ("building", None)
    assert await indexes.finish(pdf, "v1", _index("Coberturas"))

    await indexes.start(pdf, "v2")
    while_building = await indexes.get(pdf)
    assert while_building is not None
    assert (while_building.status, while_building.version_key, while_building.building_key) == ("building", "v1", "v2")
    assert while_building.parsed == _index("Coberturas")

    assert await indexes.finish(pdf, "v2", _index("Coberturas 2027"))
    ready = await indexes.get(pdf)
    assert ready is not None
    assert (ready.status, ready.version_key, ready.building_key, ready.outline) == (
        "ready",
        "v2",
        None,
        "Coberturas 2027",
    )
    assert await indexes.states([pdf, page]) == {pdf: "ready", page: "none"}


async def test_a_superseded_build_changes_nothing(indexes: NodeIndexRepository, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["CG 2026.pdf"]})
    pdf = tree["Bradesco/CG 2026.pdf"].id
    await indexes.start(pdf, "v1")
    await indexes.finish(pdf, "v1", _index("Coberturas"))
    await indexes.start(pdf, "v2")
    await indexes.start(pdf, "v3")

    assert not await indexes.finish(pdf, "v2", _index("Velho"))
    assert not await indexes.fail(pdf, "v2", "senha")

    stored = await indexes.get(pdf)
    assert stored is not None
    assert (stored.status, stored.version_key, stored.building_key, stored.outline) == (
        "building",
        "v1",
        "v3",
        "Coberturas",
    )


async def test_a_failed_build_keeps_the_previous_index(indexes: NodeIndexRepository, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["CG 2026.pdf"]})
    pdf = tree["Bradesco/CG 2026.pdf"].id
    await indexes.start(pdf, "v1")
    await indexes.finish(pdf, "v1", _index("Coberturas"))
    await indexes.start(pdf, "v2")

    assert await indexes.fail(pdf, "v2", "arquivo corrompido")

    stored = await indexes.get(pdf)
    assert stored is not None
    assert (stored.status, stored.error, stored.building_key) == ("failed", "arquivo corrompido", None)
    assert stored.parsed == _index("Coberturas")
    await indexes.start(pdf, "v2")
    retried = await indexes.get(pdf)
    assert retried is not None and (retried.status, retried.error) == ("building", None)


async def test_outlines_never_load_the_parsed_index(
    indexes: NodeIndexRepository, connection: AsyncConnection, make_tree: MakeTree
) -> None:
    tree = await make_tree({"Bradesco": ["CG 2026.pdf", "Tabela.pdf"]})
    ready, building = tree["Bradesco/CG 2026.pdf"].id, tree["Bradesco/Tabela.pdf"].id
    await indexes.start(ready, "v1")
    await indexes.finish(ready, "v1", _index("Coberturas"))
    await indexes.start(building, "v1")
    statements: list[str] = []

    def record(*args: Any) -> None:
        statements.append(args[2])

    event.listen(connection.sync_connection, "before_cursor_execute", record)
    try:
        assert await indexes.outlines([ready, building]) == {ready: "Coberturas"}
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", record)
    assert statements and not any("parsed" in statement for statement in statements)
