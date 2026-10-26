"""drop node.favorite_sort: favorites are per account, in the favorite table

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-26 14:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("node", "favorite_sort", schema="acervo")


def downgrade() -> None:
    op.add_column("node", sa.Column("favorite_sort", sa.Text()), schema="acervo")
