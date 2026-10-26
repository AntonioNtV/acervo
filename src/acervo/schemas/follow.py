from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FollowCreate(BaseModel):
    """A page an account follows, for the daily digest."""

    account_id: UUID = Field(description="Account that follows the page.")
    node_id: UUID = Field(description="The followed page.")


class FollowRead(FollowCreate):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime = Field(description="When it started following.")
