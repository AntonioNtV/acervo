"""Events streamed to the chat over SSE, one stream per conversation."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from acervo.schemas.conversation import MessageRead
from acervo.schemas.proposal import ProposalRead

StepName = Literal[
    "understanding",
    "splitting",
    "reading_file",
    "choosing_place",
    "checking_page",
    "checking_pdf",
    "writing",
    "organizing",
]


class StepEvent(BaseModel):
    """A step of the job working on a reply, shown live in the thread."""

    type: Literal["step"] = "step"
    message_id: UUID = Field(description="The reply being worked on.")
    step: StepName = Field(description="What the job is doing; the app shows its own text for it.")
    detail: str | None = Field(default=None, description="What it is done to: a file's name, a folder's path.")


class MessageEvent(BaseModel):
    """A message stored or changed: the person's, or Acervo's reply."""

    type: Literal["message"] = "message"
    message: MessageRead


class ProposalEvent(BaseModel):
    """A proposal created or changed by a reply."""

    type: Literal["proposal"] = "proposal"
    proposal: ProposalRead


class DoneEvent(BaseModel):
    """The job of a reply ended; its message and proposals are final."""

    type: Literal["done"] = "done"
    message_id: UUID = Field(description="The reply.")


class ErrorEvent(BaseModel):
    """The job of a reply failed; nothing it did was applied."""

    type: Literal["error"] = "error"
    message_id: UUID = Field(description="The reply.")
    error: str = Field(description="Error code, as in ErrorResponse.")
    message: str = Field(description="Human-readable explanation; the app shows the code's own text instead.")


ChatEvent = Annotated[StepEvent | MessageEvent | ProposalEvent | DoneEvent | ErrorEvent, Field(discriminator="type")]
