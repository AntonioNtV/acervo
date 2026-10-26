from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class PendingSignIn(UUIDPkMixin, TimestampMixin, Base):
    """The step between a right password and the two-step code: not a session, it opens nothing."""

    __tablename__ = "pending_sign_in"
    __table_args__ = (CheckConstraint("method in ('email', 'whatsapp')", name="method"),)

    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime]
    code_hash: Mapped[str] = mapped_column(Text)
    # A resend replaces the code; the wait before the next counts from here.
    code_sent_at: Mapped[datetime]
    attempts: Mapped[int] = mapped_column(server_default="0", default=0)
    # Where the code went; "Receber por email" moves a WhatsApp one to email.
    method: Mapped[str] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
