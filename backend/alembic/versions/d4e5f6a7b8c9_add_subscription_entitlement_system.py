"""add subscription entitlement system

Revision ID: d4e5f6a7b8c9
Revises: c1a72f4d8e90
Create Date: 2026-11-13 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1a72f4d8e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. user_subscriptions
    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.String(length=50), server_default="free", nullable=False),
        sa.Column("billing_cycle", sa.String(length=20), server_default="monthly", nullable=False),
        sa.Column("payment_provider", sa.String(length=50), server_default="manual", nullable=False),
        sa.Column("provider_customer_id", sa.String(length=255), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="active", nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_billing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_trial", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("trial_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failed_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("provider_subscription_id"),
    )
    op.create_index(op.f("ix_user_subscriptions_user_id"), "user_subscriptions", ["user_id"], unique=True)
    op.create_index(op.f("ix_user_subscriptions_plan_id"), "user_subscriptions", ["plan_id"], unique=False)
    op.create_index(op.f("ix_user_subscriptions_status"), "user_subscriptions", ["status"], unique=False)
    op.create_index(op.f("ix_user_subscriptions_current_period_end"), "user_subscriptions", ["current_period_end"], unique=False)

    # 2. subscription_events
    op.create_table(
        "subscription_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("provider_event_type", sa.String(length=100), nullable=False),
        sa.Column("subscription_id", sa.String(length=255), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="processed", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_event_id"),
    )
    op.create_index(op.f("ix_subscription_events_provider_event_id"), "subscription_events", ["provider_event_id"], unique=True)
    op.create_index(op.f("ix_subscription_events_provider_event_type"), "subscription_events", ["provider_event_type"], unique=False)
    op.create_index(op.f("ix_subscription_events_subscription_id"), "subscription_events", ["subscription_id"], unique=False)
    op.create_index(op.f("ix_subscription_events_user_id"), "subscription_events", ["user_id"], unique=False)

    # 3. usage_ledger
    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.String(length=255), nullable=True),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=10, scale=2), server_default="1.0", nullable=False),
        sa.Column("credits_consumed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_provider_cost", sa.Numeric(precision=10, scale=6), server_default="0.000000", nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="USD", nullable=False),
        sa.Column("provider", sa.String(length=50), server_default="gemini", nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usage_ledger_user_id"), "usage_ledger", ["user_id"], unique=False)
    op.create_index(op.f("ix_usage_ledger_deployment_id"), "usage_ledger", ["deployment_id"], unique=False)
    op.create_index(op.f("ix_usage_ledger_operation"), "usage_ledger", ["operation"], unique=False)
    op.create_index(op.f("ix_usage_ledger_created_at"), "usage_ledger", ["created_at"], unique=False)

    # 4. trial_history
    op.create_table(
        "trial_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("template_slug", sa.String(length=255), nullable=True),
        sa.Column("deployment_id", sa.Uuid(), nullable=True),
        sa.Column("trial_type", sa.String(length=50), server_default="deployment", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trial_history_user_id"), "trial_history", ["user_id"], unique=False)
    op.create_index(op.f("ix_trial_history_template_id"), "trial_history", ["template_id"], unique=False)
    op.create_index(op.f("ix_trial_history_template_slug"), "trial_history", ["template_slug"], unique=False)

    # 5. auto_heal_registrations
    op.create_table(
        "auto_heal_registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.String(length=50), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("repair_count_current_period", sa.Integer(), server_default="0", nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_healed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auto_heal_registrations_user_id"), "auto_heal_registrations", ["user_id"], unique=False)
    op.create_index(op.f("ix_auto_heal_registrations_deployment_id"), "auto_heal_registrations", ["deployment_id"], unique=False)
    op.create_index(op.f("ix_auto_heal_registrations_site_id"), "auto_heal_registrations", ["site_id"], unique=False)

    # 6. promotional_domain_credits
    op.create_table(
        "promotional_domain_credits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("max_credit_usd", sa.Numeric(precision=10, scale=2), server_default="15.00", nullable=False),
        sa.Column("credit_used_usd", sa.Numeric(precision=10, scale=2), server_default="0.00", nullable=False),
        sa.Column("domain_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="available", nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_promotional_domain_credits_user_id"), "promotional_domain_credits", ["user_id"], unique=False)

    # 7. Add subscription and auto-heal columns to users table
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("subscription_status", sa.String(length=50), server_default="active", nullable=True))
        batch_op.add_column(sa.Column("subscription_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("auto_renew", sa.Boolean(), server_default="true", nullable=False))
        batch_op.add_column(sa.Column("free_domain_claimed", sa.Boolean(), server_default="false", nullable=False))
        batch_op.add_column(sa.Column("pro_auto_heal_deployment_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("pro_auto_heal_expires_at", sa.DateTime(timezone=True), nullable=True))

    # 8. Add trial and auto-heal columns to deployments table
    with op.batch_alter_table("deployments") as batch_op:
        batch_op.add_column(sa.Column("trial_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("custom_domain_trial_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("is_auto_heal_active", sa.Boolean(), server_default="false", nullable=False))

    # 9. Add transfer push columns to domains table
    with op.batch_alter_table("domains") as batch_op:
        batch_op.add_column(sa.Column("transfer_lock", sa.Boolean(), server_default="false", nullable=False))
        batch_op.add_column(sa.Column("transfer_auth_code", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("transfer_status", sa.String(length=50), server_default="none", nullable=True))
        batch_op.add_column(sa.Column("pushed_to_account", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("domains") as batch_op:
        batch_op.drop_column("pushed_at")
        batch_op.drop_column("pushed_to_account")
        batch_op.drop_column("transfer_status")
        batch_op.drop_column("transfer_auth_code")
        batch_op.drop_column("transfer_lock")

    with op.batch_alter_table("deployments") as batch_op:
        batch_op.drop_column("is_auto_heal_active")
        batch_op.drop_column("custom_domain_trial_expires_at")
        batch_op.drop_column("trial_expires_at")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("pro_auto_heal_expires_at")
        batch_op.drop_column("pro_auto_heal_deployment_id")
        batch_op.drop_column("free_domain_claimed")
        batch_op.drop_column("auto_renew")
        batch_op.drop_column("subscription_id")
        batch_op.drop_column("subscription_status")
        batch_op.drop_column("subscription_expires_at")

    op.drop_table("promotional_domain_credits")
    op.drop_table("auto_heal_registrations")
    op.drop_table("trial_history")
    op.drop_table("usage_ledger")
    op.drop_table("subscription_events")
    op.drop_table("user_subscriptions")

