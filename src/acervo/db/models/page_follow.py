from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base


class PageFollow(Base):
    """A page an account follows for the daily digest."""

    __tablename__ = "page_follow"

    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), primary_key=True)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
