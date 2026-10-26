"""kb policy for a guest Admin, and visible_kb_ids from the account's own rows

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-26 23:00:00.000000
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

IN_MY_ORGANIZATION = (
    "organization_id in (select organization_id from acervo.membership where account_id = acervo.current_account_id())"
)


def _kb_policy(check: str) -> None:
    op.execute("drop policy visible on acervo.kb")
    op.execute(
        f"create policy visible on acervo.kb using (acervo.sees_kb(id, organization_id, general_access)) "
        f"with check ({check})"
    )


def upgrade() -> None:
    # A guest Admin is outside the organization, yet renames, trashes and restores the base: an update must pass.
    op.execute(
        """
        create function acervo.admins_kb(kb_id uuid) returns boolean language sql stable
        as $$
            select exists (
                select from acervo.base_member b
                where b.kb_id = admins_kb.kb_id and b.account_id = acervo.current_account_id() and b.role = 'admin'
            )
        $$
        """
    )
    _kb_policy(f"{IN_MY_ORGANIZATION} or acervo.admins_kb(id)")
    # Starts from the account's rows through their indexes, instead of judging every base.
    op.execute(
        """
        create or replace function acervo.visible_kb_ids() returns setof uuid language sql stable security definer
        set search_path = pg_catalog, pg_temp
        as $$
            select b.kb_id from acervo.base_member b where b.account_id = acervo.current_account_id()
            union
            select k.id from acervo.membership m join acervo.kb k on k.organization_id = m.organization_id
            where m.account_id = acervo.current_account_id()
                and (m.role in ('owner', 'admin') or k.general_access <> 'none')
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        create or replace function acervo.visible_kb_ids() returns setof uuid language sql stable security definer
        set search_path = pg_catalog, pg_temp
        as $$ select id from acervo.kb where acervo.sees_kb(id, organization_id, general_access) $$
        """
    )
    _kb_policy(IN_MY_ORGANIZATION)
    op.execute("drop function acervo.admins_kb(uuid)")
