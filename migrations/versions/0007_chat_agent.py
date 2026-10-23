"""the chat is an agent: a reply keeps its citations and whether it used the base, no routing is stored; a
conversation can be deleted

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-23 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_message_understood_as"), "message", schema="acervo", type_="check")
    op.drop_column("message", "understood_as", schema="acervo")
    op.drop_column("message", "ask", schema="acervo")
    op.add_column(
        "message",
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        schema="acervo",
    )
    op.add_column(
        "message", sa.Column("grounded", sa.Boolean(), server_default="false", nullable=False), schema="acervo"
    )
    op.add_column("conversation", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), schema="acervo")


def downgrade() -> None:
    op.drop_column("conversation", "deleted_at", schema="acervo")
    op.drop_column("message", "grounded", schema="acervo")
    op.drop_column("message", "citations", schema="acervo")
    op.add_column("message", sa.Column("ask", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="acervo")
    op.add_column("message", sa.Column("understood_as", sa.Text(), nullable=True), schema="acervo")
    op.create_check_constraint(
        op.f("ck_message_understood_as"),
        "message",
        "understood_as in ('perguntar', 'guardar', 'organizar', 'conversar')",
        schema="acervo",
    )
