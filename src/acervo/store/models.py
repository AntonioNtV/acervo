import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    MetaData,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema="acervo", naming_convention=NAMING_CONVENTION)
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


class TableModel:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Kb(Base, TableModel):
    __tablename__ = "kb"

    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="", default="")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Node(Base, TableModel):
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

    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kb.id"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("node.id"), index=True)
    kind: Mapped[str] = mapped_column(Text)
    # A file's title keeps its extension; a page's does not.
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="", default="")
    description_locked: Mapped[bool] = mapped_column(server_default="false", default=False)
    # Fractional index, so moving one item rewrites one row.
    sort: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The node whose trashing hid this one; restore unmarks every node carrying that id.
    trashed_with: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("node.id"), index=True)


class PageVersion(Base, TableModel):
    __tablename__ = "page_version"
    __table_args__ = (CheckConstraint("author in ('user', 'agent')", name="author"),)

    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id"), index=True)
    markdown: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(Text)
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proposal.id"))


class PageDraft(Base, TableModel):
    __tablename__ = "page_draft"

    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id"), unique=True)
    markdown: Mapped[str] = mapped_column(Text)
    base_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("page_version.id"))


class PageLink(Base, TableModel):
    __tablename__ = "page_link"
    __table_args__ = (Index("ix_page_link_kb_id_target", "kb_id", "target"),)

    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kb.id"))
    from_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id"), index=True)
    # The normalized title inside `[[…]]`.
    target: Mapped[str] = mapped_column(Text)


class FileColumns:
    """What is known about one stored file. Metadata only: never its text (rule 1 of CLAUDE.md)."""

    storage_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text, index=True)
    size: Mapped[int] = mapped_column(BigInteger)
    mime: Mapped[str] = mapped_column(Text)
    pages: Mapped[int | None]
    protected: Mapped[bool] = mapped_column(server_default="false", default=False)
    doc_type: Mapped[str | None] = mapped_column(Text)
    sensitive: Mapped[bool] = mapped_column(server_default="false", default=False)
    map: Mapped[dict[str, Any] | None]
    map_origin: Mapped[str | None] = mapped_column(Text)


class File(Base, TableModel, FileColumns):
    __tablename__ = "file"
    __table_args__ = (CheckConstraint("map_origin in ('bookmarks', 'toc', 'generated')", name="map_origin"),)

    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id"), unique=True)


class FileVersion(Base, TableModel, FileColumns):
    __tablename__ = "file_version"
    __table_args__ = (CheckConstraint("map_origin in ('bookmarks', 'toc', 'generated')", name="map_origin"),)

    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id"), index=True)
    replaced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Proposal(Base, TableModel):
    __tablename__ = "proposal"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'editing', 'accepted', 'applied', 'rejected', 'stale')",
            name="status",
        ),
        CheckConstraint(
            "reject_reason in ('wrong_place', 'already_there', 'wrong_info', 'not_worth_keeping')",
            name="reject_reason",
        ),
    )

    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]]
    edited_payload: Mapped[dict[str, Any] | None]
    alternatives: Mapped[list[Any] | None]
    status: Mapped[str] = mapped_column(Text, server_default="pending", default="pending")
    reject_reason: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    base_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("page_version.id", use_alter=True))


class DecisionLog(Base, TableModel):
    __tablename__ = "decision_log"

    run_id: Mapped[uuid.UUID] = mapped_column(index=True)
    step: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(Text)
    options: Mapped[list[Any]]
    probs: Mapped[list[Any]]
    threshold: Mapped[float | None] = mapped_column(Float)
    action: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int]
    cached: Mapped[bool] = mapped_column(server_default="false", default=False)
