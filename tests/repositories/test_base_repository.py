import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from acervo.core.errors import ConflictError, NotFoundError
from acervo.repositories.kb import KbRepository
from acervo.repositories.node import NodeRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.kb import KbCreate, KbUpdate
from acervo.schemas.node import NodeCreate
from acervo.schemas.organization import OrganizationRecord


@pytest.fixture
def kbs(session: AsyncSession) -> KbRepository:
    return KbRepository(session)


@pytest.fixture
async def organization(
    make_account: Callable[..., Awaitable[Any]], make_organization: Callable[..., Awaitable[OrganizationRecord]]
) -> uuid.UUID:
    return (await make_organization((await make_account()).id)).id


async def test_get_returns_what_create_wrote(kbs: KbRepository, organization: uuid.UUID) -> None:
    created = await kbs.create(
        KbCreate(organization_id=organization, name="Seguros", description="Apólices e sinistros")
    )

    assert await kbs.get(created.id) == created
    assert (created.name, created.description, created.deleted_at) == ("Seguros", "Apólices e sinistros", None)


async def test_get_missing_raises_not_found(kbs: KbRepository) -> None:
    missing = uuid.uuid4()

    with pytest.raises(NotFoundError) as raised:
        await kbs.get(missing)

    assert raised.value.details == {"id": str(missing)}


async def test_empty_update_emits_no_write(kbs: KbRepository, organization: uuid.UUID, engine: AsyncEngine) -> None:
    created = await kbs.create(KbCreate(organization_id=organization, name="Seguros"))
    statements: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        updated = await kbs.update(created.id, KbUpdate())
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)

    assert updated == created
    assert all(statement.lstrip().startswith("SELECT") for statement in statements)


async def test_update_changes_only_the_fields_set(kbs: KbRepository, organization: uuid.UUID) -> None:
    created = await kbs.create(KbCreate(organization_id=organization, name="Seguros", description="Apólices"))

    updated = await kbs.update(created.id, KbUpdate(name="Seguros · Operação"))

    assert (updated.name, updated.description) == ("Seguros · Operação", "Apólices")


async def test_unique_violation_raises_conflict_naming_the_constraint(
    kbs: KbRepository, organization: uuid.UUID, session: AsyncSession
) -> None:
    nodes = NodeRepository(session)
    kb = await kbs.create(KbCreate(organization_id=organization, name="Seguros"))
    page = NodeCreate(kb_id=kb.id, parent_id=None, kind="page", title="Renovação", sort="a")
    await nodes.create(page)

    with pytest.raises(ConflictError) as raised:
        await nodes.create(page.model_copy(update={"title": "RENOVAÇÃO", "sort": "b"}))

    assert raised.value.details == {"constraint": "uq_node_live_sibling_title"}


async def test_uow_rolls_back_on_exception(uow: UnitOfWork, organization: uuid.UUID) -> None:
    with pytest.raises(RuntimeError):
        async with uow:
            await uow.kbs.create(KbCreate(organization_id=organization, name="Seguros"))
            raise RuntimeError("boom")

    async with uow:
        assert await uow.kbs.count() == 0
