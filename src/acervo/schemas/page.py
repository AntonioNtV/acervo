from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acervo.schemas.file import FileResponse
from acervo.schemas.node import NodeRead

Author = Literal["user", "agent"]


class PageVersionCreate(BaseModel):
    """A whole-file version of a page, to store. Versions are never updated or deleted."""

    node_id: UUID = Field(description="Page the version belongs to.")
    markdown: str = Field(description="The page's whole text.")
    author: Author = Field(description="Who wrote it.")


class PageVersionSummary(BaseModel):
    """One version of a page in its history, without its text."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Version ID.")
    author: Author = Field(description="Who wrote it.")
    created_at: datetime = Field(description="When it was written.")


class PageVersionRead(PageVersionSummary):
    """A stored version of a page, with its text."""

    node_id: UUID = Field(description="Page the version belongs to.")
    markdown: str = Field(description="The page's whole text.")


class PageDraftCreate(BaseModel):
    """The page's draft, to store in place of the one it had."""

    node_id: UUID = Field(description="Page the draft belongs to.")
    markdown: str = Field(description="The draft's whole text.")
    base_version_id: UUID = Field(description="The version the person was editing.")


class PageDraftRead(BaseModel):
    """The page's single autosaved draft. Never a version."""

    model_config = ConfigDict(from_attributes=True)

    markdown: str = Field(description="The draft's whole text.")
    base_version_id: UUID = Field(description="The version the person was editing.")
    updated_at: datetime = Field(description="When it was last autosaved.")


class PageLinkCreate(BaseModel):
    """A `[[…]]` link of a page's newest version."""

    kb_id: UUID = Field(description="Base of the linking page.")
    from_node_id: UUID = Field(description="The linking page.")
    target: str = Field(description="The title inside `[[…]]`, its whitespace collapsed and lowercased.")


class PageLinkRead(PageLinkCreate):
    """A stored link of a page."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Link ID.")


class Section(BaseModel):
    """A `##` heading of a page."""

    anchor: str = Field(description="Unique in the page, for `#anchor` links.")
    heading: str = Field(description="The heading's text.")


class PageRead(BaseModel):
    """What a page holds now."""

    version_id: UUID = Field(description="The current version, the base of the next save.")
    markdown: str = Field(description="The current version's whole text.")
    draft: PageDraftRead | None = Field(description="An unsaved draft to offer to continue; null if there is none.")
    links: dict[str, UUID | Literal["missing", "ambiguous"]] = Field(
        description="Each `[[…]]` target, keyed with its whitespace collapsed to single spaces and lowercased: the "
        "page it opens, or why it shows in gray."
    )
    sections: list[Section] = Field(description="The page's `##` headings, in order.")


class PageSave(BaseModel):
    """A new whole-file version of a page."""

    markdown: str = Field(description="The page's whole text.")
    base_version_id: UUID = Field(description="The version the person opened.")
    force: bool = Field(default=False, description="Save on top even if the page changed since `base_version_id`.")


class DraftPut(BaseModel):
    """The draft of a page, replacing the previous one."""

    markdown: str = Field(description="The draft's whole text.")
    base_version_id: UUID = Field(description="The version the person is editing.")


class DiffLine(BaseModel):
    """One line of a difference between two texts, in reading order."""

    op: Literal["same", "add", "del"] = Field(description="In both texts, only in the new one or only in the old.")
    text: str = Field(description="The line, without its line break.")


class PageDiff(BaseModel):
    """A page version against the one before it."""

    lines: list[DiffLine] = Field(description="Every line of both versions, in reading order.")


class NodeDetail(NodeRead):
    """A node opened: a page's text or a file's current content."""

    path: str = Field(description="Titles from the base's root down to the node, joined by /.")
    page: PageRead | None = Field(description="Set for a page.")
    file: FileResponse | None = Field(description="Set for a file.")
    versions: int = Field(description="How many versions it has, the current one included; 0 for a folder.")
