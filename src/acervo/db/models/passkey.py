from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Passkey(UUIDPkMixin, TimestampMixin, Base):
    """A WebAuthn credential of an account; signing in with it counts as both factors."""

    __tablename__ = "passkey"

    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"), index=True)
    credential_id: Mapped[bytes] = mapped_column(unique=True)
    public_key: Mapped[bytes]
    # WebAuthn's counter is an unsigned 32-bit number.
    sign_count: Mapped[int] = mapped_column(BigInteger, server_default="0", default=0)
    transports: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}", default=list)
    name: Mapped[str] = mapped_column(Text)
    last_used_at: Mapped[datetime | None]
    aaguid: Mapped[str] = mapped_column(Text)
