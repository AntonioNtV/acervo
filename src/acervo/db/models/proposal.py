from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Proposal(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "proposal"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'editing', 'accepted', 'applied', 'rejected', 'stale')",
            name="status",
        ),
        CheckConstraint(
            "reject_reason in ('wrong_place', 'already_there', 'wrong_info', 'not_worth_keeping')",
            name="reject_reason",
        ),
    )

    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]]
    edited_payload: Mapped[dict[str, Any] | None]
    alternatives: Mapped[list[Any] | None]
    status: Mapped[str] = mapped_column(Text, server_default="pending", default="pending")
    reject_reason: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[UUID | None] = mapped_column(index=True)
    # proposal and page_version point at each other; this side is added once page_version exists.
    base_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("page_version.id", use_alter=True))
