from collections.abc import AsyncIterable, AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.sse import EventSourceResponse

from acervo.api.deps import get_conversation_service, require_api_key
from acervo.schemas.common import ErrorResponse
from acervo.schemas.conversation import (
    ConversationRead,
    ConversationStart,
    MessageContext,
    MessagePosted,
    MessageRead,
    Reroute,
)
from acervo.schemas.events import ChatEvent
from acervo.services.conversation_service import ConversationService, Upload

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1",
    tags=["conversations"],
    dependencies=[Depends(require_api_key)],
    responses={401: ERROR, 404: ERROR, 422: ERROR},
)

Service = Annotated[ConversationService, Depends(get_conversation_service)]


@router.get("/kbs/{kb_id}/conversations", response_model=list[ConversationRead])
async def list_conversations(kb_id: UUID, service: Service, agent_id: UUID | None = None) -> list[ConversationRead]:
    """The conversations with an agent of the base, the built-in chat when omitted; the most recent first."""
    return await service.list(kb_id, agent_id)


@router.post("/kbs/{kb_id}/conversations", status_code=201, response_model=ConversationRead)
async def start_conversation(kb_id: UUID, body: ConversationStart, service: Service) -> ConversationRead:
    return await service.create(kb_id, body)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(conversation_id: UUID, service: Service) -> list[MessageRead]:
    """The conversation's messages in the order they were sent."""
    return await service.messages(conversation_id)


@router.post("/conversations/{conversation_id}/messages", status_code=201, response_model=MessagePosted)
async def post_message(
    conversation_id: UUID,
    service: Service,
    text: Annotated[str, Form(description="What the person wrote.")] = "",
    files: Annotated[list[UploadFile] | None, File(description="Files sent with it; staged, not in the tree.")] = None,
    page_id: Annotated[UUID | None, Form(description="The page open in the app, kept as context.")] = None,
    selection: Annotated[str | None, Form(description="The text selected on that page.")] = None,
) -> MessagePosted:
    """Stores the message and a working reply; the reply's steps and result arrive on the events stream."""
    uploads = [Upload(name=file.filename, mime=file.content_type, source=file.file) for file in files or []]
    context = MessageContext(page_id=page_id, selection=selection) if page_id or selection else None
    return await service.post(conversation_id, text, uploads, context)


@router.post("/messages/{message_id}/reroute", status_code=201, response_model=MessageRead, responses={409: ERROR})
async def reroute_message(message_id: UUID, body: Reroute, service: Service) -> MessageRead:
    """A new reply that redoes a finished reply's message understood as `route`."""
    return await service.reroute(message_id, body.route)


async def _events(conversation_id: UUID, service: Service) -> AsyncIterator[ChatEvent]:
    # A dependency, so an unknown conversation is a 404 before the stream starts.
    return await service.events(conversation_id)


@router.get("/conversations/{conversation_id}/events", response_class=EventSourceResponse)
async def conversation_events(
    events: Annotated[AsyncIterator[ChatEvent], Depends(_events)],
) -> AsyncIterable[ChatEvent]:
    """The conversation's live events, each a JSON `data:` line, for as long as the connection stays open."""
    async for event in events:
        yield event
