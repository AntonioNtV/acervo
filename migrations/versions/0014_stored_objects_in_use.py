"""shas_in_use: which cover and attachment hashes any base still references

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-26 12:00:00.000000
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Security definer: covers and attachments are stored by content alone, so a base the deleting account cannot
    # see may share the bytes; deleting an organization keeps every object one of those still uses.
    op.execute(
        """
        create function acervo.shas_in_use(shas text[]) returns setof text language sql stable security definer
        set search_path = pg_catalog, pg_temp
        as $$
            select a.sha256 from acervo.page_attachment a where a.sha256 = any(shas)
            union
            select substr(n.cover, 7) from acervo.node n where n.cover = any(select 'image:' || s from unnest(shas) s)
        $$
        """
    )


def downgrade() -> None:
    op.execute("drop function acervo.shas_in_use(text[])")
