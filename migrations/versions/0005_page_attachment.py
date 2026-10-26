"""page_attachment: files put in a page, outside the tree

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-25 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_attachment",
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["page_id"], ["acervo.node.id"], name=op.f("fk_page_attachment_page_id_node"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_attachment")),
        sa.UniqueConstraint("page_id", "name", name=op.f("uq_page_attachment_page_id_name")),
        schema="acervo",
    )


def downgrade() -> None:
    op.drop_table("page_attachment", schema="acervo")
