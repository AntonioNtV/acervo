from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acervo.domain.cards import Placement

ProposalKind = Literal["append", "edit", "create_page", "conflict", "save_pdf", "replace_pdf", "move", "rename", "undo"]
ProposalStatus = Literal["pending", "applied", "rejected", "stale"]
RejectReason = Literal["wrong_place", "already_there", "wrong_info", "not_worth_keeping"]
AcceptedBy = Literal["person", "auto"]


class StagedFile(BaseModel):
    """A file waiting in storage, outside the base's tree, search and Lixeira."""

    storage_key: str = Field(description="Where the bytes wait.")
    sha256: str = Field(description="Hash of the bytes.")
    size: int = Field(description="Size in bytes.")
    name: str = Field(description="The file's name as received.")


class PatchPayload(BaseModel):
    """Lines added to a section of a page, or one line changed in it (skill `markdown-pages`)."""

    kind: Literal["append", "edit"] = Field(description="append adds lines to the section; edit changes a line.")
    page_id: UUID = Field(description="The page.")
    path: str = Field(description="The page's path from the base's root, joined by /.")
    base_version_id: UUID = Field(description="The version the lines were written against.")
    anchor: str = Field(description="The section's anchor; empty for the text before the first ##.")
    heading: str = Field(description="The section's heading, to show.")
    op: Literal["append", "insert_after", "replace", "new_section"] = Field(description="How the lines go in.")
    line: str | None = Field(
        default=None, description="For insert_after and replace: the exact text of the line it refers to."
    )
    lines: list[str] = Field(description="The lines to add, each followed by its provenance comment.")


class CreatePagePayload(BaseModel):
    """A new page under a folder or page."""

    kind: Literal["create_page"] = "create_page"
    parent_id: UUID | None = Field(description="Where it goes; null for the base's root.")
    parent_path: str = Field(description="The parent's path, joined by /; empty for the root.")
    title: str = Field(description="The page's title.")
    markdown: str = Field(description="Its first version.")


class ConflictPayload(BaseModel):
    """A fact that contradicts a page: both texts, for the person to choose."""

    kind: Literal["conflict"] = "conflict"
    page_id: UUID = Field(description="The page.")
    path: str = Field(description="The page's path, joined by /.")
    base_version_id: UUID = Field(description="The version the current text comes from.")
    anchor: str = Field(description="The section's anchor.")
    heading: str = Field(description="The section's heading, to show.")
    current: str = Field(description="What the page says now.")
    new: str = Field(description="What the input says.")


class SavePdfPayload(BaseModel):
    """A staged PDF saved under a folder or page."""

    kind: Literal["save_pdf"] = "save_pdf"
    parent_id: UUID | None = Field(description="Where it goes; null for the base's root.")
    parent_path: str = Field(description="The parent's path, joined by /; empty for the root.")
    name: str = Field(description="The suggested name, ending in .pdf; editable before accepting.")


class ReplacePdfPayload(BaseModel):
    """A staged PDF as the new version of a file already in the base; the old one goes to its history."""

    kind: Literal["replace_pdf"] = "replace_pdf"
    node_id: UUID = Field(description="The file replaced.")
    path: str = Field(description="The file's path, joined by /.")


class MovePayload(BaseModel):
    """A node moved under another folder or page of the same base."""

    kind: Literal["move"] = "move"
    node_id: UUID = Field(description="The node moved.")
    from_path: str = Field(description="Its path now.")
    parent_id: UUID | None = Field(description="Its new parent; null for the base's root.")
    to_path: str = Field(description="The new parent's path; empty for the root.")


class RenamePayload(BaseModel):
    """A node renamed; links to a renamed page are fixed."""

    kind: Literal["rename"] = "rename"
    node_id: UUID = Field(description="The node renamed.")
    path: str = Field(description="Its path now.")
    title: str = Field(description="The new title.")


class UndoPayload(BaseModel):
    """Undoing an applied proposal: a page back to its previous version, a file to its previous place or version."""

    kind: Literal["undo"] = "undo"
    proposal_id: UUID = Field(description="The applied proposal it undoes.")
    path: str = Field(description="The path of what it changes back.")


