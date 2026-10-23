from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acervo.schemas.node import Icon


class KbCreate(BaseModel):
    """A knowledge base to create."""

    name: str = Field(min_length=1, description="Name of the base.")
    description: str = Field(default="", description="What the base holds.")


class KbUpdate(BaseModel):
    """Fields to change on a base; omitted fields keep their value."""

    name: str | None = Field(default=None, min_length=1, description="New name.")
    description: str | None = Field(default=None, description="New description.")
    icon: str | None = Field(default=None, description="An emoji; null removes it.")
    deleted_at: datetime | None = Field(default=None, description="When the base went to the trash; null restores it.")


class KbRead(BaseModel):
    """A saved knowledge base."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Base ID.")
    name: str = Field(description="Name of the base.")
    description: str = Field(description="What the base holds.")
    icon: str | None = Field(description="An emoji shown before the name; null for none.")
    deleted_at: datetime | None = Field(description="When the base went to the trash; null while it is live.")
    created_at: datetime = Field(description="When the base was created.")
    updated_at: datetime = Field(description="When the base last changed.")


class KbEdit(BaseModel):
    """A change to a base; omitted fields keep their value."""

    name: str | None = Field(default=None, min_length=1, description="New name; cannot be blank.")
    description: str | None = Field(default=None, description="New description.")
    icon: Icon | None = Field(default=None, description="An emoji; null removes it.")


class KbSummary(KbRead):
    """A base as the Bases screen lists it."""

    pages: int = Field(description="Live pages in the base.")
    files: int = Field(description="Live files in the base.")
    last_edit: datetime = Field(description="The newest change to the base, its nodes, pages or files.")
