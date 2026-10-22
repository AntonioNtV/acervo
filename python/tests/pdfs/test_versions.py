import hashlib
from pathlib import Path

import pytest

from acervo.errors import ConflictError
from acervo.pdfs import files, versions
from acervo.pdfs.storage import Storage

PDFS = Path(__file__).parent.parent / "fixtures" / "pdfs"
SIMPLE = PDFS / "simple.pdf"
PROTECTED = PDFS / "protected.pdf"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _saved(session, storage, make_tree):
    tree = await make_tree({"Bradesco": None})
    with SIMPLE.open("rb") as source:
        return await files.save(session, Storage(storage), tree.kb.id, tree["Bradesco"].id, "CG 2026.pdf", source)


async def _replace(session, storage, node_id, path: Path):
    with path.open("rb") as source:
        return await versions.replace(session, Storage(storage), node_id, source)


async def test_replace_moves_current_to_history(session, storage, make_tree) -> None:
    file = await _saved(session, storage, make_tree)

    await _replace(session, storage, file.node_id, PROTECTED)

    assert (file.sha256, file.protected) == (_sha256(PROTECTED), True)
    [old] = await versions.list_versions(session, file.node_id)
    assert (old.sha256, old.pages, old.protected) == (_sha256(SIMPLE), 3, False)


async def test_replace_with_same_content_is_refused(session, storage, make_tree) -> None:
    file = await _saved(session, storage, make_tree)

    with pytest.raises(ConflictError, match="é o mesmo arquivo"):
        await _replace(session, storage, file.node_id, SIMPLE)

    assert await versions.list_versions(session, file.node_id) == []


async def test_restore_old_version_keeps_every_file(session, storage, make_tree) -> None:
    file = await _saved(session, storage, make_tree)
    await _replace(session, storage, file.node_id, PROTECTED)
    [first] = await versions.list_versions(session, file.node_id)

    await versions.restore(session, file.node_id, first.id)

    assert file.sha256 == _sha256(SIMPLE)
    history = await versions.list_versions(session, file.node_id)
    assert sorted(version.sha256 for version in history) == sorted([_sha256(SIMPLE), _sha256(PROTECTED)])
    for version in [None, *history]:
        row, chunks = await versions.open_bytes(session, Storage(storage), file.node_id, version and version.id)
        assert hashlib.sha256(b"".join([chunk async for chunk in chunks])).hexdigest() == row.sha256
