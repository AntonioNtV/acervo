"""notifications: email toggles and time zone on account, page_follow, page_version.author_id, email_copy

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-26 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def _fk(table: str, column: str, target: str, ondelete: str = "CASCADE") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"acervo.{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete=ondelete
    )


def upgrade() -> None:
    op.add_column(
        "account", sa.Column("notify_invites", sa.Boolean(), server_default=sa.true(), nullable=False), schema="acervo"
    )
    op.add_column(
        "account",
        sa.Column("notify_followed", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema="acervo",
    )
    op.add_column(
        "account",
        sa.Column("timezone", sa.Text(), server_default="America/Sao_Paulo", nullable=False),
        schema="acervo",
    )
    op.add_column("account", sa.Column("digest_sent_on", sa.Date(), nullable=True), schema="acervo")

    # Versions saved before this migration keep no author.
    op.add_column("page_version", sa.Column("author_id", sa.Uuid(), nullable=True), schema="acervo")
    op.create_foreign_key(
        op.f("fk_page_version_author_id_account"),
        "page_version",
        "account",
        ["author_id"],
        ["id"],
        source_schema="acervo",
        referent_schema="acervo",
        ondelete="SET NULL",
    )

    op.create_table(
        "page_follow",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        _fk("page_follow", "account_id", "account"),
        _fk("page_follow", "node_id", "node"),
        sa.PrimaryKeyConstraint("account_id", "node_id", name=op.f("pk_page_follow")),
        schema="acervo",
    )
    op.create_index(op.f("ix_page_follow_node_id"), "page_follow", ["node_id"], unique=False, schema="acervo")
    # As favorite (0009): a follow is seen only with its node, so the policy of the node's base holds.
    op.execute("alter table acervo.page_follow enable row level security")
    op.execute("alter table acervo.page_follow force row level security")
    op.execute(
        "create policy visible on acervo.page_follow using (node_id in (select id from acervo.node)) "
        "with check (node_id in (select id from acervo.node))"
    )

    # Not a base's: no row-level security; 0009's default privileges grant it to acervo_app.
    op.create_table(
        "email_copy",
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("copy", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        _fk("email_copy", "updated_by", "account", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("template", "language", name=op.f("pk_email_copy")),
        schema="acervo",
    )


def downgrade() -> None:
    op.drop_table("email_copy", schema="acervo")
    op.drop_table("page_follow", schema="acervo")
    op.drop_constraint(op.f("fk_page_version_author_id_account"), "page_version", schema="acervo", type_="foreignkey")
    op.drop_column("page_version", "author_id", schema="acervo")
    for column in ("digest_sent_on", "timezone", "notify_followed", "notify_invites"):
        op.drop_column("account", column, schema="acervo")
