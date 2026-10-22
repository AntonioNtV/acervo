from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class FileColumns:
    """What is known about one stored file. Metadata only: never its text (rule 1 of CLAUDE.md)."""

    storage_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text, index=True)
    size: Mapped[int] = mapped_column(BigInteger)
    mime: Mapped[str] = mapped_column(Text)
    pages: Mapped[int | None]
    protected: Mapped[bool] = mapped_column(server_default="false", default=False)
    doc_type: Mapped[str | None] = mapped_column(Text)
    sensitive: Mapped[bool] = mapped_column(server_default="false", default=False)
    map: Mapped[dict[str, Any] | None]
    map_origin: Mapped[str | None] = mapped_column(Text)


class File(UUIDPkMixin, TimestampMixin, FileColumns, Base):
    __tablename__ = "file"
    __table_args__ = (CheckConstraint("map_origin in ('bookmarks', 'toc', 'generated')", name="map_origin"),)

    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id"), unique=True)
