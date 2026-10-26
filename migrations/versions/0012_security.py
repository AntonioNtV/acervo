"""security: passkey, pending_sign_in and security_event; two-step verification on account and organization

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-27 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def _id_and_timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _fk(table: str, column: str, target: str, ondelete: str = "CASCADE") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"acervo.{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete=ondelete
    )


def _replace_purposes(*purposes: str) -> None:
    listed = ", ".join(f"'{purpose}'" for purpose in purposes)
    op.drop_constraint(op.f("ck_email_code_purpose"), "email_code", schema="acervo", type_="check")
    op.create_check_constraint(op.f("ck_email_code_purpose"), "email_code", f"purpose in ({listed})", schema="acervo")


def upgrade() -> None:
    # New tables hang off the account, not a base: like session, no row-level security; 0009's default
    # privileges already grant them to acervo_app.
    op.create_table(
        "passkey",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("transports", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aaguid", sa.Text(), nullable=False),
        *_id_and_timestamps(),
        _fk("passkey", "account_id", "account"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_passkey")),
        sa.UniqueConstraint("credential_id", name=op.f("uq_passkey_credential_id")),
        schema="acervo",
    )
    op.create_index(op.f("ix_passkey_account_id"), "passkey", ["account_id"], unique=False, schema="acervo")
    op.create_table(
        "pending_sign_in",
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("code_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        *_id_and_timestamps(),
        sa.CheckConstraint("method in ('email', 'whatsapp')", name=op.f("ck_pending_sign_in_method")),
        _fk("pending_sign_in", "account_id", "account"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pending_sign_in")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_pending_sign_in_token_hash")),
        schema="acervo",
    )
    op.create_index(
        op.f("ix_pending_sign_in_account_id"), "pending_sign_in", ["account_id"], unique=False, schema="acervo"
    )
    op.create_table(
        "security_event",
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        *_id_and_timestamps(),
        _fk("security_event", "account_id", "account"),
        _fk("security_event", "organization_id", "organization"),
        _fk("security_event", "actor_id", "account", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_event")),
        schema="acervo",
    )
    for column in ("account_id", "organization_id"):
        op.create_index(
            op.f(f"ix_security_event_{column}_created_at"),
            "security_event",
            [column, "created_at"],
            unique=False,
            schema="acervo",
        )

    op.add_column("account", sa.Column("two_factor", sa.Text(), server_default="none", nullable=False), schema="acervo")
    op.add_column("account", sa.Column("phone", sa.Text(), nullable=True), schema="acervo")
    op.add_column("account", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True), schema="acervo")
    op.create_check_constraint(
        op.f("ck_account_two_factor"), "account", "two_factor in ('none', 'email', 'whatsapp')", schema="acervo"
    )
    # Turning two-step verification on confirms the email or the number with a code (`target_email` holds either).
    _replace_purposes("verify_email", "change_email", "two_factor")
    op.add_column(
        "session", sa.Column("reauthenticated_at", sa.DateTime(timezone=True), nullable=True), schema="acervo"
    )
    # Sessions open before this migration count as password ones.
    op.add_column("session", sa.Column("method", sa.Text(), server_default="password", nullable=False), schema="acervo")
    op.create_check_constraint(
        op.f("ck_session_method"), "session", "method in ('password', 'google', 'passkey', 'reset')", schema="acervo"
    )
    op.add_column(
        "organization",
        sa.Column("require_two_factor", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema="acervo",
    )


def downgrade() -> None:
    op.drop_column("organization", "require_two_factor", schema="acervo")
    op.execute("delete from acervo.email_code where purpose = 'two_factor'")
    _replace_purposes("verify_email", "change_email")
    op.drop_constraint(op.f("ck_session_method"), "session", schema="acervo", type_="check")
    for column in ("method", "reauthenticated_at"):
        op.drop_column("session", column, schema="acervo")
    op.drop_constraint(op.f("ck_account_two_factor"), "account", schema="acervo", type_="check")
    for column in ("phone_verified_at", "phone", "two_factor"):
        op.drop_column("account", column, schema="acervo")
    for table in ("security_event", "pending_sign_in", "passkey"):
        op.drop_table(table, schema="acervo")
