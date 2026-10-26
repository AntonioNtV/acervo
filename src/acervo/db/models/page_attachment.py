from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class PageAttachment(UUIDPkMixin, TimestampMixin, Base):
    """A file put in a page, kept byte for byte; not a node, so the tree and the search never list it."""

    __tablename__ = "page_attachment"
    __table_args__ = (UniqueConstraint("page_id", "name"),)

    page_id: Mapped[UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"))
    # What the page's Markdown calls it: `arquivos/<name>`.
    name: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger)
