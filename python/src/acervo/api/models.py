import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Every error the API answers with, whatever its status."""

    error: str = Field(description="The error's class: ValidationError, NotFoundError, ConflictError, …")
    message: str = Field(description="What went wrong, in words the app may show.")
    detail: dict[str, Any] | None = Field(None, description="What the person needs to act on a conflict, if any.")


class DiffLineResponse(BaseModel):
    """One line of a difference between two texts, in reading order."""

    op: Literal["same", "add", "del"] = Field(description="In both texts, only in the new one or only in the old.")
    text: str = Field(description="The line, without its line break.")


class StalePageDetail(BaseModel):
    """Why a save was refused: the page got a newer version after the person opened it."""

    current_version_id: uuid.UUID = Field(description="The page's newest version.")
    markdown: str = Field(description="The newest version's whole text.")
    diff: list[DiffLineResponse] = Field(description="From the version the person opened to the newest one.")


class StalePageResponse(ErrorResponse):
    """The 409 of a save over a page that changed since it was opened."""

    detail: StalePageDetail = Field(description="The newest version and the difference from the person's base.")


class KbResponse(BaseModel):
    """A base."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="The base's id.")
    name: str = Field(description="The base's name.")
    description: str = Field(description="What the base holds, as the person wrote it; may be empty.")
    deleted_at: datetime | None = Field(description="When the base went to the trash; null while it is live.")


class KbSummaryResponse(KbResponse):
    """A base as the Bases screen lists it."""

    pages: int = Field(description="Live pages in the base.")
    files: int = Field(description="Live files in the base.")
    last_edit: datetime = Field(description="The newest change to the base, its nodes, pages or files.")


class CreateKbRequest(BaseModel):
    """A new base."""

    name: str = Field(description="The base's name; cannot be empty.")
    description: str = Field("", description="What the base holds.")


class UpdateKbRequest(BaseModel):
    """A change to a base; a field left out stays as it is."""

    name: str | None = Field(None, description="The new name; cannot be empty.")
    description: str | None = Field(None, description="The new description.")


class NodeResponse(BaseModel):
    """An item of a base's tree."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="The node's id.")
    kb_id: uuid.UUID = Field(description="The base it belongs to.")
    parent_id: uuid.UUID | None = Field(description="Its folder; null at the base's root.")
    kind: Literal["folder", "page", "file"] = Field(description="What the node is.")
    title: str = Field(description="A file's title keeps its extension; a page's does not.")
    deleted_at: datetime | None = Field(description="When it went to the trash; null while it is live.")


class TreeNodeResponse(NodeResponse):
    """A node as the tree shows it."""

    protected: bool = Field(description="A password-protected PDF; false for anything else.")


class SearchHitResponse(NodeResponse):
    """A node found by the name search."""

    path: str = Field(description="Titles from the base's root down to the node, joined by /.")


class TrashItemResponse(NodeResponse):
    """A node trashed on its own; what was under it went with it."""

    path: str = Field(description="Where it was when it was trashed.")


class RestoredNodeResponse(NodeResponse):
    """A node back from the trash."""

    to_root: bool = Field(description="Its old folder was gone, so it came back at the base's root.")


class CreateNodeRequest(BaseModel):
    """A new folder or page; a page starts with an empty first version."""

    parent_id: uuid.UUID | None = Field(None, description="The folder to create it in; null for the base's root.")
    kind: Literal["folder", "page"] = Field(description="What to create. Files come from an upload.")
    title: str = Field(description="Its title; no sibling of the same kind may have it already.")


class RenameNodeRequest(BaseModel):
    """A new title. Renaming a page also fixes the `[[…]]` links that pointed to it."""

    title: str = Field(description="The new title; no sibling of the same kind may have it already.")


class MoveNodeRequest(BaseModel):
    """Where to put a node."""

    parent_id: uuid.UUID | None = Field(None, description="The destination folder; null for the base's root.")
    before_id: uuid.UUID | None = Field(None, description="The sibling it goes just before; null to put it last.")


class SectionResponse(BaseModel):
    """A `##` heading of a page."""

    anchor: str = Field(description="Unique in the page, for `#anchor` links.")
    heading: str = Field(description="The heading's text.")


class DraftResponse(BaseModel):
    """The page's single autosaved draft. Never a version."""

    model_config = ConfigDict(from_attributes=True)

    markdown: str = Field(description="The draft's whole text.")
    base_version_id: uuid.UUID = Field(description="The version the person was editing.")
    updated_at: datetime = Field(description="When it was last autosaved.")


class PageResponse(BaseModel):
    """What a page holds now."""

    version_id: uuid.UUID = Field(description="The current version, the base of the next save.")
    markdown: str = Field(description="The current version's whole text.")
    draft: DraftResponse | None = Field(description="An unsaved draft to offer to continue; null if there is none.")
    links: dict[str, uuid.UUID | Literal["missing", "ambiguous"]] = Field(
        description="Each `[[…]]` target, keyed with its whitespace collapsed to single spaces and lowercased: the "
        "page it opens, or why it shows in gray."
    )
    sections: list[SectionResponse] = Field(description="The page's `##` headings, in order.")


class FileResponse(BaseModel):
    """What is known about a stored file. Metadata only, never its text."""

    model_config = ConfigDict(from_attributes=True)

    size: int = Field(description="In bytes.")
    mime: str = Field(description="The media type; application/octet-stream when unknown.")
    pages: int | None = Field(description="A PDF's page count; null for other files or a broken PDF.")
    protected: bool = Field(description="A PDF that needs a password to open.")
    sha256: str = Field(description="The content's hash.")


class NodeDetailResponse(NodeResponse):
    """A node opened: a page's text or a file's metadata."""

    path: str = Field(description="Titles from the base's root down to the node, joined by /.")
    page: PageResponse | None = Field(description="Set for a page.")
    file: FileResponse | None = Field(description="Set for a file.")
    versions: int = Field(description="How many versions it has, the current one included; 0 for a folder.")


class SavePageRequest(BaseModel):
    """A new whole-file version of a page."""

    markdown: str = Field(description="The page's whole text.")
    base_version_id: uuid.UUID = Field(description="The version the person opened.")
    force: bool = Field(False, description="Save on top even if the page changed since `base_version_id`.")


class PutDraftRequest(BaseModel):
    """The draft of a page, replacing the previous one."""

    markdown: str = Field(description="The draft's whole text.")
    base_version_id: uuid.UUID = Field(description="The version the person is editing.")


class VersionResponse(BaseModel):
    """One version of a page, or one older content of a file."""

    id: uuid.UUID = Field(description="The version's id.")
    created_at: datetime = Field(description="A page version: when it was written. A file's: when it was replaced.")
    author: Literal["user", "agent"] | None = Field(description="Who wrote a page version; null for a file.")
    size: int | None = Field(description="A file version's size in bytes; null for a page.")


class DiffResponse(BaseModel):
    """A page version against the one before it."""

    lines: list[DiffLineResponse] = Field(description="Every line of both versions, in reading order.")
