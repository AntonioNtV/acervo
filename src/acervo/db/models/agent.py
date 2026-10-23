from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Agent(UUIDPkMixin, TimestampMixin, Base):
    """A connection that files into one base: the built-in chat, or an external agent over MCP with a token."""

    __tablename__ = "agent"
    __table_args__ = (
        CheckConstraint("mode in ('ask', 'auto')", name="mode"),
        Index("uq_agent_built_in", "kb_id", unique=True, postgresql_where=text("built_in")),
    )

    kb_id: Mapped[UUID] = mapped_column(ForeignKey("kb.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text, server_default="ask", default="ask")
    built_in: Mapped[bool] = mapped_column(server_default="false", default=False)
    # sha256 of the token, which is shown once and never stored; null for the built-in chat.
    token_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    token_hint: Mapped[str | None] = mapped_column(Text)
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
