from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AgentMode = Literal["ask", "auto"]


class AgentCreate(BaseModel):
    """An agent to connect to a base."""

    name: str = Field(min_length=1, description="Shown on every proposal it makes.")
    mode: AgentMode = Field(default="ask", description="ask: its proposals wait; auto: applied when created.")


class AgentUpdate(BaseModel):
    """Fields to change on an agent; omitted fields keep their value."""

    name: str | None = Field(default=None, min_length=1, description="New name.")
    mode: AgentMode | None = Field(default=None, description="New approval mode.")
    last_used_at: datetime | None = Field(default=None, description="When its token was last accepted.")
    revoked_at: datetime | None = Field(default=None, description="When its token stopped working.")


class AgentRead(BaseModel):
    """A connection that files into one base: the built-in chat, or an external agent over MCP."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Agent ID.")
    kb_id: UUID = Field(description="The only base it sees.")
    name: str = Field(description="Shown on every proposal it makes.")
    mode: AgentMode = Field(
        description="ask: its proposals wait for the person; auto: applied when created, except a conflict or an "
        "input with no clear place."
    )
    built_in: bool = Field(description="The base's own chat, which has no token and cannot be revoked.")
    token_hint: str | None = Field(description="The token's last 4 characters; null for the built-in chat.")
    last_used_at: datetime | None = Field(description="When its token was last accepted; null if never.")
    revoked_at: datetime | None = Field(description="When its token stopped working; null while it works.")
    created_at: datetime = Field(description="When it was connected.")
