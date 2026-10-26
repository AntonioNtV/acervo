import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Row, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import acervo.db.models  # noqa: F401  registers every table on Base.metadata
from acervo.db.base import Base

SCHEMA = Base.metadata.schema
EARLY, TYPED, FIXED = (datetime(2026, 10, 1, hour, tzinfo=UTC) for hour in (9, 10, 11))


async def _autogenerate_diff(database_url: str) -> list[object]:
    # As migrations/env.py connects: `public` first, so the `acervo` schema is compared by name.
    engine = create_async_engine(
        database_url, poolclass=NullPool, connect_args={"server_settings": {"search_path": "public"}}
    )
    options = {
        "include_schemas": True,
        "version_table_schema": SCHEMA,
        "include_name": lambda name, type_, _: type_ != "schema" or name == SCHEMA,
    }
    async with engine.connect() as connection:
        diff = await connection.run_sync(
            lambda sync: compare_metadata(MigrationContext.configure(sync, opts=options), Base.metadata)
        )
    await engine.dispose()
    return list(diff)


async def _tables(database_url: str) -> set[str]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names(schema=SCHEMA)))
    await engine.dispose()
    return names


def test_upgrade_downgrade_upgrade(migrations: Config, database_url: str) -> None:
    command.downgrade(migrations, "base")
    assert asyncio.run(_tables(database_url)) == {"alembic_version"}

    command.upgrade(migrations, "head")
    every_table = {table.name for table in Base.metadata.sorted_tables}
    assert asyncio.run(_tables(database_url)) == every_table | {"alembic_version"}


def test_autogenerate_has_no_diff(database_url: str) -> None:
    assert asyncio.run(_autogenerate_diff(database_url)) == []


async def _execute(database_url: str, sql: str, **params: Any) -> list[Row[Any]]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        result = await connection.execute(text(sql), params)
        rows = list(result) if result.returns_rows else []
    await engine.dispose()
    return rows


def _sql(database_url: str, sql: str, **params: Any) -> list[Row[Any]]:
    return asyncio.run(_execute(database_url, sql, **params))


def _pages(database_url: str, titles: list[str]) -> list[uuid.UUID]:
    kb_id = uuid.uuid4()
    _sql(database_url, "insert into acervo.kb (id, name) values (:id, 'Migração')", id=kb_id)
    ids = [uuid.uuid4() for _ in titles]
    for node_id, title in zip(ids, titles, strict=True):
        _sql(
            database_url,
            "insert into acervo.node (id, kb_id, kind, title, sort) values (:id, :kb_id, 'page', :title, :title)",
            id=node_id,
            kb_id=kb_id,
            title=title,
        )
    return ids


def _version(database_url: str, node_id: uuid.UUID, markdown: str, at: datetime) -> uuid.UUID:
    version_id = uuid.uuid4()
    _sql(
        database_url,
        "insert into acervo.page_version (id, node_id, markdown, author, created_at) "
        "values (:id, :node_id, :md, 'user', :at)",
        id=version_id,
        node_id=node_id,
        md=markdown,
        at=at,
    )
    return version_id


def _versions(database_url: str, node_id: uuid.UUID) -> list[tuple[str, str]]:
    query = "select markdown, author from acervo.page_version where node_id = :node_id order by created_at"
    return [(row.markdown, row.author) for row in _sql(database_url, query, node_id=node_id)]


def _drafts(database_url: str) -> int:
    count: int = _sql(database_url, "select count(*) from acervo.page_draft")[0][0]
    return count


@pytest.fixture
def at_head(migrations: Config, database_url: str) -> Iterator[None]:
    """Leaves the database at head and without the rows the test put in it, for the tests that follow."""
    yield
    # Before the upgrade: 0008 refuses bases that no account can own.
    pages = "select n.id from acervo.node n join acervo.kb k on k.id = n.kb_id where k.name = 'Migração'"
    for table in ("page_draft", "page_link", "page_version"):
        column = "from_node_id" if table == "page_link" else "node_id"
        _sql(database_url, f"delete from acervo.{table} where {column} in ({pages})")
    _sql(database_url, f"delete from acervo.node where id in ({pages})")
    _sql(database_url, "delete from acervo.kb where name = 'Migração'")
    command.upgrade(migrations, "head")


@pytest.mark.usefixtures("at_head")
def test_0002_turns_f1_drafts_into_versions(migrations: Config, database_url: str) -> None:
    command.downgrade(migrations, "0001")
    changed, same, fixed = _pages(database_url, ["Emissão", "Renovação", "Vistoria"])
    drafts = [
        (changed, _version(database_url, changed, "Antes\n", EARLY), "Digitado\n"),
        (same, _version(database_url, same, "Igual\n", EARLY), "Igual\n"),
        (fixed, _version(database_url, fixed, "Ver [[Sinistro]]\n", EARLY), "Digitado [[Sinistro]]\n"),
    ]
    for node_id, version_id, markdown in drafts:
        _sql(
            database_url,
            "insert into acervo.page_draft (node_id, markdown, base_version_id, updated_at) "
            "values (:node_id, :md, :version_id, :at)",
            node_id=node_id,
            md=markdown,
            version_id=version_id,
            at=TYPED,
        )
    _version(database_url, fixed, "Ver [[Aviso de sinistro]]\n", FIXED)

    command.upgrade(migrations, "0002")

    assert _versions(database_url, changed) == [("Antes\n", "user"), ("Digitado\n", "user")]
    assert _versions(database_url, same) == [("Igual\n", "user")]
    assert _versions(database_url, fixed) == [
        ("Ver [[Sinistro]]\n", "user"),
        ("Digitado [[Sinistro]]\n", "user"),
        ("Ver [[Aviso de sinistro]]\n", "user"),
    ]
    typed_at = "select created_at from acervo.page_version where node_id = :node_id and markdown = 'Digitado\n'"
    assert _sql(database_url, typed_at, node_id=changed)[0][0] == TYPED
    assert _drafts(database_url) == 0


@pytest.mark.usefixtures("at_head")
def test_0002_downgrade_keeps_the_working_text_as_a_version(migrations: Config, database_url: str) -> None:
    # Versions still had an author before 0004.
    command.downgrade(migrations, "0003")
    changed, same = _pages(database_url, ["Emissão", "Renovação"])
    for node_id, markdown in ((changed, "Digitado\n"), (same, "Igual\n")):
        _version(database_url, node_id, "Igual\n", EARLY)
        _sql(
            database_url,
            "insert into acervo.page_draft (node_id, markdown, revision, started_at, updated_at) "
            "values (:node_id, :md, 3, :at, :at)",
            node_id=node_id,
            md=markdown,
            at=TYPED,
        )

    command.downgrade(migrations, "0001")

    assert _versions(database_url, changed) == [("Igual\n", "user"), ("Digitado\n", "user")]
    assert _versions(database_url, same) == [("Igual\n", "user")]
    assert _drafts(database_url) == 0
