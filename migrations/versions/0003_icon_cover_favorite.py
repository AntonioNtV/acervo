"""icon, cover and favorite order of nodes; icon of bases

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22 18:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("node", sa.Column("icon", sa.Text()), schema="acervo")
    op.add_column("node", sa.Column("cover", sa.Text()), schema="acervo")
    op.add_column("node", sa.Column("favorite_sort", sa.Text()), schema="acervo")
    op.add_column("kb", sa.Column("icon", sa.Text()), schema="acervo")


def downgrade() -> None:
    op.drop_column("kb", "icon", schema="acervo")
    op.drop_column("node", "favorite_sort", schema="acervo")
    op.drop_column("node", "cover", schema="acervo")
    op.drop_column("node", "icon", schema="acervo")
