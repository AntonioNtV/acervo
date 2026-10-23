from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from acervo.api.deps import get_conversation_service, require_api_key
from acervo.schemas.common import ErrorResponse
from acervo.schemas.conversation import (
    ConversationRead,
    ConversationStart,
    MessageContext,
    MessagePosted,
    MessageRead,
    UiMessage,
)
from acervo.services.conversation_service import ConversationService, Upload

ERROR: dict[str, Any] = {"model": ErrorResponse}
# How the AI SDK knows a response is its UI message stream.
UI_STREAM_HEADERS = {"x-vercel-ai-ui-message-stream": "v1", "cache-control": "no-cache"}

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


@router.delete("/conversations/{conversation_id}", response_model=ConversationRead, responses={409: ERROR})
async def delete_conversation(conversation_id: UUID, service: Service) -> ConversationRead:
    """Leaves the list and its messages are no longer served; what it proposed stays, pending or in the history. A
    conversation still working: 409."""
    return await service.delete(conversation_id)


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
    """Stores the message and a working reply; the reply streams from `/v1/messages/{reply_id}/stream`."""
    uploads = [Upload(name=file.filename, mime=file.content_type, source=file.file) for file in files or []]
    context = MessageContext(page_id=page_id, selection=selection) if page_id or selection else None
    return await service.post(conversation_id, text, uploads, context)


@router.post("/messages/{message_id}/retry", status_code=201, response_model=MessageRead, responses={409: ERROR})
async def retry_message(message_id: UUID, service: Service) -> MessageRead:
    """A new reply that runs a finished reply's message again ("Tentar de novo"); what the old one left waiting is
    dropped."""
    return await service.retry(message_id)


@router.get("/conversations/{conversation_id}/ui-messages", response_model=list[UiMessage])
async def list_ui_messages(conversation_id: UUID, service: Service) -> list[UiMessage]:
    """The conversation as the AI SDK's UI messages (v6): text, proposals as they stand now, citations as sources."""
    return await service.ui_messages(conversation_id)


@router.get(
    "/messages/{reply_id}/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_reply(reply_id: UUID, service: Service) -> StreamingResponse:
    """A reply as the AI SDK's UI message stream (v6), a `data:` line per chunk and `data: [DONE]` last: what it
    streamed so far, then live until it ends; a reply already finished replays and ends."""
    chunks = await service.stream(reply_id)

    async def lines() -> AsyncIterator[str]:
        async for chunk in chunks:
            yield f"data: {chunk}\n\n"

    return StreamingResponse(lines(), media_type="text/event-stream", headers=UI_STREAM_HEADERS)
