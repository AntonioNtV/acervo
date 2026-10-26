"""page_draft.author_id: who typed the working text, so the version it is cut into is theirs

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-26 20:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("page_draft", sa.Column("author_id", sa.Uuid(), nullable=True), schema="acervo")
    op.create_foreign_key(
        op.f("fk_page_draft_author_id_account"),
        "page_draft",
        "account",
        ["author_id"],
        ["id"],
        source_schema="acervo",
        referent_schema="acervo",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_page_draft_author_id_account"), "page_draft", schema="acervo", type_="foreignkey")
    op.drop_column("page_draft", "author_id", schema="acervo")
