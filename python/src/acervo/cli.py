import json

import typer
from alembic import command
from alembic.config import Config

from acervo.api.app import app as api_app
from acervo.config import Settings

app = typer.Typer(no_args_is_help=True)
db = typer.Typer(no_args_is_help=True, help="The database.")
contract = typer.Typer(no_args_is_help=True, help="The HTTP contract.")
app.add_typer(db, name="db")
app.add_typer(contract, name="contract")


def alembic_config(url: str | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", "acervo:store/migrations")
    config.set_main_option("sqlalchemy.url", url or Settings().database_url)
    return config


@db.command()
def upgrade(url: str | None = typer.Option(None, help="Database URL; defaults to ACERVO_DATABASE_URL.")) -> None:
    """Migrate the database to the latest revision."""
    command.upgrade(alembic_config(url), "head")


@contract.command()
def schemas() -> None:
    """Print the API's OpenAPI document."""
    typer.echo(json.dumps(api_app.openapi(), indent=2, ensure_ascii=False))
