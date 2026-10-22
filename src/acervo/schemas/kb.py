from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KbCreate(BaseModel):
    """A knowledge base to create."""

    name: str = Field(min_length=1, description="Name of the base.")
    description: str = Field(default="", description="What the base holds.")


class KbUpdate(BaseModel):
    """Fields to change on a base; omitted fields keep their value."""

    name: str | None = Field(default=None, min_length=1, description="New name.")
    description: str | None = Field(default=None, description="New description.")
    deleted_at: datetime | None = Field(default=None, description="When the base went to the trash; null restores it.")


class KbRead(BaseModel):
    """A saved knowledge base."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Base ID.")
    name: str = Field(description="Name of the base.")
    description: str = Field(description="What the base holds.")
    deleted_at: datetime | None = Field(description="When the base went to the trash; null while it is live.")
    created_at: datetime = Field(description="When the base was created.")
    updated_at: datetime = Field(description="When the base last changed.")
