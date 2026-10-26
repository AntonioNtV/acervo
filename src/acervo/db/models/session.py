from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Session(UUIDPkMixin, TimestampMixin, Base):
    """A signed-in browser; the cookie holds the token, the table only its hash."""

    __tablename__ = "session"
    __table_args__ = (CheckConstraint("method in ('password', 'google', 'passkey', 'reset')", name="method"),)

    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), index=True)
    last_seen_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    user_agent: Mapped[str | None] = mapped_column(Text)
    # The last time the password or a passkey was asked again; sensitive changes need it recent.
    reauthenticated_at: Mapped[datetime | None]
    method: Mapped[str] = mapped_column(Text, server_default="password")
