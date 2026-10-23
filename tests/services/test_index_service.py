from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.node import NodeAdd
from acervo.schemas.page import PageTextPut
from acervo.services import index_service
from acervo.services.file_service import FileService
from acervo.services.index_service import FAILED, IndexService
from acervo.services.page_service import PageService
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService

PDFS = Path(__file__).parent.parent / "fixtures" / "pdfs"
MakeTree = Callable[..., Awaitable[Any]]


@dataclass
class Env:
    uow: UnitOfWork
    files: FileService
    pages: PageService
    tree: TreeService
    index: IndexService


@pytest.fixture
async def env(uow: UnitOfWork, storage: Settings, session: AsyncSession) -> AsyncIterator[Env]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        bucket = Storage(storage)
        yield Env(
            uow,
            FileService(uow, bucket),
            PageService(uow),
            TreeService(uow),
            IndexService(uow, bucket, storage.retrieval_limits),
        )


async def _build_pending(env: Env) -> None:
    for node_id, key in await env.uow.indexes.pending():
        await env.index.build(node_id, key)


async def test_upload_builds_and_a_replace_keeps_the_old_index_until_the_new_one_is_ready(
    env: Env, make_tree: MakeTree
) -> None:
    tree = await make_tree({})
    with (PDFS / "simple.pdf").open("rb") as source:
        saved = await env.files.save(tree.kb.id, None, "CG 2026.pdf", source)
    assert await env.uow.indexes.states([saved.id]) == {saved.id: "building"}

    await _build_pending(env)
    first = await env.uow.indexes.get(saved.id)
    assert first is not None and first.parsed is not None
    assert (first.status, first.version_key) == ("ready", saved.file.sha256)

    with (PDFS / "protected.pdf").open("rb") as source:
        replaced = await env.files.replace(saved.id, source)
    during = await env.uow.indexes.get(saved.id)
    assert during is not None
    assert (during.status, during.version_key, during.parsed) == ("building", saved.file.sha256, first.parsed)

    await _build_pending(env)
    after = await env.uow.indexes.get(saved.id)
    assert after is not None and (after.status, after.version_key) == ("ready", replaced.file.sha256)


async def test_a_failing_build_is_failed_with_a_message_and_a_retry_rebuilds(
    env: Env, make_tree: MakeTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = await make_tree({})
    with (PDFS / "simple.pdf").open("rb") as source:
        saved = await env.files.save(tree.kb.id, None, "CG 2026.pdf", source)

    def broken(path: Path, limits: Any) -> Any:
        raise RuntimeError("PyMuPDF caiu")

    with monkeypatch.context() as patched:
        patched.setattr(index_service, "index_pdf", broken)
        await _build_pending(env)
    failed = await env.uow.indexes.get(saved.id)
    assert failed is not None and (failed.status, failed.error) == ("failed", FAILED)
    assert await env.uow.indexes.pending() == []

    retried = await env.tree.reindex(saved.id)
    assert retried.index_state == "building"
    await _build_pending(env)
    assert await env.uow.indexes.states([saved.id]) == {saved.id: "ready"}


async def test_cutting_a_page_version_reindexes_and_typing_does_not(env: Env, make_tree: MakeTree) -> None:
    tree = await make_tree({})
    page = await env.tree.create(tree.kb.id, NodeAdd(kind="page", title="Prazos"))
    assert await env.uow.indexes.states([page.id]) == {page.id: "none"}

    await env.pages.put_text(page.id, PageTextPut(markdown="# Prazos\n\nCinco dias.\n", revision=0), 300)
    assert await env.uow.indexes.pending() == []

    await env.pages.cut(page.id)
    newest = await env.uow.page_versions.current(page.id)
    assert await env.uow.indexes.pending() == [(page.id, str(newest.id))]
    await _build_pending(env)
    index = await env.uow.indexes.get(page.id)
    assert index is not None and index.parsed is not None
    assert (index.status, index.version_key) == ("ready", str(newest.id))
    assert "Cinco dias." in " ".join(passage.text for passage in index.parsed.passages)
