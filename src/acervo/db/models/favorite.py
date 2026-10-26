from uuid import UUID

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Favorite(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "favorite"
    __table_args__ = (UniqueConstraint("account_id", "node_id"),)

    account_id: Mapped[UUID] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    node_id: Mapped[UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"), index=True)
    # Fractional index, compared with collate "C" as `node.favorite_sort` is.
    sort: Mapped[str] = mapped_column(Text)
