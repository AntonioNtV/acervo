from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin
from acervo.db.models.file import FileColumns


class FileVersion(UUIDPkMixin, TimestampMixin, FileColumns, Base):
    __tablename__ = "file_version"
    __table_args__ = (CheckConstraint("map_origin in ('bookmarks', 'toc', 'generated')", name="map_origin"),)

    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id"), index=True)
    replaced_at: Mapped[datetime]
