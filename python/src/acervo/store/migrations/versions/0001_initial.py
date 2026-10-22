"""initial: every table of F1, plus proposal and decision_log for F2

Revision ID: 0001
Revises:
Create Date: 2026-10-22 10:59:44.914443
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists pg_trgm with schema public")
    op.execute("create extension if not exists unaccent with schema public")
    # unaccent() is only stable, so an index cannot call it; this wrapper pins the dictionary and is immutable.
    op.execute(
        """
        create function acervo.immutable_unaccent(text) returns text
        language sql immutable parallel safe strict
        as $$ select public.unaccent('public.unaccent'::regdictionary, $1) $$
        """
    )
    op.create_table(
        "decision_log",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("question_type", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("probs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cached", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_log")),
        schema="acervo",
    )
    op.create_index(op.f("ix_decision_log_run_id"), "decision_log", ["run_id"], unique=False, schema="acervo")
    op.create_table(
        "kb",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kb")),
        schema="acervo",
    )
    op.create_table(
        "proposal",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("edited_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("alternatives", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("base_version_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "reject_reason in ('wrong_place', 'already_there', 'wrong_info', 'not_worth_keeping')",
            name=op.f("ck_proposal_reject_reason"),
        ),
        sa.CheckConstraint(
            "status in ('pending', 'editing', 'accepted', 'applied', 'rejected', 'stale')",
            name=op.f("ck_proposal_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposal")),
        schema="acervo",
    )
    op.create_index(op.f("ix_proposal_run_id"), "proposal", ["run_id"], unique=False, schema="acervo")
    op.create_table(
        "node",
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("description_locked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sort", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trashed_with", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind in ('folder', 'page', 'file')", name=op.f("ck_node_kind")),
        sa.ForeignKeyConstraint(["kb_id"], ["acervo.kb.id"], name=op.f("fk_node_kb_id_kb")),
        sa.ForeignKeyConstraint(["parent_id"], ["acervo.node.id"], name=op.f("fk_node_parent_id_node")),
        sa.ForeignKeyConstraint(["trashed_with"], ["acervo.node.id"], name=op.f("fk_node_trashed_with_node")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_node")),
        schema="acervo",
    )
    op.create_index(op.f("ix_node_kb_id"), "node", ["kb_id"], unique=False, schema="acervo")
    op.create_index(op.f("ix_node_parent_id"), "node", ["parent_id"], unique=False, schema="acervo")
    op.create_index(
        "ix_node_title_trgm",
        "node",
        [sa.literal_column("acervo.immutable_unaccent(lower(title)) gin_trgm_ops")],
        unique=False,
        schema="acervo",
        postgresql_using="gin",
    )
    op.create_index(op.f("ix_node_trashed_with"), "node", ["trashed_with"], unique=False, schema="acervo")
    op.create_index(
        "uq_node_live_sibling_title",
        "node",
        ["kb_id", "parent_id", "kind", sa.literal_column("lower(title)")],
        unique=True,
        schema="acervo",
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("deleted_at is null"),
    )
    op.create_table(
        "file",
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.Column("protected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("doc_type", sa.Text(), nullable=True),
        sa.Column("sensitive", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("map", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("map_origin", sa.Text(), nullable=True),
        sa.CheckConstraint("map_origin in ('bookmarks', 'toc', 'generated')", name=op.f("ck_file_map_origin")),
        sa.ForeignKeyConstraint(["node_id"], ["acervo.node.id"], name=op.f("fk_file_node_id_node")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file")),
        sa.UniqueConstraint("node_id", name=op.f("uq_file_node_id")),
        schema="acervo",
    )
    op.create_index(op.f("ix_file_sha256"), "file", ["sha256"], unique=False, schema="acervo")
    op.create_table(
        "file_version",
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.Column("protected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("doc_type", sa.Text(), nullable=True),
        sa.Column("sensitive", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("map", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("map_origin", sa.Text(), nullable=True),
        sa.CheckConstraint("map_origin in ('bookmarks', 'toc', 'generated')", name=op.f("ck_file_version_map_origin")),
        sa.ForeignKeyConstraint(["node_id"], ["acervo.node.id"], name=op.f("fk_file_version_node_id_node")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_version")),
        schema="acervo",
    )
    op.create_index(op.f("ix_file_version_node_id"), "file_version", ["node_id"], unique=False, schema="acervo")
    op.create_index(op.f("ix_file_version_sha256"), "file_version", ["sha256"], unique=False, schema="acervo")
    op.create_table(
        "page_link",
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("from_node_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["from_node_id"], ["acervo.node.id"], name=op.f("fk_page_link_from_node_id_node")),
        sa.ForeignKeyConstraint(["kb_id"], ["acervo.kb.id"], name=op.f("fk_page_link_kb_id_kb")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_link")),
        schema="acervo",
    )
    op.create_index(op.f("ix_page_link_from_node_id"), "page_link", ["from_node_id"], unique=False, schema="acervo")
    op.create_index("ix_page_link_kb_id_target", "page_link", ["kb_id", "target"], unique=False, schema="acervo")
    op.create_table(
        "page_version",
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("author in ('user', 'agent')", name=op.f("ck_page_version_author")),
        sa.ForeignKeyConstraint(["node_id"], ["acervo.node.id"], name=op.f("fk_page_version_node_id_node")),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["acervo.proposal.id"], name=op.f("fk_page_version_proposal_id_proposal")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_version")),
        schema="acervo",
    )
    op.create_index(op.f("ix_page_version_node_id"), "page_version", ["node_id"], unique=False, schema="acervo")
    # proposal and page_version point at each other; this side waits for page_version to exist.
    op.create_foreign_key(
        op.f("fk_proposal_base_version_id_page_version"),
        "proposal",
        "page_version",
        ["base_version_id"],
        ["id"],
        source_schema="acervo",
        referent_schema="acervo",
    )
    op.create_table(
        "page_draft",
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("base_version_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["base_version_id"], ["acervo.page_version.id"], name=op.f("fk_page_draft_base_version_id_page_version")
        ),
        sa.ForeignKeyConstraint(["node_id"], ["acervo.node.id"], name=op.f("fk_page_draft_node_id_node")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_draft")),
        sa.UniqueConstraint("node_id", name=op.f("uq_page_draft_node_id")),
        schema="acervo",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_proposal_base_version_id_page_version"), "proposal", schema="acervo", type_="foreignkey"
    )
    op.drop_table("page_draft", schema="acervo")
    op.drop_index(op.f("ix_page_version_node_id"), table_name="page_version", schema="acervo")
    op.drop_table("page_version", schema="acervo")
    op.drop_index("ix_page_link_kb_id_target", table_name="page_link", schema="acervo")
    op.drop_index(op.f("ix_page_link_from_node_id"), table_name="page_link", schema="acervo")
    op.drop_table("page_link", schema="acervo")
    op.drop_index(op.f("ix_file_version_sha256"), table_name="file_version", schema="acervo")
    op.drop_index(op.f("ix_file_version_node_id"), table_name="file_version", schema="acervo")
    op.drop_table("file_version", schema="acervo")
    op.drop_index(op.f("ix_file_sha256"), table_name="file", schema="acervo")
    op.drop_table("file", schema="acervo")
    op.drop_index(
        "uq_node_live_sibling_title",
        table_name="node",
        schema="acervo",
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("deleted_at is null"),
    )
    op.drop_index(op.f("ix_node_trashed_with"), table_name="node", schema="acervo")
    op.drop_index("ix_node_title_trgm", table_name="node", schema="acervo", postgresql_using="gin")
    op.drop_index(op.f("ix_node_parent_id"), table_name="node", schema="acervo")
    op.drop_index(op.f("ix_node_kb_id"), table_name="node", schema="acervo")
    op.drop_table("node", schema="acervo")
    op.drop_index(op.f("ix_proposal_run_id"), table_name="proposal", schema="acervo")
    op.drop_table("proposal", schema="acervo")
    op.drop_table("kb", schema="acervo")
    op.drop_index(op.f("ix_decision_log_run_id"), table_name="decision_log", schema="acervo")
    op.drop_table("decision_log", schema="acervo")
    op.execute("drop function acervo.immutable_unaccent(text)")
    op.execute("drop extension if exists unaccent")
    op.execute("drop extension if exists pg_trgm")
