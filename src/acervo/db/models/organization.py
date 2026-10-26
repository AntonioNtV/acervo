from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Organization(UUIDPkMixin, TimestampMixin, Base):
    """A team, or the Pessoal of one account (`personal_of`)."""

    __tablename__ = "organization"
    __table_args__ = (CheckConstraint("new_base_access in ('none', 'reader', 'editor')", name="new_base_access"),)

    name: Mapped[str] = mapped_column(Text)
    logo_key: Mapped[str | None] = mapped_column(Text)
    personal_of: Mapped[UUID | None] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), unique=True)
    # The general access a new base of the organization starts with.
    new_base_access: Mapped[str] = mapped_column(Text, server_default="editor")
    # Members without a passkey or two-step verification cannot reach its bases until they set one.
    require_two_factor: Mapped[bool] = mapped_column(server_default=false(), default=False)
