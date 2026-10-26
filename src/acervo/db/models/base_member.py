from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class BaseMember(UUIDPkMixin, TimestampMixin, Base):
    """Someone added to one base: a member of its organization, or a guest of that base only."""

    __tablename__ = "base_member"
    __table_args__ = (
        UniqueConstraint("kb_id", "account_id"),
        CheckConstraint("role in ('reader', 'editor', 'admin')", name="role"),
    )

    kb_id: Mapped[UUID] = mapped_column(ForeignKey("kb.id", ondelete="CASCADE"))
    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(Text)
