from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class PageVersion(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "page_version"

    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id"), index=True)
    markdown: Mapped[str] = mapped_column(Text)
    edit_started_at: Mapped[datetime | None]
    edit_ended_at: Mapped[datetime | None]
