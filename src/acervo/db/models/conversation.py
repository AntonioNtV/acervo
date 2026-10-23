from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Conversation(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "conversation"

    kb_id: Mapped[UUID] = mapped_column(ForeignKey("kb.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.id"), index=True)
    title: Mapped[str] = mapped_column(Text, server_default="", default="")
    deleted_at: Mapped[datetime | None]
