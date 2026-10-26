from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class PasswordReset(UUIDPkMixin, TimestampMixin, Base):
    """A single-use reset link; the link holds the token, the table only its hash."""

    __tablename__ = "password_reset"

    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
