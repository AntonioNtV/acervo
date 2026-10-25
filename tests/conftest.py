import asyncio
import hashlib
import mimetypes
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import aioboto3
import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from acervo.core.settings import Settings
from acervo.db.models import File, Node, PageVersion
from acervo.db.session import async_url
from acervo.repositories.kb import KbRepository
from acervo.repositories.node import NodeRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.kb import KbCreate, KbRead
from acervo.schemas.node import NodeCreate

ROOT = Path(__file__).resolve().parents[1]
API_KEY = "test-api-key"
# acervo.api.main builds its app from the environment at import; the tests then build their own with create_app.
os.environ.setdefault("API_KEY", API_KEY)


def _base_settings() -> Settings:
    return Settings(api_key=SecretStr(API_KEY))


async def _admin(sql: str) -> None:
    engine = create_async_engine(
        async_url(_base_settings().database_url), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    async with engine.connect() as connection:
        await connection.execute(text(sql))
    await engine.dispose()


def _s3(settings: Settings) -> Any:
    return aioboto3.Session().client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )


async def _create_bucket(settings: Settings) -> None:
    async with _s3(settings) as s3:
        await s3.create_bucket(Bucket=settings.s3_bucket)


async def _drop_bucket(settings: Settings) -> None:
    async with _s3(settings) as s3:
        async for page in s3.get_paginator("list_objects_v2").paginate(Bucket=settings.s3_bucket):
            for item in page.get("Contents", []):
                await s3.delete_object(Bucket=settings.s3_bucket, Key=item["Key"])
        await s3.delete_bucket(Bucket=settings.s3_bucket)


def alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """A database of its own for this session (parallel worktrees share the server), migrated to head."""
    name = f"acervo_test_{uuid.uuid4().hex[:12]}"
    asyncio.run(_admin(f'create database "{name}"'))
    url = make_url(async_url(_base_settings().database_url)).set(database=name).render_as_string(hide_password=False)
    try:
        command.upgrade(alembic_config(url), "head")
        yield url
    finally:
        asyncio.run(_admin(f'drop database "{name}" with (force)'))


@pytest.fixture
def migrations(database_url: str) -> Config:
    """Alembic pointed at this session's database."""
    return alembic_config(database_url)


@pytest.fixture(scope="session")
def test_settings(database_url: str) -> Iterator[Settings]:
    """Settings on this session's database and on a bucket of its own, so worktrees running at once never meet."""
    settings = _base_settings().model_copy(
        update={"database_url": database_url, "s3_bucket": f"acervo-test-{uuid.uuid4().hex[:8]}"}
    )
    asyncio.run(_create_bucket(settings))
    yield settings
    asyncio.run(_drop_bucket(settings))


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """A connection inside a transaction rolled back at the end of the test."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        yield connection
        await transaction.rollback()


@pytest.fixture
def session_factory(connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    # Commits and rollbacks inside the test act on savepoints of the outer transaction.
    return async_sessionmaker(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
def uow(session_factory: async_sessionmaker[AsyncSession]) -> UnitOfWork:
    """A UnitOfWork not yet entered: the test opens it with `async with uow`."""
    return UnitOfWork(session_factory)


@pytest.fixture
def storage(test_settings: Settings) -> Settings:
    """The S3 endpoint, keys and this session's bucket."""
    return test_settings


@dataclass
class Tree:
    kb: KbRead
    # By path as written in the spec: "Bradesco/Residencial/Emissão de apólice.md". ORM rows, because the
    # concept packages' tests change them in place until cards 03-05 move those tests onto the services.
    nodes: dict[str, Node] = field(default_factory=dict)

    def __getitem__(self, path: str) -> Node:
        return self.nodes[path]


TreeSpec = dict[str, Any] | list[Any] | None


def _children(spec: TreeSpec) -> list[tuple[str, TreeSpec]]:
    if spec is None:
        return []
    if isinstance(spec, dict):
        return list(spec.items())
    items: list[tuple[str, TreeSpec]] = []
    for item in spec:
        items += _children(item) if isinstance(item, dict) else [(item, None)]
    return items


@pytest.fixture
def make_tree(session: AsyncSession) -> Callable[..., Awaitable[Tree]]:
    """Builds a base from a dict. `.md` names are pages with one version, other names with an extension are
    files with fake metadata and no bytes, and names without one are folders."""
    kbs, nodes = KbRepository(session), NodeRepository(session)

    async def add(tree: Tree, parent: Node | None, prefix: str, spec: TreeSpec) -> None:
        for index, (name, children) in enumerate(_children(spec)):
            suffix = PurePosixPath(name).suffix
            kind = "page" if suffix == ".md" else "file" if suffix else "folder"
            created = await nodes.create(
                NodeCreate(
                    kb_id=tree.kb.id,
                    parent_id=parent.id if parent else None,
                    kind=kind,
                    title=name.removesuffix(".md") if kind == "page" else name,
                    sort=f"a{index:04d}",
                )
            )
            node = await session.get_one(Node, created.id)
            path = f"{prefix}{name}"
            tree.nodes[path] = node
            if kind == "page":
                session.add(PageVersion(node_id=node.id, markdown=f"# {node.title}\n"))
            elif kind == "file":
                sha256 = hashlib.sha256(f"{tree.kb.id}/{path}".encode()).hexdigest()
                session.add(
                    File(
                        node_id=node.id,
                        storage_key=f"kb/{tree.kb.id}/{sha256}",
                        sha256=sha256,
                        size=0,
                        mime=mimetypes.guess_type(name)[0] or "application/octet-stream",
                    )
                )
            else:
                await add(tree, node, f"{path}/", children)
        await session.flush()

    async def make(spec: TreeSpec, name: str = "Seguros · Operação") -> Tree:
        tree = Tree(await kbs.create(KbCreate(name=name)))
        await add(tree, None, "", spec)
        return tree

    return make
