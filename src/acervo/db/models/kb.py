from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Kb(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "kb"
    __table_args__ = (CheckConstraint("general_access in ('none', 'reader', 'editor')", name="general_access"),)

    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="", default="")
    deleted_at: Mapped[datetime | None]
    icon: Mapped[str | None] = mapped_column(Text)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organization.id"), index=True)
    # What every member of the organization gets on the base; guests never get it.
    general_access: Mapped[str] = mapped_column(Text, server_default="editor")
