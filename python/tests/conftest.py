import asyncio
import hashlib
import mimetypes
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

import aioboto3
import pytest
from alembic import command
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from acervo.cli import alembic_config
from acervo.config import Settings
from acervo.store import db
from acervo.store.models import File, Kb, Node, PageVersion


async def _admin(sql: str) -> None:
    engine = create_async_engine(db.async_url(Settings().database_url), isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        await connection.execute(text(sql))
    await engine.dispose()


def _database_url(name: str) -> str:
    url = make_url(db.async_url(Settings().database_url)).set(database=name)
    return url.render_as_string(hide_password=False)


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


@pytest.fixture(scope="session", autouse=True)
def test_settings() -> Iterator[Settings]:
    """A database migrated to head and a bucket of this session's own, so worktrees running at once never meet."""
    suffix = uuid.uuid4().hex[:8]
    name = f"acervo_test_{suffix}"
    asyncio.run(_admin(f"create database {name}"))
    command.upgrade(alembic_config(_database_url(name)), "head")
    with pytest.MonkeyPatch.context() as env:
        env.setenv("ACERVO_DATABASE_URL", _database_url(name))
        env.setenv("ACERVO_S3_BUCKET", f"acervo-test-{suffix}")
        db.engine.cache_clear()
        db.session_factory.cache_clear()
        settings = Settings()
        asyncio.run(_create_bucket(settings))
        yield settings
        asyncio.run(_drop_bucket(settings))
    db.engine.cache_clear()
    db.session_factory.cache_clear()
    asyncio.run(_admin(f"drop database {name} with (force)"))


@pytest.fixture
def scratch_database_url() -> Iterator[str]:
    """An empty database, for tests that run the migrations themselves."""
    name = f"acervo_scratch_{uuid.uuid4().hex[:8]}"
    asyncio.run(_admin(f"create database {name}"))
    yield _database_url(name)
    asyncio.run(_admin(f"drop database {name} with (force)"))


@pytest.fixture
async def session(test_settings: Settings) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.begin()
        async with AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        await connection.rollback()
    await engine.dispose()


@pytest.fixture
def storage(test_settings: Settings) -> Settings:
    """The S3 endpoint, keys and this session's bucket."""
    return test_settings


@dataclass
class Tree:
    kb: Kb
    # By path as written in the spec: "Bradesco/Residencial/Emissão de apólice.md".
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

    async def add(tree: Tree, parent: Node | None, prefix: str, spec: TreeSpec) -> None:
        for index, (name, children) in enumerate(_children(spec)):
            suffix = PurePosixPath(name).suffix
            kind = "page" if suffix == ".md" else "file" if suffix else "folder"
            node = Node(
                id=uuid.uuid4(),
                kb_id=tree.kb.id,
                parent_id=parent.id if parent else None,
                kind=kind,
                title=name.removesuffix(".md") if kind == "page" else name,
                sort=f"a{index:04d}",
            )
            session.add(node)
            await session.flush()
            path = f"{prefix}{name}"
            tree.nodes[path] = node
            if kind == "page":
                session.add(PageVersion(node_id=node.id, markdown=f"# {node.title}\n", author="user"))
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
        kb = Kb(id=uuid.uuid4(), name=name)
        session.add(kb)
        await session.flush()
        tree = Tree(kb)
        await add(tree, None, "", spec)
        return tree

    return make
