"""page_version.author_known: tells a version saved before authors were kept from one whose author was deleted

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-26 18:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "page_version",
        sa.Column("author_known", sa.Boolean(), server_default=sa.true(), nullable=False),
        schema="acervo",
    )
    # A version with no author yet may predate 0013 or have lost it; neither can be told now, so it shows none.
    op.execute("update acervo.page_version set author_known = author_id is not null")


def downgrade() -> None:
    op.drop_column("page_version", "author_known", schema="acervo")
