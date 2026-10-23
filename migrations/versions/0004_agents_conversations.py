"""agents of a base (the built-in chat and MCP clients), conversations and messages; proposals know their source

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22 22:16:10.091495
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

KINDS = "'append', 'edit', 'create_page', 'conflict', 'save_pdf', 'replace_pdf', 'move', 'rename', 'undo'"
CHAT_AGENT = "insert into acervo.agent (kb_id, name, mode, built_in) select {kb}, 'Chat do Acervo', 'ask', true"


def upgrade() -> None:
    op.create_table(
        "agent",
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), server_default="ask", nullable=False),
        sa.Column("built_in", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=True),
        sa.Column("token_hint", sa.Text(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("mode in ('ask', 'auto')", name=op.f("ck_agent_mode")),
        sa.ForeignKeyConstraint(["kb_id"], ["acervo.kb.id"], name=op.f("fk_agent_kb_id_kb")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_agent_token_hash")),
        schema="acervo",
    )
    op.create_index(op.f("ix_agent_kb_id"), "agent", ["kb_id"], unique=False, schema="acervo")
    op.create_index(
        "uq_agent_built_in", "agent", ["kb_id"], unique=True, schema="acervo", postgresql_where=sa.text("built_in")
    )
    op.create_table(
        "conversation",
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["acervo.agent.id"], name=op.f("fk_conversation_agent_id_agent")),
        sa.ForeignKeyConstraint(["kb_id"], ["acervo.kb.id"], name=op.f("fk_conversation_kb_id_kb")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation")),
        schema="acervo",
    )
    op.create_index(op.f("ix_conversation_agent_id"), "conversation", ["agent_id"], unique=False, schema="acervo")
    op.create_index(op.f("ix_conversation_kb_id"), "conversation", ["kb_id"], unique=False, schema="acervo")
    op.create_table(
        "message",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), server_default="", nullable=False),
        sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("understood_as", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), server_default="done", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("replaces_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role in ('person', 'acervo')", name=op.f("ck_message_role")),
        sa.CheckConstraint("status in ('done', 'working', 'failed')", name=op.f("ck_message_status")),
        sa.CheckConstraint(
            "understood_as in ('perguntar', 'guardar', 'organizar', 'conversar')",
            name=op.f("ck_message_understood_as"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["acervo.conversation.id"], name=op.f("fk_message_conversation_id_conversation")
        ),
        sa.ForeignKeyConstraint(["replaces_id"], ["acervo.message.id"], name=op.f("fk_message_replaces_id_message")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message")),
        schema="acervo",
    )
    op.create_index(op.f("ix_message_conversation_id"), "message", ["conversation_id"], unique=False, schema="acervo")
    op.create_index(op.f("ix_message_run_id"), "message", ["run_id"], unique=False, schema="acervo")

    op.add_column("decision_log", sa.Column("message_id", sa.Uuid(), nullable=True), schema="acervo")
    op.create_index(op.f("ix_decision_log_message_id"), "decision_log", ["message_id"], unique=False, schema="acervo")
    op.create_foreign_key(
        op.f("fk_decision_log_message_id_message"),
        "decision_log",
        "message",
        ["message_id"],
        ["id"],
        source_schema="acervo",
        referent_schema="acervo",
    )

    # No code wrote a proposal before this revision, so the new required columns need no default.
    op.add_column("proposal", sa.Column("kb_id", sa.Uuid(), nullable=False), schema="acervo")
    op.add_column("proposal", sa.Column("agent_id", sa.Uuid(), nullable=False), schema="acervo")
    op.add_column("proposal", sa.Column("conversation_id", sa.Uuid(), nullable=True), schema="acervo")
    op.add_column("proposal", sa.Column("message_id", sa.Uuid(), nullable=True), schema="acervo")
    op.add_column("proposal", sa.Column("accepted_by", sa.Text(), nullable=True), schema="acervo")
    op.add_column("proposal", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True), schema="acervo")
    op.add_column(
        "proposal", sa.Column("staged", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="acervo"
    )
    op.add_column("proposal", sa.Column("undo_of", sa.Uuid(), nullable=True), schema="acervo")
    op.create_index(op.f("ix_proposal_kb_id"), "proposal", ["kb_id"], unique=False, schema="acervo")
    op.create_index(op.f("ix_proposal_message_id"), "proposal", ["message_id"], unique=False, schema="acervo")
    for column, table in (
        ("kb_id", "kb"),
        ("agent_id", "agent"),
        ("conversation_id", "conversation"),
        ("message_id", "message"),
        ("undo_of", "proposal"),
    ):
        op.create_foreign_key(
            op.f(f"fk_proposal_{column}_{table}"),
            "proposal",
            table,
            [column],
            ["id"],
            source_schema="acervo",
            referent_schema="acervo",
        )
    op.create_check_constraint(op.f("ck_proposal_kind"), "proposal", f"kind in ({KINDS})", schema="acervo")
    op.create_check_constraint(
        op.f("ck_proposal_accepted_by"), "proposal", "accepted_by in ('person', 'auto')", schema="acervo"
    )

    # Every base already there gets its chat; a new base gets it from BaseService.create.
    op.execute(CHAT_AGENT.format(kb="id") + " from acervo.kb")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_proposal_kind"), "proposal", schema="acervo", type_="check")
    # Dropping a column drops its indexes, foreign keys and checks with it.
    for column in (
        "undo_of",
        "staged",
        "applied_at",
        "accepted_by",
        "message_id",
        "conversation_id",
        "agent_id",
        "kb_id",
    ):
        op.drop_column("proposal", column, schema="acervo")
    op.drop_column("decision_log", "message_id", schema="acervo")
    op.drop_table("message", schema="acervo")
    op.drop_table("conversation", schema="acervo")
    op.drop_table("agent", schema="acervo")
