"""accounts: account, session, email_code, password_reset, login_failure and favorite

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-26 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _id_and_timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _account_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["account_id"], ["acervo.account.id"], name=op.f(f"fk_{table}_account_id_account"), ondelete="CASCADE"
    )


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("google_sub", sa.Text(), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("photo_key", sa.Text(), nullable=True),
        sa.Column("theme", sa.Text(), server_default="system", nullable=False),
        sa.Column("page_width", sa.Text(), server_default="default", nullable=False),
        sa.Column("language", sa.Text(), server_default="pt-BR", nullable=False),
        sa.Column("start_page", sa.Text(), server_default="last", nullable=False),
        *_id_and_timestamps(),
        sa.CheckConstraint("theme in ('light', 'dark', 'system')", name=op.f("ck_account_theme")),
        sa.CheckConstraint("page_width in ('default', 'wide')", name=op.f("ck_account_page_width")),
        sa.CheckConstraint("language in ('pt-BR', 'en')", name=op.f("ck_account_language")),
        sa.CheckConstraint("start_page in ('last', 'bases')", name=op.f("ck_account_start_page")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
        sa.UniqueConstraint("google_sub", name=op.f("uq_account_google_sub")),
        schema="acervo",
    )
    op.create_index(
        "uq_account_email_lower", "account", [sa.literal_column("lower(email)")], unique=True, schema="acervo"
    )
    op.create_table(
        "session",
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        *_id_and_timestamps(),
        _account_fk("session"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_session_token_hash")),
        schema="acervo",
    )
    op.create_index(op.f("ix_session_account_id"), "session", ["account_id"], unique=False, schema="acervo")
    op.create_table(
        "email_code",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("target_email", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        *_id_and_timestamps(),
        sa.CheckConstraint("purpose in ('verify_email', 'change_email')", name=op.f("ck_email_code_purpose")),
        _account_fk("email_code"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_code")),
        schema="acervo",
    )
    op.create_index(
        "uq_email_code_live",
        "email_code",
        ["account_id", "purpose"],
        unique=True,
        schema="acervo",
        postgresql_where=sa.text("used_at is null"),
    )
    op.create_table(
        "password_reset",
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        *_id_and_timestamps(),
        _account_fk("password_reset"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_token_hash")),
        schema="acervo",
    )
    op.create_index(
        op.f("ix_password_reset_account_id"), "password_reset", ["account_id"], unique=False, schema="acervo"
    )
    op.create_table(
        "login_failure",
        sa.Column("email_lower", sa.Text(), nullable=False),
        *_id_and_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_failure")),
        schema="acervo",
    )
    op.create_index(
        op.f("ix_login_failure_email_lower_created_at"),
        "login_failure",
        ["email_lower", "created_at"],
        unique=False,
        schema="acervo",
    )
    op.create_table(
        "favorite",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("sort", sa.Text(), nullable=False),
        *_id_and_timestamps(),
        _account_fk("favorite"),
        sa.ForeignKeyConstraint(
            ["node_id"], ["acervo.node.id"], name=op.f("fk_favorite_node_id_node"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_favorite")),
        sa.UniqueConstraint("account_id", "node_id", name=op.f("uq_favorite_account_id_node_id")),
        schema="acervo",
    )
    op.create_index(op.f("ix_favorite_node_id"), "favorite", ["node_id"], unique=False, schema="acervo")


def downgrade() -> None:
    for table in ("favorite", "login_failure", "password_reset", "email_code", "session", "account"):
        op.drop_table(table, schema="acervo")
