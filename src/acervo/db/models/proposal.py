from datetime import datetime
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
        CheckConstraint(
            "kind in ('append', 'edit', 'create_page', 'conflict', 'save_pdf', 'replace_pdf', 'move', 'rename', "
            "'undo')",
            name="kind",
        ),
        CheckConstraint("accepted_by in ('person', 'auto')", name="accepted_by"),
    )

    kb_id: Mapped[UUID] = mapped_column(ForeignKey("kb.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.id"))
    conversation_id: Mapped[UUID | None] = mapped_column(ForeignKey("conversation.id"))
    message_id: Mapped[UUID | None] = mapped_column(ForeignKey("message.id"), index=True)

    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]]
    edited_payload: Mapped[dict[str, Any] | None]
    alternatives: Mapped[list[Any] | None]
    status: Mapped[str] = mapped_column(Text, server_default="pending", default="pending")
    reject_reason: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[UUID | None] = mapped_column(index=True)
    # proposal and page_version point at each other; this side is added once page_version exists.
    base_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("page_version.id", use_alter=True))
    accepted_by: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None]
    # A dropped PDF waiting in storage until the proposal is accepted: storage key, sha256, size and name.
    staged: Mapped[dict[str, Any] | None]
    undo_of: Mapped[UUID | None] = mapped_column(ForeignKey("proposal.id"))
