import asyncio
import hashlib
import io
import os
import tracemalloc
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from acervo.core.errors import Duplicate, SameFile, TitleTaken
from acervo.core.settings import Settings
from acervo.db.base import Base
from acervo.db.models import Agent, File, Kb, Node
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.file import FileContent, FileNodeRead
from acervo.services.file_service import FileService
from acervo.services.storage import PART_SIZE, Storage
from acervo.services.tree_service import TreeService

FIXTURES = Path(__file__).parent.parent / "fixtures"
SIMPLE = FIXTURES / "pdfs" / "simple.pdf"
PROTECTED = FIXTURES / "pdfs" / "protected.pdf"
MB = 1024 * 1024

MakeTree = Callable[..., Awaitable[Any]]


@pytest.fixture
async def files(uow: UnitOfWork, storage: Settings, session: AsyncSession) -> AsyncIterator[FileService]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield FileService(uow, Storage(storage))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _read(files: FileService, content: FileContent, byte_range: tuple[int, int] | None = None) -> bytes:
    return b"".join([chunk async for chunk in files.stream(content, byte_range)])


async def _save(files: FileService, tree: Any, folder: str | None, fixture: Path, filename: str) -> FileNodeRead:
    with fixture.open("rb") as source:
        return await files.save(tree.kb.id, tree[folder].id if folder else None, filename, source)


async def _replace(files: FileService, node_id: uuid.UUID, fixture: Path) -> FileNodeRead:
    with fixture.open("rb") as source:
        return await files.replace(node_id, source)


async def _live_files(session: AsyncSession, kb_id: uuid.UUID) -> int:
    return await session.scalar(select(func.count()).where(Node.kb_id == kb_id, Node.kind == "file")) or 0


async def test_save_pdf_round_trip(files: FileService, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["Emissão de apólice.md"]}})

    saved = await _save(files, tree, "Bradesco/Residencial", SIMPLE, "Condições Gerais 2026.pdf")

    assert (saved.kind, saved.title, saved.parent_id, saved.path, saved.versions) == (
        "file",
        "Condições Gerais 2026.pdf",
        tree["Bradesco/Residencial"].id,
        "Bradesco/Residencial/Condições Gerais 2026.pdf",
        1,
    )
    assert saved.sort > tree["Bradesco/Residencial/Emissão de apólice.md"].sort
    content = SIMPLE.read_bytes()
    assert (saved.file.mime, saved.file.pages, saved.file.protected, saved.file.size) == (
        "application/pdf",
        3,
        False,
        len(content),
    )
    assert saved.file.sha256 == hashlib.sha256(content).hexdigest()
    node, opened = await files.open(saved.id)
    assert (node.id, await _read(files, opened), await _read(files, opened, (2, 5))) == (
        saved.id,
        content,
        content[2:6],
    )


async def test_protected_pdf_is_flagged(files: FileService, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})

    saved = await _save(files, tree, "Bradesco", PROTECTED, "Apólice.pdf")

    assert (saved.file.mime, saved.file.pages, saved.file.protected) == ("application/pdf", 3, True)


async def test_non_pdf_file_has_no_pages(files: FileService, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})

    saved = await _save(files, tree, "Bradesco", FIXTURES / "files" / "photo.png", "Fachada.png")

    assert (saved.file.mime, saved.file.pages, saved.file.protected) == ("image/png", None, False)


async def test_duplicate_in_base_is_refused_with_its_path(
    files: FileService, make_tree: MakeTree, session: AsyncSession
) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": None}, "Porto": None})
    first = await _save(files, tree, "Bradesco/Residencial", SIMPLE, "CG 2026.pdf")

    with pytest.raises(Duplicate) as refused:
        await _save(files, tree, "Porto", SIMPLE, "Outro nome.pdf")

    assert refused.value.message == "já está em Bradesco/Residencial/CG 2026.pdf"
    assert refused.value.details == {
        "node_id": str(first.id),
        "path": "Bradesco/Residencial/CG 2026.pdf",
        "trashed": False,
        "history": False,
    }
    assert await _live_files(session, tree.kb.id) == 1


