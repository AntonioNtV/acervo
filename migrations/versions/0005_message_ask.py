"""a reply that asks first keeps the two readings the person picks between

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22 23:40:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("message", sa.Column("ask", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="acervo")


def downgrade() -> None:
    op.drop_column("message", "ask", schema="acervo")
