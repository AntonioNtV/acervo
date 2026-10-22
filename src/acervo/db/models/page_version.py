from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class PageVersion(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "page_version"
    __table_args__ = (CheckConstraint("author in ('user', 'agent')", name="author"),)

    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id"), index=True)
    markdown: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(Text)
    proposal_id: Mapped[UUID | None] = mapped_column(ForeignKey("proposal.id"))
