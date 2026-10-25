"""without AI: no proposal or decision_log tables, no author or proposal on a page version, no locked description,
no classification or section map on a file

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-25 10:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("fk_page_version_proposal_id_proposal"), "page_version", schema="acervo", type_="foreignkey"
    )
    op.drop_column("page_version", "proposal_id", schema="acervo")
    op.drop_constraint(op.f("ck_page_version_author"), "page_version", schema="acervo", type_="check")
    op.drop_column("page_version", "author", schema="acervo")
    op.drop_column("node", "description_locked", schema="acervo")
    for table in ("file", "file_version"):
        op.drop_constraint(op.f(f"ck_{table}_map_origin"), table, schema="acervo", type_="check")
        for column in ("doc_type", "sensitive", "map", "map_origin"):
            op.drop_column(table, column, schema="acervo")
    op.drop_index(op.f("ix_proposal_run_id"), table_name="proposal", schema="acervo")
    op.drop_table("proposal", schema="acervo")
    op.drop_index(op.f("ix_decision_log_run_id"), table_name="decision_log", schema="acervo")
    op.drop_table("decision_log", schema="acervo")


def downgrade() -> None:
    for table in ("file", "file_version"):
        op.add_column(table, sa.Column("doc_type", sa.Text(), nullable=True), schema="acervo")
        op.add_column(
            table, sa.Column("sensitive", sa.Boolean(), server_default="false", nullable=False), schema="acervo"
        )
        op.add_column(table, sa.Column("map", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="acervo")
        op.add_column(table, sa.Column("map_origin", sa.Text(), nullable=True), schema="acervo")
        op.create_check_constraint(
            op.f(f"ck_{table}_map_origin"), table, "map_origin in ('bookmarks', 'toc', 'generated')", schema="acervo"
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
        sa.ForeignKeyConstraint(
            ["base_version_id"], ["acervo.page_version.id"], name=op.f("fk_proposal_base_version_id_page_version")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposal")),
        schema="acervo",
    )
    op.create_index(op.f("ix_proposal_run_id"), "proposal", ["run_id"], unique=False, schema="acervo")
    op.add_column(
        "node",
        sa.Column("description_locked", sa.Boolean(), server_default="false", nullable=False),
        schema="acervo",
    )
    # Every version left was written by a person.
    op.add_column(
        "page_version", sa.Column("author", sa.Text(), server_default="user", nullable=False), schema="acervo"
    )
    op.alter_column("page_version", "author", server_default=None, schema="acervo")
    op.create_check_constraint(
        op.f("ck_page_version_author"), "page_version", "author in ('user', 'agent')", schema="acervo"
    )
    op.add_column("page_version", sa.Column("proposal_id", sa.Uuid(), nullable=True), schema="acervo")
    op.create_foreign_key(
        op.f("fk_page_version_proposal_id_proposal"),
        "page_version",
        "proposal",
        ["proposal_id"],
        ["id"],
        source_schema="acervo",
        referent_schema="acervo",
    )
