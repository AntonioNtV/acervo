from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Message(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "message"
    __table_args__ = (
        CheckConstraint("role in ('person', 'acervo')", name="role"),
        CheckConstraint("status in ('done', 'working', 'failed')", name="status"),
        CheckConstraint("understood_as in ('perguntar', 'guardar', 'organizar', 'conversar')", name="understood_as"),
    )

    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id"), index=True)
    role: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, server_default="", default="")
    attachments: Mapped[list[Any]] = mapped_column(server_default="[]", default=list)
    # The open page and the selected text the person kept as context.
    context: Mapped[dict[str, Any] | None]
    understood_as: Mapped[str | None] = mapped_column(Text)
    # A reply that asks first: the two readings, likeliest first, the person picks between.
    ask: Mapped[list[Any] | None]
    run_id: Mapped[UUID | None] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(Text, server_default="done", default="done")
    error: Mapped[str | None] = mapped_column(Text)
    # A reply redone another way ("era uma pergunta") points at the reply it replaces.
    replaces_id: Mapped[UUID | None] = mapped_column(ForeignKey("message.id"))
