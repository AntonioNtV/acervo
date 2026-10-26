from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class PageVersion(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "page_version"

    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id"), index=True)
    markdown: Mapped[str] = mapped_column(Text)
    edit_started_at: Mapped[datetime | None]
    edit_ended_at: Mapped[datetime | None]
    # Null for versions saved before authors were recorded, and once the author's account is deleted.
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("account.id", ondelete="SET NULL"))
    # False only for versions saved before authors were recorded: their null author is not a deleted account.
    author_known: Mapped[bool] = mapped_column(server_default=true(), default=True)
