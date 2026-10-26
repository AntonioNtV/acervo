from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class EmailCode(UUIDPkMixin, TimestampMixin, Base):
    """A 6-digit code sent to `target_email`, kept hashed."""

    __tablename__ = "email_code"
    __table_args__ = (
        CheckConstraint("purpose in ('verify_email', 'change_email', 'two_factor')", name="purpose"),
        # Asking for a new code first marks the live one used.
        Index("uq_email_code_live", "account_id", "purpose", unique=True, postgresql_where=text("used_at is null")),
    )

    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(Text)
    target_email: Mapped[str] = mapped_column(Text)
    code_hash: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime]
    attempts: Mapped[int] = mapped_column(server_default="0", default=0)
    used_at: Mapped[datetime | None]
