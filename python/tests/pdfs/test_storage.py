import hashlib
import io
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
    with path.open("rb") as source:
        await bucket.put("kb/round-trip/big", source, path.stat().st_size)
    received = hashlib.sha256()
    async for chunk in bucket.stream("kb/round-trip/big"):
        received.update(chunk)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert received.hexdigest() == sent.hexdigest()
    assert peak < 3 * PART_SIZE


async def _read(bucket: Storage, key: str, byte_range: tuple[int, int] | None = None) -> bytes:
    return b"".join([chunk async for chunk in bucket.stream(key, byte_range)])


async def test_range_read(storage) -> None:
    bucket = Storage(storage)
    await bucket.put("kb/range/small", io.BytesIO(b"0123456789"), 10)

    assert await _read(bucket, "kb/range/small", (2, 5)) == b"2345"


async def test_same_content_is_stored_once(storage) -> None:
    bucket = Storage(storage)
    await bucket.put("kb/once/key", io.BytesIO(b"same content"), 12)

    # The key exists, so the other source is never read.
    await bucket.put("kb/once/key", io.BytesIO(b"other"), 5)

    assert await _read(bucket, "kb/once/key") == b"same content"
