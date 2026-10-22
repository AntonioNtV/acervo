import hashlib
import os
import tracemalloc

from acervo.pdfs.storage import PART_SIZE, Storage

MB = 1024 * 1024


async def test_round_trip_keeps_the_bytes(storage, tmp_path) -> None:
    path = tmp_path / "big.bin"
    sent = hashlib.sha256()
    with path.open("wb") as target:
        for _ in range(50):
            chunk = os.urandom(MB)
            sent.update(chunk)
            target.write(chunk)
    bucket = Storage(storage)
    # Loads the client's service model first, which is held once whatever the size of the file.
    await bucket.delete("kb/round-trip/big")

    tracemalloc.start()
    await bucket.put("kb/round-trip/big", path)
    received = hashlib.sha256()
    async for chunk in bucket.stream("kb/round-trip/big"):
        received.update(chunk)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert received.hexdigest() == sent.hexdigest()
    assert peak < 3 * PART_SIZE


async def test_range_read(storage, tmp_path) -> None:
    path = tmp_path / "small.bin"
    path.write_bytes(b"0123456789")
    bucket = Storage(storage)
    await bucket.put("kb/range/small", path)

    assert await bucket.get_range("kb/range/small", 2, 5) == b"2345"


async def test_same_content_is_stored_once(storage, tmp_path) -> None:
    path = tmp_path / "once.bin"
    path.write_bytes(b"same content")
    bucket = Storage(storage)
    await bucket.put("kb/once/key", path)

    # The key exists, so the missing file is never opened.
    await bucket.put("kb/once/key", tmp_path / "missing.bin")

    assert await bucket.get_range("kb/once/key", 0, 3) == b"same"
