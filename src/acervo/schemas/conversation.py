from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acervo.domain.cards import Route
from acervo.schemas.proposal import StagedFile

MessageRole = Literal["person", "acervo"]
MessageStatus = Literal["done", "working", "failed"]


class ConversationCreate(BaseModel):
    """A conversation to start in a base."""

    kb_id: UUID = Field(description="Base it belongs to.")
    agent_id: UUID = Field(description="The agent it talks to: the built-in chat or an external agent.")
    title: str = Field(default="", description="Shown in the list of past conversations.")


class ConversationUpdate(BaseModel):
    """Fields to change on a conversation; omitted fields keep their value."""

    title: str | None = Field(default=None, description="New title.")
    updated_at: datetime | None = Field(default=None, description="When it was last used, for the list's order.")


class ConversationRead(ConversationCreate):
    """A conversation of a base, kept to reopen."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Conversation ID.")
    created_at: datetime = Field(description="When it started.")
    updated_at: datetime = Field(description="When it last changed.")


class Attachment(StagedFile):
    """A file attached to a message, waiting in storage; never in the base's tree until a proposal is accepted."""

    mime: str = Field(description="Media type as received.")


class MessageContext(BaseModel):
    """What the person kept as context when sending."""

    page_id: UUID | None = Field(default=None, description="The page open in the app.")
    selection: str | None = Field(default=None, description="The text selected on that page.")


class MessageCreate(BaseModel):
    """A message of a conversation, to store."""

    conversation_id: UUID = Field(description="Conversation it belongs to.")
    role: MessageRole = Field(description="Who wrote it: the person, or Acervo replying.")
    text: str = Field(default="", description="The message's text.")
    attachments: list[Attachment] = Field(default_factory=list, description="Files sent with it.")
    context: MessageContext | None = Field(default=None, description="The open page and selection, if kept.")
    status: MessageStatus = Field(default="done", description="A reply is working until its job ends.")
    run_id: UUID | None = Field(default=None, description="The run that handles it, linking the decision log.")
    replaces_id: UUID | None = Field(default=None, description="The reply this one redoes another way.")


class MessageUpdate(BaseModel):
    """Fields to change on a reply as its job runs; omitted fields keep their value."""

    text: str | None = Field(default=None, description="The reply's text.")
    status: MessageStatus | None = Field(default=None, description="New status.")
    understood_as: Route | None = Field(default=None, description="How the message was understood.")
    run_id: UUID | None = Field(default=None, description="The run that handles it.")
    error: str | None = Field(default=None, description="Why it failed.")


class MessageRead(MessageCreate):
    """A stored message."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Message ID.")
    understood_as: Route | None = Field(
        description="How the message was understood, shown with a one-click change; null until it is."
    )
    error: str | None = Field(description="Why it failed; null unless status is failed.")
    created_at: datetime = Field(description="When it was sent.")
