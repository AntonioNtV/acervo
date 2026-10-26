"""organizations: organization, membership, base_member, invite; every base belongs to an organization

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-26 18:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _id_and_timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"acervo.{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete="CASCADE"
    )


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("logo_key", sa.Text(), nullable=True),
        sa.Column("personal_of", sa.Uuid(), nullable=True),
        sa.Column("new_base_access", sa.Text(), server_default="editor", nullable=False),
        *_id_and_timestamps(),
        sa.CheckConstraint(
            "new_base_access in ('none', 'reader', 'editor')", name=op.f("ck_organization_new_base_access")
        ),
        _fk("organization", "personal_of", "account"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization")),
        sa.UniqueConstraint("personal_of", name=op.f("uq_organization_personal_of")),
        schema="acervo",
    )
    op.create_table(
        "membership",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        *_id_and_timestamps(),
        sa.CheckConstraint("role in ('owner', 'admin', 'member')", name=op.f("ck_membership_role")),
        _fk("membership", "organization_id", "organization"),
        _fk("membership", "account_id", "account"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership")),
        sa.UniqueConstraint("organization_id", "account_id", name=op.f("uq_membership_organization_id_account_id")),
        schema="acervo",
    )
    op.create_index(op.f("ix_membership_account_id"), "membership", ["account_id"], unique=False, schema="acervo")

    op.add_column("kb", sa.Column("organization_id", sa.Uuid(), nullable=True), schema="acervo")
    op.add_column(
        "kb", sa.Column("general_access", sa.Text(), server_default="editor", nullable=False), schema="acervo"
    )
    op.create_check_constraint(
        op.f("ck_kb_general_access"), "kb", "general_access in ('none', 'reader', 'editor')", schema="acervo"
    )
    # Every account gets its Pessoal; the bases there were go to the oldest account's, closed to everyone else.
    op.execute("insert into acervo.organization (name, personal_of) select 'Pessoal', id from acervo.account")
    op.execute(
        "insert into acervo.membership (organization_id, account_id, role) "
        "select id, personal_of, 'owner' from acervo.organization"
    )
    op.execute(
        """
        do $$
        begin
            if exists (select from acervo.kb) and not exists (select from acervo.account) then
                raise exception 'acervo.kb has bases and acervo.account has no account to own them: '
                    'create an account first, then run this migration again';
            end if;
        end $$
        """
    )
    op.execute(
        """
        update acervo.kb set general_access = 'none', organization_id = (
            select o.id from acervo.organization o join acervo.account a on a.id = o.personal_of
            order by a.created_at, a.id limit 1
        )
        """
    )
    op.alter_column("kb", "organization_id", nullable=False, schema="acervo")
    op.create_foreign_key(
        op.f("fk_kb_organization_id_organization"),
        "kb",
        "organization",
        ["organization_id"],
        ["id"],
        source_schema="acervo",
        referent_schema="acervo",
    )
    op.create_index(op.f("ix_kb_organization_id"), "kb", ["organization_id"], unique=False, schema="acervo")

    op.create_table(
        "base_member",
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        *_id_and_timestamps(),
        sa.CheckConstraint("role in ('reader', 'editor', 'admin')", name=op.f("ck_base_member_role")),
        _fk("base_member", "kb_id", "kb"),
        _fk("base_member", "account_id", "account"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_base_member")),
        sa.UniqueConstraint("kb_id", "account_id", name=op.f("uq_base_member_kb_id_account_id")),
        schema="acervo",
    )
    op.create_index(op.f("ix_base_member_account_id"), "base_member", ["account_id"], unique=False, schema="acervo")
    op.create_table(
        "invite",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("invited_by", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_id_and_timestamps(),
        sa.CheckConstraint("role in ('owner', 'admin', 'member', 'reader', 'editor')", name=op.f("ck_invite_role")),
        _fk("invite", "organization_id", "organization"),
        _fk("invite", "kb_id", "kb"),
        _fk("invite", "invited_by", "account"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invite")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invite_token_hash")),
        schema="acervo",
    )
    op.create_index(op.f("ix_invite_organization_id"), "invite", ["organization_id"], unique=False, schema="acervo")
    op.create_index(op.f("ix_invite_kb_id"), "invite", ["kb_id"], unique=False, schema="acervo")


def downgrade() -> None:
    for table in ("invite", "base_member"):
        op.drop_table(table, schema="acervo")
    op.drop_index(op.f("ix_kb_organization_id"), table_name="kb", schema="acervo")
    op.drop_constraint(op.f("fk_kb_organization_id_organization"), "kb", schema="acervo", type_="foreignkey")
    op.drop_constraint(op.f("ck_kb_general_access"), "kb", schema="acervo", type_="check")
    op.drop_column("kb", "general_access", schema="acervo")
    op.drop_column("kb", "organization_id", schema="acervo")
    for table in ("membership", "organization"):
        op.drop_table(table, schema="acervo")
