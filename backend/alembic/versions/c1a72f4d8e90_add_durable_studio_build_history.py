"""add durable studio build history

Revision ID: c1a72f4d8e90
Revises: f9b8a7c6d5e4
Create Date: 2026-10-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a72f4d8e90"
down_revision: Union[str, None] = "f9b8a7c6d5e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "studio_builds",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("initial_prompt", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("site_type", sa.String(length=100), nullable=False),
        sa.Column("stack", sa.String(length=80), nullable=False, server_default="html-css-js"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("current_phase", sa.String(length=80), nullable=False, server_default="queued"),
        sa.Column("plan", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("answers", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("approved_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("result_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_studio_builds_user_id", "studio_builds", ["user_id"])
    op.create_index("ix_studio_builds_template_id", "studio_builds", ["template_id"])
    op.create_index("ix_studio_builds_status", "studio_builds", ["status"])
    op.execute('ALTER TABLE public."studio_builds" ENABLE ROW LEVEL SECURITY;')

    op.create_table(
        "studio_build_messages",
        sa.Column("build_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False, server_default="chat"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["build_id"], ["studio_builds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("build_id", "sequence", name="uq_studio_build_message_sequence"),
    )
    op.create_index("ix_studio_build_messages_build_id", "studio_build_messages", ["build_id"])
    op.create_index("ix_studio_build_messages_created_at", "studio_build_messages", ["created_at"])
    op.execute('ALTER TABLE public."studio_build_messages" ENABLE ROW LEVEL SECURITY;')

    op.create_table(
        "studio_build_events",
        sa.Column("build_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["build_id"], ["studio_builds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("build_id", "sequence", name="uq_studio_build_event_sequence"),
    )
    op.create_index("ix_studio_build_events_build_id", "studio_build_events", ["build_id"])
    op.execute('ALTER TABLE public."studio_build_events" ENABLE ROW LEVEL SECURITY;')


def downgrade() -> None:
    op.drop_index("ix_studio_build_events_build_id", table_name="studio_build_events")
    op.drop_table("studio_build_events")
    op.drop_index("ix_studio_build_messages_created_at", table_name="studio_build_messages")
    op.drop_index("ix_studio_build_messages_build_id", table_name="studio_build_messages")
    op.drop_table("studio_build_messages")
    op.drop_index("ix_studio_builds_status", table_name="studio_builds")
    op.drop_index("ix_studio_builds_template_id", table_name="studio_builds")
    op.drop_index("ix_studio_builds_user_id", table_name="studio_builds")
    op.drop_table("studio_builds")
