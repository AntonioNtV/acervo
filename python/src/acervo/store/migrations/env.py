import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import create_async_engine

from acervo.config import Settings
from acervo.store.db import async_url
from acervo.store.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

SCHEMA = Base.metadata.schema


def run(connection: Connection) -> None:
    # The version table lives in the schema, so the schema must exist before Alembic looks for it.
    connection.execute(text(f"create schema if not exists {SCHEMA}"))
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_name=lambda name, type_, _: type_ != "schema" or name == SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


async def main() -> None:
    url = config.get_main_option("sqlalchemy.url") or Settings().database_url
    # The role `acervo` would otherwise make `acervo` its default schema ("$user"), which autogenerate then
    # compares as unnamed and reports every table as new.
    engine = create_async_engine(async_url(url), connect_args={"server_settings": {"search_path": "public"}})
    async with engine.begin() as connection:
        await connection.run_sync(run)
    await engine.dispose()


asyncio.run(main())
