from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base


class EmailCopy(Base):
    """An email's text as an admin edited it, with the keys of `mail_templates.Copy`; none: the code's text."""

    __tablename__ = "email_copy"
    __mapper_args__ = {"eager_defaults": True}

    template: Mapped[str] = mapped_column(Text, primary_key=True)
    language: Mapped[str] = mapped_column(Text, primary_key=True)
    copy: Mapped[dict[str, Any]]
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("account.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
