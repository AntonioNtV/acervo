from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acervo.schemas.node import NodeRead


class FileContent(BaseModel):
    """What is known about one stored content of a file. Metadata only: never its text (rule 3 of CLAUDE.md)."""

    model_config = ConfigDict(from_attributes=True)

    storage_key: str = Field(description="Key of the bytes in the bucket.")
    sha256: str = Field(description="The content's hash.")
    size: int = Field(description="In bytes.")
    mime: str = Field(description="The media type; application/octet-stream when unknown.")
    pages: int | None = Field(description="A PDF's page count; null for other files or a broken PDF.")
    protected: bool = Field(description="A PDF that needs a password to open.")

    def only_content(self) -> "FileContent":
        """The content's own fields, every one set, so an update or a history row takes all of them."""
        return FileContent(**{name: getattr(self, name) for name in FileContent.model_fields})


class FileCreate(FileContent):
    """The current content of a file node, to store."""

    node_id: UUID = Field(description="File node the content belongs to.")


class FileRead(FileContent):
    """The current content of a file node."""

    id: UUID = Field(description="File ID.")
    node_id: UUID = Field(description="File node the content belongs to.")
    created_at: datetime = Field(description="When the file was first stored.")
    updated_at: datetime = Field(description="When the current content was set.")


class FileVersionCreate(FileContent):
    """A content a file node had, to keep in its history."""

    node_id: UUID = Field(description="File node the content belonged to.")
    replaced_at: datetime = Field(description="When a newer content took its place.")


class FileVersionRead(FileContent):
    """A content a file node had before its current one."""

    id: UUID = Field(description="Version ID.")
    node_id: UUID = Field(description="File node the content belonged to.")
    replaced_at: datetime = Field(description="When a newer content took its place.")


class FileResponse(BaseModel):
    """What the API shows of a stored content of a file. Metadata only, never its text."""

    model_config = ConfigDict(from_attributes=True)

    size: int = Field(description="In bytes.")
    mime: str = Field(description="The media type; application/octet-stream when unknown.")
    pages: int | None = Field(description="A PDF's page count; null for other files or a broken PDF.")
    protected: bool = Field(description="A PDF that needs a password to open.")
    sha256: str = Field(description="The content's hash.")


class FileVersionResponse(FileResponse):
    """A content a file node had before its current one."""

    id: UUID = Field(description="Version ID.")
    replaced_at: datetime = Field(description="When a newer content took its place.")


class FileNodeRead(NodeRead):
    """A file node with its path and current content."""

    path: str = Field(description="Titles from the base's root down to the node, joined by /.")
    file: FileResponse = Field(description="The current content.")
    versions: int = Field(description="How many contents it has had, the current one included.")


class FileLink(BaseModel):
    """A short-lived URL of a file's bytes that opens without the session cookie."""

    url: str = Field(description="The raw route with `expires` and `signature` query parameters.")
    expires_at: datetime = Field(description="When the link stops working.")
