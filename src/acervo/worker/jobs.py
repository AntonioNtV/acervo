"""The worker's jobs: each opens its own unit of work on what `settings.startup` put in arq's context."""

from typing import Any
from uuid import UUID

from acervo.repositories.uow import UnitOfWork
from acervo.services.chat_service import ChatService
from acervo.services.filing_service import FilingService


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


async def refresh_descriptions(ctx: dict[str, Any], node_ids: list[str]) -> None:
    async with UnitOfWork(ctx["session_factory"]) as uow:
        filing = FilingService(uow, ctx["storage"], ctx["decider"], ctx["writer"], ctx["settings"].thresholds)
        await filing.refresh_descriptions([UUID(node_id) for node_id in node_ids])
