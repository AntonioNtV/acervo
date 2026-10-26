from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class LoginFailure(UUIDPkMixin, TimestampMixin, Base):
    """A wrong password for an email, counted for the lockout whether or not the account exists."""

    __tablename__ = "login_failure"
    __table_args__ = (Index(None, "email_lower", "created_at"),)

    email_lower: Mapped[str] = mapped_column(Text)
