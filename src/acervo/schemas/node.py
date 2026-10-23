from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from acervo.schemas.index import IndexState

NodeKind = Literal["folder", "page", "file"]


def _emoji(icon: str) -> str:
    # One emoji, sequences such as flags, skin tones and families included; never a word or a number.
    if not icon or len(icon) > 16 or any(char.isascii() and char.isalnum() for char in icon):
        raise ValueError("an icon is one emoji")
    return icon


Icon = Annotated[str, AfterValidator(_emoji)]
GalleryCover = Annotated[str, Field(pattern=r"^gallery:[a-z0-9-]{1,32}$")]


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
    icon: str | None = Field(default=None, description="An emoji; null removes it.")
    cover: str | None = Field(default=None, description="`gallery:<slug>` or `image:<sha256>`; null removes it.")
    favorite_sort: str | None = Field(default=None, description="Sort key among the favorites; null unfavorites.")


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
    icon: str | None = Field(description="An emoji shown before the title; null for none.")
    cover: str | None = Field(
        description="`gallery:<slug>` from the gallery or `image:<sha256>` uploaded; null for none."
    )
    favorite: bool = Field(description="Whether it is in the person's favorites.")
    index_state: IndexState = Field(default="none", description="Its search index; none for a folder.")
    created_at: datetime = Field(description="When the node was created.")
    updated_at: datetime = Field(description="When the node last changed.")


class NodeAdd(BaseModel):
    """A new folder or page; files come from an upload."""

    parent_id: UUID | None = Field(default=None, description="Folder to create it in; null for the base's root.")
    kind: Literal["folder", "page"] = Field(description="What to create.")
    title: str = Field(description="Title; no live sibling of the same kind may have it already.")


class NodeEdit(BaseModel):
    """What the person changes on a node; omitted fields keep their value."""

    title: str | None = Field(default=None, description="New title; no live sibling of the same kind may have it.")
    description: str | None = Field(
        default=None, max_length=200, description="New description; once the person edits it, agents keep it."
    )
    icon: Icon | None = Field(default=None, description="An emoji; null removes it.")
    cover: GalleryCover | None = Field(
        default=None, description="`gallery:<slug>`, for folders and pages only; null removes it."
    )


class NodeMove(BaseModel):
    """Where to put a node."""

    kb_id: UUID | None = Field(default=None, description="Destination base; null for the node's own base.")
    parent_id: UUID | None = Field(default=None, description="Destination folder; null for the base's root.")
    before_id: UUID | None = Field(default=None, description="Sibling it goes just before; null to put it last.")


class TreeNode(NodeRead):
    """A node as the tree shows it."""

    protected: bool = Field(description="A password-protected PDF; false for anything else.")
    child_count: int = Field(description="How many live nodes are right under it.")
    pages: int | None = Field(description="A PDF's page count; null for anything else.")
    size: int | None = Field(description="A file's size in bytes; null for folders and pages.")


class NodeWithPath(NodeRead):
    """A node found by the name search, or trashed on its own."""

    path: str = Field(description="Titles from the base's root down to the node, joined by /.")


class RestoredNode(NodeRead):
    """A node back from the trash."""

    to_root: bool = Field(description="Its old folder was gone, so it came back at the base's root.")
