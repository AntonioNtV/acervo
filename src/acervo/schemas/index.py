from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from acervo.domain.index import DocIndex

IndexStatus = Literal["building", "ready", "failed"]
IndexState = Literal["building", "ready", "failed", "none"]


class NodeIndexRead(BaseModel):
    """Where the index of a file or a page stands; its parsed content is read on its own."""

    model_config = ConfigDict(from_attributes=True)

    node_id: UUID = Field(description="The file or the page.")
    version_key: str = Field(description="The file's sha256 or the page version's ID the ready index is of.")
    building_key: str | None = Field(description="The version being indexed while the previous index stays readable.")
    status: IndexStatus = Field(description="building, ready or failed.")
    outline: str = Field(description="The outline of the readable index; empty until the first build finishes.")
    error: str | None = Field(description="Why the last build failed; null unless it failed.")
    updated_at: datetime = Field(description="When it last changed.")


class NodeIndexParsed(NodeIndexRead):
    """The index with its parsed content, for search."""

    parsed: DocIndex | None = Field(description="The readable index; null until the first build finishes.")