async def test_duplicate_in_trash_is_refused(files: FileService, make_tree: MakeTree, session: AsyncSession) -> None:
    tree = await make_tree({"Bradesco": None})
    first = await _save(files, tree, "Bradesco", SIMPLE, "CG 2026.pdf")
    (await session.get_one(Node, first.id)).deleted_at = datetime.now(UTC)
    await session.flush()

    with pytest.raises(Duplicate) as refused:
        await _save(files, tree, None, SIMPLE, "CG 2026.pdf")

    assert refused.value.message == "está na Lixeira: Bradesco/CG 2026.pdf"
    assert refused.value.details["trashed"] is True
    assert await _live_files(session, tree.kb.id) == 1


async def test_duplicate_of_an_old_version_is_refused_with_its_path(
    files: FileService, make_tree: MakeTree, session: AsyncSession
) -> None:
    tree = await make_tree({"Bradesco": None, "Porto": None})
    first = await _save(files, tree, "Bradesco", SIMPLE, "CG 2026.pdf")
    await _replace(files, first.id, PROTECTED)

    with pytest.raises(Duplicate) as refused:
        await _save(files, tree, "Porto", SIMPLE, "Outro nome.pdf")

    assert refused.value.message == "já está no histórico de Bradesco/CG 2026.pdf"
    assert (refused.value.details["node_id"], refused.value.details["history"]) == (str(first.id), True)
    assert await _live_files(session, tree.kb.id) == 1


async def test_sibling_clash_is_refused_and_nothing_stored(
    files: FileService, make_tree: MakeTree, storage: Settings
) -> None:
    tree = await make_tree({"Bradesco": ["CG 2026.pdf"]})

    with pytest.raises(TitleTaken, match="já existe"):
        await _save(files, tree, "Bradesco", SIMPLE, "cg 2026.PDF")

    with pytest.raises(Exception, match="NoSuchKey"):
        await anext(Storage(storage).stream(f"kb/{tree.kb.id}/{_sha256(SIMPLE)}"))


async def test_no_text_is_stored(files: FileService, make_tree: MakeTree, session: AsyncSession) -> None:
    tree = await make_tree({"Bradesco": None})

    await _save(files, tree, "Bradesco", SIMPLE, "Condições Gerais 2026.pdf")

    for table in Base.metadata.sorted_tables:
        rows = await session.scalar(
            text(f"select count(*) from {table.fullname} as row where row::text ilike '%página%'")
        )
        assert rows == 0, table.fullname


async def test_replace_moves_current_to_history(files: FileService, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})
    saved = await _save(files, tree, "Bradesco", SIMPLE, "CG 2026.pdf")

    replaced = await _replace(files, saved.id, PROTECTED)

    assert (replaced.file.sha256, replaced.file.protected, replaced.versions) == (_sha256(PROTECTED), True, 2)
    [old] = await files.versions(saved.id)
    assert (old.sha256, old.pages, old.protected) == (_sha256(SIMPLE), 3, False)


async def test_replace_with_same_content_is_refused(files: FileService, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})
    saved = await _save(files, tree, "Bradesco", SIMPLE, "CG 2026.pdf")

    with pytest.raises(SameFile, match="é o mesmo arquivo"):
        await _replace(files, saved.id, SIMPLE)

    assert await files.versions(saved.id) == []


async def test_replace_with_another_files_content_is_refused(files: FileService, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})
    saved = await _save(files, tree, "Bradesco", SIMPLE, "CG 2026.pdf")
    await _save(files, tree, "Bradesco", PROTECTED, "Apólice.pdf")

    with pytest.raises(Duplicate, match="^já está em Bradesco/Apólice.pdf$"):
        await _replace(files, saved.id, PROTECTED)

    _, current = await files.open(saved.id)
    assert (current.sha256, await files.versions(saved.id)) == (_sha256(SIMPLE), [])


async def test_restore_old_version_keeps_every_file(files: FileService, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})
    saved = await _save(files, tree, "Bradesco", SIMPLE, "CG 2026.pdf")
    await _replace(files, saved.id, PROTECTED)
    [first] = await files.versions(saved.id)

    restored = await files.restore(saved.id, first.id)

    assert (restored.file.sha256, restored.versions) == (_sha256(SIMPLE), 3)
    history = await files.versions(saved.id)
    assert sorted(version.sha256 for version in history) == sorted([_sha256(SIMPLE), _sha256(PROTECTED)])
    for version in [None, *history]:
        _, content = await files.open(saved.id, version and version.id)
        assert hashlib.sha256(await _read(files, content)).hexdigest() == content.sha256


