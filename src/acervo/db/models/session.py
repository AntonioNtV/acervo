from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Session(UUIDPkMixin, TimestampMixin, Base):
    """A signed-in browser; the cookie holds the token, the table only its hash."""

    __tablename__ = "session"

    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), index=True)
    last_seen_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    user_agent: Mapped[str | None] = mapped_column(Text)
