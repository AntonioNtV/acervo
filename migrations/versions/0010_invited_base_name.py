"""invited base name: whoever holds a base invite's link reads that base's name before signing in

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-26 22:00:00.000000
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Security definer: the Convite screen runs for no account, and row-level security hides every base from it.
    # The token's hash is the key, so it gives one name and only to a holder of the link.
    op.execute(
        """
        create function acervo.invited_base_name(token_hash text) returns text
        language sql stable security definer
        set search_path = pg_catalog, pg_temp
        as $$
            select k.name from acervo.invite i join acervo.kb k on k.id = i.kb_id
            where i.token_hash = invited_base_name.token_hash
        $$
        """
    )


def downgrade() -> None:
    op.execute("drop function acervo.invited_base_name(text)")
