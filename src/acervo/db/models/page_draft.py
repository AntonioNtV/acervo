from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class PageDraft(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "page_draft"

    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id"), unique=True)
    markdown: Mapped[str] = mapped_column(Text)
    base_version_id: Mapped[UUID] = mapped_column(ForeignKey("page_version.id"))
