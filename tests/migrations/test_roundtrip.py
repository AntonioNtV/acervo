import asyncio

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import acervo.db.models  # noqa: F401  registers every table on Base.metadata
from acervo.db.base import Base

SCHEMA = Base.metadata.schema


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
