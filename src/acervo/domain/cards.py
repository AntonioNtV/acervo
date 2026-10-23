"""What the chat understands of an input and where the Curator files it (skill `curator-agent`)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Route = Literal["perguntar", "guardar", "organizar", "conversar"]
# The options of the route Choice, in the order ties are broken.
ROUTES: tuple[Route, ...] = ("perguntar", "guardar", "organizar", "conversar")
OrganizeKind = Literal["move", "rename", "undo"]
# The options of the organize Choice, in the order ties are broken.
ORGANIZE_KINDS: tuple[OrganizeKind, ...] = ("move", "rename", "undo")
# How the person says a message is to be read when the chat asks: a route, or which change an organizar is.
Reading = Route | OrganizeKind

NodeKind = Literal["folder", "page", "file"]


class CardInput(BaseModel):
    """What the LLM `card` role reads: a chat message, or a PDF's first pages and outline (never the whole PDF)."""

    text: str = Field(description="The message, or the text of the PDF's first pages.")
    file_name: str | None = Field(default=None, description="The PDF's name; null for a message.")
    outline: list[str] = Field(default_factory=list, description="The PDF's outline titles, in order.")


class Card(BaseModel):
    """The LLM's summary of an input, from which places are chosen and lines written."""

    title: str = Field(description="A short title, used for a new page.")
    subject: str = Field(description="What the input is about, in one line.")
    entities: list[str] = Field(default_factory=list, description="Insurers, products, people, documents named.")
    facts: list[str] = Field(default_factory=list, description="The key facts, one per item.")
    file_name: str | None = Field(default=None, description="A suggested name ending in .pdf; null for a message.")


class Placement(BaseModel):
    """A place the descent reached, as the proposal shows it and as "Outro lugar" swaps to."""

    node_id: UUID | None = Field(description="The folder or page it stopped at; null for the base's root.")
    path: str = Field(description="Titles from the root down to that node, joined by /; empty for the root.")
    landing: Literal["page", "here", "new_page", "new_folder"] = Field(
        description="Into that page's text, under that node (save or stay here), or a new page or folder under it."
    )
    probability: float = Field(description="The product of the chosen options' probabilities along the path.")


class PatchRequest(BaseModel):
    """What the LLM `patch` role reads to write the lines of an append or an edit."""

    section_markdown: str = Field(description="The chosen section of the page's newest version.")
    heading: str = Field(description="The section's heading.")
    action: Literal["append", "edit"] = Field(description="Decided in code: add lines, or change one line.")
    card: Card


class WrittenPatch(BaseModel):
    """The lines the LLM wrote for a patch, without provenance comments (code adds them)."""

    lines: list[str] = Field(description="The lines to add, or the line that replaces `replaces`.")
    replaces: str | None = Field(default=None, description="For an edit: the exact text of the line it replaces.")


class ChildDescription(BaseModel):
    """One child of a node, as the LLM `describe` role reads it."""

    title: str
    kind: NodeKind
    description: str
