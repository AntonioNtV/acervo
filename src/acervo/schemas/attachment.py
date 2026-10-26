from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Attachment(BaseModel):
    """A file put in a page, which its Markdown reaches as `arquivos/<name>`."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="Unique in the page; the uploaded file's name made safe, with -2, -3… on a clash.")
    mime: str = Field(description="The media type; application/octet-stream when unknown.")
    size: int = Field(description="In bytes.")


class AttachmentCreate(Attachment):
    """An attachment of a page, to store."""

    page_id: UUID = Field(description="Page the file was put in.")
    sha256: str = Field(description="The content's hash, which is also its key in the bucket.")


class AttachmentRead(AttachmentCreate):
    """A stored attachment of a page."""

    id: UUID = Field(description="Attachment ID.")
    created_at: datetime = Field(description="When it was uploaded.")
