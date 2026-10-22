from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class Node(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "node"
    __table_args__ = (
        CheckConstraint("kind in ('folder', 'page', 'file')", name="kind"),
        Index(
            "uq_node_live_sibling_title",
            "kb_id",
            "parent_id",
            "kind",
            text("lower(title)"),
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("deleted_at is null"),
        ),
        # The person's name filter only (rule 2 of CLAUDE.md): agents never search by title.
        Index(
            "ix_node_title_trgm",
            text("acervo.immutable_unaccent(lower(title)) gin_trgm_ops"),
            postgresql_using="gin",
        ),
    )

    kb_id: Mapped[UUID] = mapped_column(ForeignKey("kb.id"), index=True)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("node.id"), index=True)
    kind: Mapped[str] = mapped_column(Text)
    # A file's title keeps its extension; a page's does not.
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="", default="")
    description_locked: Mapped[bool] = mapped_column(server_default="false", default=False)
    # Fractional index, so moving one item rewrites one row.
    sort: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None]
    # The node whose trashing hid this one; restore unmarks every node carrying that id.
    trashed_with: Mapped[UUID | None] = mapped_column(ForeignKey("node.id"), index=True)
