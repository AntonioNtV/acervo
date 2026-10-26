from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Account(UUIDPkMixin, TimestampMixin, Base):
    """A person; `account` because `user` is reserved in Postgres."""

    __tablename__ = "account"
    __table_args__ = (
        # Stored as typed, unique ignoring case.
        Index("uq_account_email_lower", text("lower(email)"), unique=True),
        CheckConstraint("theme in ('light', 'dark', 'system')", name="theme"),
        CheckConstraint("page_width in ('default', 'wide')", name="page_width"),
        CheckConstraint("language in ('pt-BR', 'en')", name="language"),
        CheckConstraint("start_page in ('last', 'bases')", name="start_page"),
    )

    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    # Null for an account that only signs in with Google.
    password_hash: Mapped[str | None] = mapped_column(Text)
    google_sub: Mapped[str | None] = mapped_column(Text, unique=True)
    email_verified_at: Mapped[datetime | None]
    photo_key: Mapped[str | None] = mapped_column(Text)
    theme: Mapped[str] = mapped_column(Text, server_default="system")
    page_width: Mapped[str] = mapped_column(Text, server_default="default")
    language: Mapped[str] = mapped_column(Text, server_default="pt-BR")
    start_page: Mapped[str] = mapped_column(Text, server_default="last")
