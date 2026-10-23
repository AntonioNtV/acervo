from uuid import UUID

from pydantic import BaseModel, Field


class FavoritePlace(BaseModel):
    """Where a node goes among the person's favorites."""

    before_id: UUID | None = Field(default=None, description="Favorite it goes just before; null to put it last.")
