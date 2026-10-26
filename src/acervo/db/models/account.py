from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, Text, event, exists, text
from sqlalchemy.orm import Mapped, column_property, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin
from acervo.db.models.passkey import Passkey


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
        CheckConstraint("two_factor in ('none', 'email', 'whatsapp')", name="two_factor"),
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
    # How a password sign-in gets its code; a passkey or Google sign-in never asks it.
    two_factor: Mapped[str] = mapped_column(Text, server_default="none")
    # The WhatsApp number, E.164; confirmed by a code before it receives sign-in codes.
    phone: Mapped[str | None] = mapped_column(Text)
    phone_verified_at: Mapped[datetime | None]


# After the class, the expression needs Account.id. Kept through a flush, which would leave it to a lazy load async
# cannot do; a new account starts without one.
Account.has_passkey = column_property(exists().where(Passkey.account_id == Account.id), expire_on_flush=False)


@event.listens_for(Account, "init")
def _starts_without_passkey(target: Account, args: Any, kwargs: Any) -> None:
    target.has_passkey = False  # type: ignore[attr-defined]