ProposalPayload = Annotated[
    PatchPayload
    | CreatePagePayload
    | ConflictPayload
    | SavePdfPayload
    | ReplacePdfPayload
    | MovePayload
    | RenamePayload
    | UndoPayload,
    Field(discriminator="kind"),
]


class ProposalCreate(BaseModel):
    """A proposal to store."""

    kb_id: UUID = Field(description="Base it changes.")
    agent_id: UUID = Field(description="The agent that made it.")
    conversation_id: UUID | None = Field(default=None, description="Conversation it came from.")
    message_id: UUID | None = Field(default=None, description="The reply it belongs to.")
    run_id: UUID | None = Field(default=None, description="The run whose decisions produced it.")
    payload: ProposalPayload = Field(description="What it does; its `kind` is the proposal's kind.")
    alternatives: list[Placement] | None = Field(
        default=None, description="Other places that were close: the second path, or the top 3 when unsure."
    )
    staged: StagedFile | None = Field(default=None, description="The waiting PDF of a save_pdf or replace_pdf.")
    undo_of: UUID | None = Field(default=None, description="The applied proposal an undo reverts.")


class ProposalUpdate(BaseModel):
    """Fields to change on a proposal; omitted fields keep their value."""

    status: ProposalStatus | None = Field(default=None, description="New status.")
    reject_reason: RejectReason | None = Field(default=None, description="Why the person rejected it.")
    edited_payload: ProposalPayload | None = Field(default=None, description="The person's edited version.")
    accepted_by: AcceptedBy | None = Field(default=None, description="Who accepted it.")
    applied_at: datetime | None = Field(default=None, description="When it changed the base.")
    base_version_id: UUID | None = Field(default=None, description="The version it applies against.")


class ProposalRead(ProposalCreate):
    """A stored proposal: the only way an agent's change gets into a base."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Proposal ID.")
    kind: ProposalKind = Field(description="What it does.")
    status: ProposalStatus = Field(description="pending until accepted, rejected or stale.")
    edited_payload: ProposalPayload | None = Field(description="The person's edited version; the original stays.")
    reject_reason: RejectReason | None = Field(description="Why the person rejected it.")
    accepted_by: AcceptedBy | None = Field(description="The person, or auto for an agent in auto mode.")
    applied_at: datetime | None = Field(description="When it changed the base; null until then.")
    created_at: datetime = Field(description="When it was made.")
    updated_at: datetime = Field(description="When it last changed.")


class ProposalSummary(ProposalRead):
    """A proposal as the chat's list shows it, with where it came from."""

    agent_name: str = Field(description="The agent that made it.")
    conversation_title: str | None = Field(description="The conversation it came from; null when none.")


class ProposalReject(BaseModel):
    """Rejecting a proposal; the reason labels it for calibration."""

    reason: RejectReason = Field(description="Why it is rejected.")


class DecisionLogCreate(BaseModel):
    """One question asked of the decider, with its answer and what code did with it (rule 7)."""

    run_id: UUID = Field(description="The run that asked; the proposal it produced stores it too.")
    message_id: UUID | None = Field(default=None, description="The message the run handled.")
    step: str = Field(description="The step that asked: route, descent, page_check, pdf_check, organize.")
    question_type: Literal["noul", "choice"] = Field(description="The kind of question.")
    options: list[str] = Field(description="A Choice's options in order; a Noul's question.")
    probs: list[float] = Field(description="One probability per option; a Noul's P(yes).")
    threshold: float | None = Field(default=None, description="The cut-off the answer was compared to, if any.")
    action: str = Field(description="What code did with the answer.")
    latency_ms: int = Field(description="How long the call took.")
    cached: bool = Field(default=False, description="Answered from the cache, without a call.")


class DecisionLogRead(DecisionLogCreate):
    """A logged decision."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Decision ID.")
    created_at: datetime = Field(description="When it was asked.")
