"""a proposal is pending, applied, rejected or stale: editing and accepted were never used

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-23 10:00:00.000000
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_proposal_status"), "proposal", schema="acervo", type_="check")
    op.create_check_constraint(
        op.f("ck_proposal_status"), "proposal", "status in ('pending', 'applied', 'rejected', 'stale')", schema="acervo"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_proposal_status"), "proposal", schema="acervo", type_="check")
    op.create_check_constraint(
        op.f("ck_proposal_status"),
        "proposal",
        "status in ('pending', 'editing', 'accepted', 'applied', 'rejected', 'stale')",
        schema="acervo",
    )
