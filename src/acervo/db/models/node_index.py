from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base


class NodeIndex(Base):
    """The search index of a file or a page: extracted text for search only, never content of the base (rule 3)."""

    __tablename__ = "node_index"
    __table_args__ = (CheckConstraint("status in ('building', 'ready', 'failed')", name="status"),)
    __mapper_args__: Any = {"eager_defaults": True}

    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"), primary_key=True)
    # The file's sha256 or the page version's ID that `parsed` is of, or is first being built for.
    version_key: Mapped[str] = mapped_column(Text)
    # The version being built while the previous index stays readable.
    building_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    outline: Mapped[str] = mapped_column(Text, server_default="", default="")
    # A `DocIndex`; null until the first build finishes. Large: loaded only by `get`.
    parsed: Mapped[dict[str, Any] | None] = mapped_column(deferred=True)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
