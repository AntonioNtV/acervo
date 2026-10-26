"""row-level security: the role acervo_app sees and writes only the bases its account can see

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-26 20:00:00.000000
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

ROLE = "acervo_app"
# Tables whose rows follow a node, with the column that names it.
UNDER_NODE = {
    "file": "node_id",
    "file_version": "node_id",
    "page_version": "node_id",
    "page_draft": "node_id",
    "page_attachment": "page_id",
    "favorite": "node_id",
}
VISIBLE = "(select acervo.visible_kb_ids())"


def _protect(table: str, using: str, check: str | None = None) -> None:
    op.execute(f"alter table acervo.{table} enable row level security")
    op.execute(f"alter table acervo.{table} force row level security")
    op.execute(f"create policy visible on acervo.{table} using ({using}) with check ({check or using})")


def upgrade() -> None:
    # A role belongs to the server, not to the database: other databases there (other worktrees) may have it.
    op.execute(
        f"""
        do $$
        begin
            create role {ROLE} nologin nobypassrls;
        exception when duplicate_object or unique_violation then null;
        end $$
        """
    )
    op.execute(f"grant usage on schema acervo to {ROLE}")
    op.execute(f"grant select, insert, update, delete on all tables in schema acervo to {ROLE}")
    op.execute(f"revoke all on acervo.alembic_version from {ROLE}")
    op.execute(f"grant usage, select on all sequences in schema acervo to {ROLE}")
    op.execute(f"alter default privileges in schema acervo grant select, insert, update, delete on tables to {ROLE}")
    op.execute(f"alter default privileges in schema acervo grant usage, select on sequences to {ROLE}")

    op.execute(
        """
        create function acervo.current_account_id() returns uuid language sql stable
        as $$ select nullif(current_setting('app.account_id', true), '')::uuid $$
        """
    )
    # The rule of AccessService.base_role, on a base's own columns: a policy must judge a row being inserted too.
    op.execute(
        """
        create function acervo.sees_kb(kb_id uuid, organization_id uuid, general_access text) returns boolean
        language sql stable
        as $$
            select exists (
                select from acervo.base_member b
                where b.kb_id = sees_kb.kb_id and b.account_id = acervo.current_account_id()
            ) or exists (
                select from acervo.membership m
                where m.organization_id = sees_kb.organization_id and m.account_id = acervo.current_account_id()
                    and (m.role in ('owner', 'admin') or sees_kb.general_access <> 'none')
            )
        $$
        """
    )
    # Security definer: it reads kb past the policy of the table that calls it.
    op.execute(
        """
        create function acervo.visible_kb_ids() returns setof uuid language sql stable security definer
        set search_path = pg_catalog, pg_temp
        as $$ select id from acervo.kb where acervo.sees_kb(id, organization_id, general_access) $$
        """
    )
    # Creating a base asks only membership of its organization; card 05 then adds what makes it visible.
    _protect(
        "kb",
        "acervo.sees_kb(id, organization_id, general_access)",
        "organization_id in "
        "(select organization_id from acervo.membership where account_id = acervo.current_account_id())",
    )
    for table in ("node", "page_link"):
        _protect(table, f"kb_id in {VISIBLE}")
    for table, column in UNDER_NODE.items():
        _protect(table, f"{column} in (select id from acervo.node)")


def downgrade() -> None:
    for table in ("kb", "node", "page_link", *UNDER_NODE):
        op.execute(f"drop policy visible on acervo.{table}")
        op.execute(f"alter table acervo.{table} no force row level security")
        op.execute(f"alter table acervo.{table} disable row level security")
    op.execute("drop function acervo.visible_kb_ids()")
    op.execute("drop function acervo.sees_kb(uuid, uuid, text)")
    op.execute("drop function acervo.current_account_id()")
    # Revokes this database's grants and default privileges; the role goes once no other database uses it.
    op.execute(f"drop owned by {ROLE}")
    op.execute(
        f"""
        do $$
        begin
            drop role {ROLE};
        exception when dependent_objects_still_exist then null;
        end $$
        """
    )
