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


def upgrade() -> None:
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
    op.drop_column("page_version", "edit_ended_at", schema="acervo")
    op.drop_column("page_version", "edit_started_at", schema="acervo")
    op.drop_column("page_draft", "started_at", schema="acervo")
    op.drop_column("page_draft", "revision", schema="acervo")
