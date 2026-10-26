from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class PageDraft(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "page_draft"

    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id"), unique=True)
    markdown: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(server_default="0")
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Who typed it last: the version it is cut into is theirs, whoever's request does the cut.
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("account.id", ondelete="SET NULL"))
