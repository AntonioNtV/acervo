"""page working text: the draft gets a revision and its session start; versions get their editing span

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22 15:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _save_drafts_as_versions(created_at: str) -> None:
    """Every draft that differs from its page's newest version becomes a version by the person, then no draft is
    left: the other side of the migration reads drafts differently, and nothing typed may be lost."""
    op.execute(
        f"""
        insert into acervo.page_version (node_id, markdown, author, created_at, updated_at)
        select d.node_id, d.markdown, 'user', {created_at}, {created_at}
        from acervo.page_draft d
        where d.markdown is distinct from (
            select v.markdown from acervo.page_version v
            where v.node_id = d.node_id order by v.created_at desc limit 1
        )
        """
    )
    op.execute("delete from acervo.page_draft")


def upgrade() -> None:
    # Dated when it was typed: a version written after it, such as a link fix, stays the newest.
    _save_drafts_as_versions("d.updated_at")
    op.drop_constraint(
        op.f("fk_page_draft_base_version_id_page_version"), "page_draft", schema="acervo", type_="foreignkey"
    )
    op.drop_column("page_draft", "base_version_id", schema="acervo")
    op.add_column(
        "page_draft", sa.Column("revision", sa.Integer(), server_default="0", nullable=False), schema="acervo"
    )
    op.add_column(
        "page_draft",
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema="acervo",
    )
    op.add_column("page_version", sa.Column("edit_started_at", sa.DateTime(timezone=True)), schema="acervo")
    op.add_column("page_version", sa.Column("edit_ended_at", sa.DateTime(timezone=True)), schema="acervo")


def downgrade() -> None:
    _save_drafts_as_versions("now()")
    op.drop_column("page_version", "edit_ended_at", schema="acervo")
    op.drop_column("page_version", "edit_started_at", schema="acervo")
    op.drop_column("page_draft", "started_at", schema="acervo")
    op.drop_column("page_draft", "revision", schema="acervo")
    op.add_column("page_draft", sa.Column("base_version_id", sa.Uuid()), schema="acervo")
    op.execute(
        """
        update acervo.page_draft d set base_version_id = (
            select v.id from acervo.page_version v where v.node_id = d.node_id order by v.created_at desc limit 1
        )
        """
    )
    op.alter_column("page_draft", "base_version_id", nullable=False, schema="acervo")
    op.create_foreign_key(
        op.f("fk_page_draft_base_version_id_page_version"),
        "page_draft",
        "page_version",
        ["base_version_id"],
        ["id"],
        source_schema="acervo",
        referent_schema="acervo",
    )
