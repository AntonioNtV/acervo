from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Invite(UUIDPkMixin, TimestampMixin, Base):
    """An email invited to an organization, or to one of its bases (`kb_id`); the link holds the token."""

    __tablename__ = "invite"
    __table_args__ = (CheckConstraint("role in ('owner', 'admin', 'member', 'reader', 'editor')", name="role"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    kb_id: Mapped[UUID | None] = mapped_column(ForeignKey("kb.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    invited_by: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
