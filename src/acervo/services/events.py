"""The ports that carry a message's work out of the request: the job queue and the live stream of a conversation."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any, Protocol
from uuid import UUID

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from pydantic import TypeAdapter
from redis.asyncio import Redis

from acervo.schemas.events import ChatEvent

_EVENT: TypeAdapter[ChatEvent] = TypeAdapter(ChatEvent)


class JobQueue(Protocol):
    async def enqueue(self, job: str, **kwargs: Any) -> None: ...


class EventBus(Protocol):
    async def publish(self, conversation_id: UUID, event: ChatEvent) -> None: ...

    def subscribe(self, conversation_id: UUID) -> AsyncIterator[ChatEvent]: ...


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
    """One Redis channel per conversation; the API streams it, the worker publishes to it."""

    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url)

    async def publish(self, conversation_id: UUID, event: ChatEvent) -> None:
        await self._redis.publish(_channel(conversation_id), event.model_dump_json())

    async def subscribe(self, conversation_id: UUID) -> AsyncIterator[ChatEvent]:
        async with self._redis.pubsub() as pubsub:
            await pubsub.subscribe(_channel(conversation_id))
            async for item in pubsub.listen():
                if item["type"] == "message":
                    yield _EVENT.validate_json(item["data"])

    async def close(self) -> None:
        await self._redis.aclose()


def _channel(conversation_id: UUID) -> str:
    return f"acervo:conversation:{conversation_id}"


class RecordingJobQueue:
    """The tests' queue: keeps what was enqueued, runs nothing."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict[str, Any]]] = []

    async def enqueue(self, job: str, **kwargs: Any) -> None:
        self.jobs.append((job, kwargs))


class InMemoryEventBus:
    """The tests' bus, in one process; `close` ends a conversation's streams so a reader can finish."""

    def __init__(self) -> None:
        self._queues: defaultdict[UUID, list[asyncio.Queue[ChatEvent | None]]] = defaultdict(list)

    def subscribers(self, conversation_id: UUID) -> int:
        return len(self._queues[conversation_id])

    async def publish(self, conversation_id: UUID, event: ChatEvent) -> None:
        for queue in self._queues[conversation_id]:
            queue.put_nowait(event)

    async def close(self, conversation_id: UUID) -> None:
        for queue in self._queues[conversation_id]:
            queue.put_nowait(None)

    async def subscribe(self, conversation_id: UUID) -> AsyncIterator[ChatEvent]:
        queue: asyncio.Queue[ChatEvent | None] = asyncio.Queue()
        self._queues[conversation_id].append(queue)
        try:
            while (event := await queue.get()) is not None:
                yield event
        finally:
            self._queues[conversation_id].remove(queue)
