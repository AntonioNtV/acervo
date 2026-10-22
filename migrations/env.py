import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import acervo.db.models  # noqa: F401  registers every table on Base.metadata
from acervo.core.settings import get_settings
from acervo.db.base import Base
from acervo.db.session import async_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
SCHEMA = target_metadata.schema


def database_url() -> str:
    # Tests point alembic at their own database through sqlalchemy.url.
    return async_url(config.get_main_option("sqlalchemy.url") or get_settings().database_url)


def do_run_migrations(connection: Connection) -> None:
    # The version table lives in the schema, so the schema must exist before Alembic looks for it.
    connection.execute(text(f"create schema if not exists {SCHEMA}"))
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_name=lambda name, type_, _: type_ != "schema" or name == SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # The role `acervo` would otherwise make `acervo` its default schema ("$user"), which autogenerate then
    # compares as unnamed and reports every table as new.
    engine = create_async_engine(
        database_url(), poolclass=NullPool, connect_args={"server_settings": {"search_path": "public"}}
    )
    async with engine.begin() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


asyncio.run(run_migrations_online())
