from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

NodeKind = Literal["folder", "page", "file"]


class NodeCreate(BaseModel):
    """A node to create in a base's tree."""

    kb_id: UUID = Field(description="Base the node belongs to.")
    parent_id: UUID | None = Field(description="Folder that holds the node; null for the base's root.")
    kind: NodeKind = Field(description="folder, page or file.")
    title: str = Field(min_length=1, description="Title; a file's keeps its extension, a page's does not.")
    sort: str = Field(description="Fractional sort key among its siblings.")
    description: str = Field(default="", description="What the node holds.")


class NodeUpdate(BaseModel):
    """Fields to change on a node; omitted fields keep their value."""

    parent_id: UUID | None = Field(default=None, description="New folder; null for the base's root.")
    title: str | None = Field(default=None, min_length=1, description="New title.")
    sort: str | None = Field(default=None, description="New sort key.")
    description: str | None = Field(default=None, description="New description.")
    description_locked: bool | None = Field(default=None, description="Whether agents may rewrite the description.")
    deleted_at: datetime | None = Field(default=None, description="When the node went to the trash; null restores it.")
    trashed_with: UUID | None = Field(default=None, description="Node whose trashing hid this one.")


class NodeRead(BaseModel):
    """A saved node of a base's tree."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Node ID.")
    kb_id: UUID = Field(description="Base the node belongs to.")
    parent_id: UUID | None = Field(description="Folder that holds the node; null for the base's root.")
    kind: NodeKind = Field(description="folder, page or file.")
    title: str = Field(description="Title; a file's keeps its extension, a page's does not.")
    description: str = Field(description="What the node holds.")
    description_locked: bool = Field(description="Whether agents may rewrite the description.")
    sort: str = Field(description="Fractional sort key among its siblings.")
    deleted_at: datetime | None = Field(description="When the node went to the trash; null while it is live.")
    trashed_with: UUID | None = Field(description="Node whose trashing hid this one.")
    created_at: datetime = Field(description="When the node was created.")
    updated_at: datetime = Field(description="When the node last changed.")


class NodeAdd(BaseModel):
    """A new folder or page; files come from an upload."""

    parent_id: UUID | None = Field(default=None, description="Folder to create it in; null for the base's root.")
    kind: Literal["folder", "page"] = Field(description="What to create.")
    title: str = Field(description="Title; no live sibling of the same kind may have it already.")


class NodeRename(BaseModel):
    """A new title for a node."""

    title: str = Field(description="New title; no live sibling of the same kind may have it already.")


class NodeMove(BaseModel):
    """Where to put a node."""

    parent_id: UUID | None = Field(default=None, description="Destination folder; null for the base's root.")
    before_id: UUID | None = Field(default=None, description="Sibling it goes just before; null to put it last.")


class TreeNode(NodeRead):
    """A node as the tree shows it."""

    protected: bool = Field(description="A password-protected PDF; false for anything else.")


class NodeWithPath(NodeRead):
    """A node found by the name search, or trashed on its own."""

    path: str = Field(description="Titles from the base's root down to the node, joined by /.")


class RestoredNode(NodeRead):
    """A node back from the trash."""

    to_root: bool = Field(description="Its old folder was gone, so it came back at the base's root.")
