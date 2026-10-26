from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, false, text
from sqlalchemy.orm import Mapped, mapped_column, query_expression

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
        # The name filter of the tree and of search.
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
    # Fractional index, so moving one item rewrites one row.
    sort: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None]
    # The node whose trashing hid this one; restore unmarks every node carrying that id.
    trashed_with: Mapped[UUID | None] = mapped_column(ForeignKey("node.id"), index=True)
    icon: Mapped[str | None] = mapped_column(Text)
    # `gallery:<slug>` or `image:<sha256>`; folders and pages only.
    cover: Mapped[str | None] = mapped_column(Text)
    # Whether the request's account has it among its favorites: NodeRepository fills it for that account.
    favorite: Mapped[bool] = query_expression(default_expr=false(), expire_on_flush=False)
