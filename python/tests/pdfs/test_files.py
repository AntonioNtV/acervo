import asyncio
import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from acervo.errors import ConflictError
from acervo.pdfs import files, versions
from acervo.pdfs.storage import Storage
from acervo.store.models import Base, File, Kb, Node

FIXTURES = Path(__file__).parent.parent / "fixtures"
SIMPLE = FIXTURES / "pdfs" / "simple.pdf"
PROTECTED = FIXTURES / "pdfs" / "protected.pdf"


async def _save(session, storage, tree, folder, fixture: Path, filename: str):
    parent = tree[folder].id if folder else None
    with fixture.open("rb") as source:
        return await files.save(session, Storage(storage), tree.kb.id, parent, filename, source)


@dataclass
class Committed:
    sessions: async_sessionmaker[AsyncSession]
    kb_id: uuid.UUID


@pytest.fixture
async def committed(test_settings):
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
        await session.execute(delete(Kb).where(Kb.id == kb.id))
        await session.commit()
    await engine.dispose()


async def _save_committed(committed: Committed, storage, filename: str, content: bytes):
    async with committed.sessions() as session:
        file = await files.save(session, Storage(storage), committed.kb_id, None, filename, io.BytesIO(content))
        await session.commit()
        return file


async def _live_files(session, tree) -> int:
    return await session.scalar(select(func.count()).where(Node.kb_id == tree.kb.id, Node.kind == "file"))


async def test_save_pdf_records_pages_and_mime(session, storage, make_tree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["Emissão de apólice.md"]}})

    file = await _save(session, storage, tree, "Bradesco/Residencial", SIMPLE, "Condições Gerais 2026.pdf")

    node = await session.get(Node, file.node_id)
    assert (node.kind, node.title, node.parent_id) == (
        "file",
        "Condições Gerais 2026.pdf",
        tree["Bradesco/Residencial"].id,
    )
    assert node.sort > tree["Bradesco/Residencial/Emissão de apólice.md"].sort
    content = SIMPLE.read_bytes()
    assert (file.mime, file.pages, file.protected, file.size) == ("application/pdf", 3, False, len(content))
    assert file.sha256 == hashlib.sha256(content).hexdigest()
    stored = b"".join([chunk async for chunk in Storage(storage).stream(file.storage_key)])
    assert stored == content


async def test_protected_pdf_is_flagged(session, storage, make_tree) -> None:
    tree = await make_tree({"Bradesco": None})

    file = await _save(session, storage, tree, "Bradesco", FIXTURES / "pdfs" / "protected.pdf", "Apólice.pdf")

    assert (file.mime, file.pages, file.protected) == ("application/pdf", 3, True)


async def test_non_pdf_file_has_no_pages(session, storage, make_tree) -> None:
    tree = await make_tree({"Bradesco": None})

    file = await _save(session, storage, tree, "Bradesco", FIXTURES / "files" / "photo.png", "Fachada.png")

    assert (file.mime, file.pages, file.protected) == ("image/png", None, False)


async def test_duplicate_in_base_is_refused_with_its_path(session, storage, make_tree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": None}, "Porto": None})
    first = await _save(session, storage, tree, "Bradesco/Residencial", SIMPLE, "CG 2026.pdf")

    with pytest.raises(ConflictError) as refused:
        await _save(session, storage, tree, "Porto", SIMPLE, "Outro nome.pdf")

    assert refused.value.message == "já está em Bradesco/Residencial/CG 2026.pdf"
    assert refused.value.detail["node_id"] == str(first.node_id)
    assert await _live_files(session, tree) == 1


async def test_duplicate_in_trash_is_refused(session, storage, make_tree) -> None:
    tree = await make_tree({"Bradesco": None})
    first = await _save(session, storage, tree, "Bradesco", SIMPLE, "CG 2026.pdf")
    (await session.get(Node, first.node_id)).deleted_at = datetime.now(UTC)
    await session.flush()

    with pytest.raises(ConflictError) as refused:
        await _save(session, storage, tree, None, SIMPLE, "CG 2026.pdf")

    assert refused.value.message == "está na Lixeira: Bradesco/CG 2026.pdf"
    assert await _live_files(session, tree) == 1


async def test_duplicate_of_an_old_version_is_refused_with_its_path(session, storage, make_tree) -> None:
    tree = await make_tree({"Bradesco": None, "Porto": None})
    first = await _save(session, storage, tree, "Bradesco", SIMPLE, "CG 2026.pdf")
    with PROTECTED.open("rb") as source:
        await versions.replace(session, Storage(storage), first.node_id, source)

    with pytest.raises(ConflictError) as refused:
        await _save(session, storage, tree, "Porto", SIMPLE, "Outro nome.pdf")

    assert refused.value.message == "já está no histórico de Bradesco/CG 2026.pdf"
    assert refused.value.detail["node_id"] == str(first.node_id)
    assert await _live_files(session, tree) == 1


async def test_parallel_uploads_of_same_content_store_one(committed, storage) -> None:
    results = await asyncio.gather(
        _save_committed(committed, storage, "CG 2026.pdf", SIMPLE.read_bytes()),
        _save_committed(committed, storage, "Outro nome.pdf", SIMPLE.read_bytes()),
        return_exceptions=True,
    )

    assert sorted(type(result).__name__ for result in results) == ["ConflictError", "File"]
    async with committed.sessions() as session:
        assert await session.scalar(select(func.count()).where(Node.kb_id == committed.kb_id)) == 1


async def test_parallel_uploads_get_distinct_sort_keys(committed, storage) -> None:
    saved = await asyncio.gather(
        *(_save_committed(committed, storage, f"Anexo {n}.txt", f"anexo {n}".encode()) for n in range(4))
    )

    async with committed.sessions() as session:
        sorts = [(await session.get(Node, file.node_id)).sort for file in saved]
    assert len(set(sorts)) == 4


async def test_sibling_clash_is_refused(session, storage, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["CG 2026.pdf"]})

    with pytest.raises(ConflictError, match="já existe"):
        await _save(session, storage, tree, "Bradesco", SIMPLE, "cg 2026.PDF")

    sha256 = hashlib.sha256(SIMPLE.read_bytes()).hexdigest()
    with pytest.raises(Exception, match="NoSuchKey"):
        await anext(Storage(storage).stream(f"kb/{tree.kb.id}/{sha256}"))


async def test_no_text_is_stored(session, storage, make_tree) -> None:
    tree = await make_tree({"Bradesco": None})

    await _save(session, storage, tree, "Bradesco", SIMPLE, "Condições Gerais 2026.pdf")

    for table in Base.metadata.sorted_tables:
        rows = await session.scalar(
            text(f"select count(*) from {table.fullname} as row where row::text ilike '%página%'")
        )
        assert rows == 0, table.fullname
