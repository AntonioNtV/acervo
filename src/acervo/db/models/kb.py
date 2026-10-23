from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Kb(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "kb"

    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="", default="")
    deleted_at: Mapped[datetime | None]
    icon: Mapped[str | None] = mapped_column(Text)
