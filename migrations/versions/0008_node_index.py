"""the search index of a file or a page, one row per node, the previous one readable while the next builds

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-23 18:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "node_index",
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("version_key", sa.Text(), nullable=False),
        sa.Column("building_key", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("outline", sa.Text(), server_default="", nullable=False),
        sa.Column("parsed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('building', 'ready', 'failed')", name=op.f("ck_node_index_status")),
        sa.ForeignKeyConstraint(
            ["node_id"], ["acervo.node.id"], name=op.f("fk_node_index_node_id_node"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("node_id", name=op.f("pk_node_index")),
        schema="acervo",
    )


def downgrade() -> None:
    op.drop_table("node_index", schema="acervo")
