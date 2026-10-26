from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class SecurityEvent(UUIDPkMixin, TimestampMixin, Base):
    """One line of an account's activity (`account_id`) or of an organization's audit (`organization_id`)."""

    __tablename__ = "security_event"
    __table_args__ = (Index(None, "account_id", "created_at"), Index(None, "organization_id", "created_at"))

    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"))
    # Who did it, kept in the audit after their account goes.
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("account.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(server_default="{}", default=dict)
    user_agent: Mapped[str | None] = mapped_column(Text)
