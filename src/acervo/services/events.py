"""The ports that carry a message's work out of the request: the job queue and the live stream of a reply."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any, Protocol
from uuid import UUID

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from redis.asyncio import Redis

# A reply's stream ends with this chunk, as the AI SDK's UI message stream does.
DONE = "[DONE]"
# How long a reply's chunks are kept to replay it on a reconnect; after that the stored thread serves it.
KEEP_SECONDS = 3600


class JobQueue(Protocol):
    async def enqueue(self, job: str, **kwargs: Any) -> None: ...


class EventBus(Protocol):
    """A reply's chunks of the AI SDK UI message stream (JSON, `[DONE]` last), live and kept for a while."""

    async def publish(self, reply_id: UUID, chunk: str) -> None: ...

    def follow(self, reply_id: UUID, working: bool) -> AsyncIterator[str]:
        """What was kept of the reply, then, while it is `working` (read before calling), what comes live until
        `[DONE]`."""
        ...


class ArqJobQueue:
    """Jobs on arq's Redis queue, run by the worker."""

    def __init__(self, redis_url: str) -> None:
        self._settings = RedisSettings.from_dsn(redis_url)
        self._pool: ArqRedis | None = None

    async def enqueue(self, job: str, **kwargs: Any) -> None:
        if self._pool is None:
            self._pool = await create_pool(self._settings)
        await self._pool.enqueue_job(job, **kwargs)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None


class RedisEventBus:
    """Each chunk is pushed to a list per reply and published on its channel with its index, so a reader that
    subscribed before reading the list skips what it already replayed."""

    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url)

    async def publish(self, reply_id: UUID, chunk: str) -> None:
        key = _key(reply_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.rpush(key, chunk)
            pipe.expire(key, KEEP_SECONDS)
            length, _ = await pipe.execute()
        await self._redis.publish(_channel(reply_id), f"{length - 1}:{chunk}")

    async def follow(self, reply_id: UUID, working: bool) -> AsyncIterator[str]:
        async with self._redis.pubsub() as pubsub:
            await pubsub.subscribe(_channel(reply_id))
            items = pubsub.listen()
            # The list is read only once the subscription is confirmed, or a chunk could fall between the two.
            async for item in items:
                if item["type"] == "subscribe":
                    break
            kept = [chunk.decode() for chunk in await self._redis.lrange(_key(reply_id), 0, -1)]
            for chunk in kept:
                yield chunk
            if DONE in kept or not working:
                return
            async for item in items:
                if item["type"] != "message":
                    continue
                index, _, chunk = item["data"].decode().partition(":")
                if int(index) < len(kept):
                    continue
                yield chunk
                if chunk == DONE:
                    return

    async def close(self) -> None:
        await self._redis.aclose()


def _channel(reply_id: UUID) -> str:
    return f"acervo:reply:{reply_id}"


def _key(reply_id: UUID) -> str:
    return f"acervo:reply:{reply_id}:chunks"


class RecordingJobQueue:
    """The tests' queue: keeps what was enqueued, runs nothing."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict[str, Any]]] = []

    async def enqueue(self, job: str, **kwargs: Any) -> None:
        self.jobs.append((job, kwargs))


class InMemoryEventBus:
    """The tests' bus, in one process; `kept` holds every reply's chunks."""

    def __init__(self) -> None:
        self.kept: defaultdict[UUID, list[str]] = defaultdict(list)
        self._queues: defaultdict[UUID, list[asyncio.Queue[str]]] = defaultdict(list)

    def followers(self, reply_id: UUID) -> int:
        return len(self._queues[reply_id])

    async def publish(self, reply_id: UUID, chunk: str) -> None:
        self.kept[reply_id].append(chunk)
        for queue in self._queues[reply_id]:
            queue.put_nowait(chunk)

    async def follow(self, reply_id: UUID, working: bool) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._queues[reply_id].append(queue)
        try:
            kept = list(self.kept[reply_id])
            for chunk in kept:
                yield chunk
            if DONE in kept or not working:
                return
            while (chunk := await queue.get()) != DONE:
                yield chunk
            yield chunk
        finally:
            self._queues[reply_id].remove(queue)
