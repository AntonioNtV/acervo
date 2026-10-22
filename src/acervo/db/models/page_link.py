from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class PageLink(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "page_link"
    __table_args__ = (Index("ix_page_link_kb_id_target", "kb_id", "target"),)

    kb_id: Mapped[UUID] = mapped_column(ForeignKey("kb.id"))
    from_node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id"), index=True)
    # The normalized title inside `[[…]]`.
    target: Mapped[str] = mapped_column(Text)