@dataclass
class Committed:
    sessions: async_sessionmaker[AsyncSession]
    kb_id: uuid.UUID


@pytest.fixture
async def committed(test_settings: Settings) -> AsyncIterator[Committed]:
    """A base written by sessions on connections of their own that commit, as parallel requests do; removed after."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        kb = Kb(id=uuid.uuid4(), name="Uploads em paralelo")
        session.add(kb)
        await session.commit()
    yield Committed(sessions, kb.id)
    async with sessions() as session:
        of_base = select(Node.id).where(Node.kb_id == kb.id)
        await session.execute(delete(File).where(File.node_id.in_(of_base)))
        await session.execute(delete(Node).where(Node.kb_id == kb.id))
        await session.execute(delete(Agent).where(Agent.kb_id == kb.id))
        await session.execute(delete(Kb).where(Kb.id == kb.id))
        await session.commit()
    await engine.dispose()


async def _save_committed(committed: Committed, storage: Settings, filename: str, content: bytes) -> FileNodeRead:
    async with UnitOfWork(committed.sessions) as uow:
        return await FileService(uow, Storage(storage)).save(committed.kb_id, None, filename, io.BytesIO(content))


async def test_parallel_uploads_of_same_content_store_one(committed: Committed, storage: Settings) -> None:
    results = await asyncio.gather(
        _save_committed(committed, storage, "CG 2026.pdf", SIMPLE.read_bytes()),
        _save_committed(committed, storage, "Outro nome.pdf", SIMPLE.read_bytes()),
        return_exceptions=True,
    )

    assert sorted(type(result).__name__ for result in results) == ["Duplicate", "FileNodeRead"]
    async with committed.sessions() as session:
        assert await session.scalar(select(func.count()).where(Node.kb_id == committed.kb_id)) == 1


async def test_parallel_uploads_get_distinct_sort_keys(committed: Committed, storage: Settings) -> None:
    saved = await asyncio.gather(
        *(_save_committed(committed, storage, f"Anexo {n}.txt", f"anexo {n}".encode()) for n in range(4))
    )

    assert len({node.sort for node in saved}) == 4


async def test_storage_round_trip_holds_one_part_in_memory(storage: Settings, tmp_path: Path) -> None:
    path = tmp_path / "big.bin"
    sent = hashlib.sha256()
    with path.open("wb") as target:
        for _ in range(50):
            chunk = os.urandom(MB)
            sent.update(chunk)
            target.write(chunk)
    bucket = Storage(storage)
    # Loads the client's service model first, which is held once whatever the size of the file.
    await bucket.put("kb/round-trip/small", io.BytesIO(b"small"), 5)

    tracemalloc.start()
    with path.open("rb") as source:
        await bucket.put("kb/round-trip/big", source, path.stat().st_size)
    received = hashlib.sha256()
    async for chunk in bucket.stream("kb/round-trip/big"):
        received.update(chunk)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert received.hexdigest() == sent.hexdigest()
    assert peak < 3 * PART_SIZE


async def test_storage_keeps_the_first_content_of_a_key(storage: Settings) -> None:
    bucket = Storage(storage)
    await bucket.put("kb/once/key", io.BytesIO(b"same content"), 12)

    # The key exists, so the other source is never read.
    await bucket.put("kb/once/key", io.BytesIO(b"other"), 5)

    assert b"".join([chunk async for chunk in bucket.stream("kb/once/key")]) == b"same content"


async def test_trash_and_restore_take_the_base_lock(
    files: FileService, uow: UnitOfWork, make_tree: MakeTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = await make_tree({"Bradesco": None})
    saved = await _save(files, tree, "Bradesco", SIMPLE, "CG 2026.pdf")
    await _replace(files, saved.id, PROTECTED)
    [first] = await files.versions(saved.id)
    locked: list[uuid.UUID] = []
    lock = uow.kbs.lock

    async def spy(kb_id: uuid.UUID) -> None:
        locked.append(kb_id)
        await lock(kb_id)

    monkeypatch.setattr(uow.kbs, "lock", spy)

    await files.restore(saved.id, first.id)
    await TreeService(uow).trash(saved.id)

    assert locked == [tree.kb.id, tree.kb.id]
