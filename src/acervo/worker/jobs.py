"""The worker's jobs: each opens its own unit of work on what `settings.startup` put in arq's context."""

from typing import Any
from uuid import UUID

from acervo.repositories.uow import UnitOfWork
from acervo.services.chat_service import ChatService
from acervo.services.index_service import INDEX_NODE, IndexService


async def handle_message(ctx: dict[str, Any], message_id: str, reply_id: str) -> None:
    settings = ctx["settings"]
    async with UnitOfWork(ctx["session_factory"]) as uow:
        chat = ChatService(
            uow,
            ctx["storage"],
            ctx["decider"],
            ctx["writer"],
            settings.thresholds,
            ctx["events"],
            ctx["jobs"],
            ctx["chat"],
            settings.chat_history,
        )
        await chat.handle(UUID(message_id), UUID(reply_id))


async def index_pending(ctx: dict[str, Any]) -> None:
    """Enqueues each index build asked for; one job per node and version, however many sweeps see it."""
    async with UnitOfWork(ctx["session_factory"]) as uow:
        pending = await uow.indexes.pending()
    for node_id, key in pending:
        await ctx["jobs"].enqueue(INDEX_NODE, node_id=str(node_id), key=key, _job_id=f"index:{node_id}:{key}")


async def index_node(ctx: dict[str, Any], node_id: str, key: str) -> None:
    async with UnitOfWork(ctx["session_factory"]) as uow:
        await IndexService(uow, ctx["storage"], ctx["settings"].retrieval_limits).build(UUID(node_id), key)
