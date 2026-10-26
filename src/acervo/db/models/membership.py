from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Membership(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "membership"
    __table_args__ = (
        UniqueConstraint("organization_id", "account_id"),
        CheckConstraint("role in ('owner', 'admin', 'member')", name="role"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"))
    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(Text)
