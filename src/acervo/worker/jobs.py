"""The worker's jobs: each opens its own unit of work on what `settings.startup` put in arq's context."""

from typing import Any
from uuid import UUID

from acervo.domain.cards import Route
from acervo.repositories.uow import UnitOfWork
from acervo.services.chat_service import ChatService


def _chat(ctx: dict[str, Any], uow: UnitOfWork) -> ChatService:
    return ChatService(
        uow,
        ctx["storage"],
        ctx["decider"],
        ctx["writer"],
        ctx["settings"].thresholds,
        ctx["events"],
        ctx["jobs"],
    )


async def handle_message(ctx: dict[str, Any], message_id: str, reply_id: str, route: Route | None = None) -> None:
    async with UnitOfWork(ctx["session_factory"]) as uow:
        await _chat(ctx, uow).handle(UUID(message_id), UUID(reply_id), route)


async def refresh_descriptions(ctx: dict[str, Any], node_ids: list[str]) -> None:
    async with UnitOfWork(ctx["session_factory"]) as uow:
        await _chat(ctx, uow).refresh_descriptions([UUID(node_id) for node_id in node_ids])
