from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from acervo.schemas.account import Language


class DigestAccount(BaseModel):
    """An account as the daily digest reads it: where to send, in which language, when it is 8:00 for it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    language: Language
    timezone: str
    digest_sent_on: date | None


class DigestChange(BaseModel):
    """A version saved in the window, on a followed page, with what the digest lists of it."""

    node_id: UUID
    title: str
    base: str
    author_id: UUID | None
    author: str | None
    author_known: bool
