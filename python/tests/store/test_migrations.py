import asyncio

from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from typer.testing import CliRunner

from acervo.cli import alembic_config, app
from acervo.store.models import Base


async def _tables(url: str) -> set[str]:
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        rows = await connection.execute(
            text("select table_name from information_schema.tables where table_schema = 'acervo'")
        )
        names = set(rows.scalars())
    await engine.dispose()
    return names


def test_upgrade_and_downgrade_on_a_scratch_database(scratch_database_url: str) -> None:
    result = CliRunner().invoke(app, ["db", "upgrade", "--url", scratch_database_url])
    assert result.exit_code == 0, result.output

    every_table = {table.name for table in Base.metadata.sorted_tables}
    assert asyncio.run(_tables(scratch_database_url)) == every_table | {"alembic_version"}

    command.downgrade(alembic_config(scratch_database_url), "base")
    assert asyncio.run(_tables(scratch_database_url)) == {"alembic_version"}
