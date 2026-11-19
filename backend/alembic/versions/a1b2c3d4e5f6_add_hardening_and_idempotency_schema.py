"""Add hardening fields, creator profile fields, and webhook_events table

Revision ID: a1b2c3d4e5f6
Revises: e5f6a7b8c9d0
Create Date: 2026-11-19 16:55:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = insp.get_table_names()

    # 1. Add missing columns to users
    if "users" in existing_tables:
        columns = [c["name"] for c in insp.get_columns("users")]
        
        user_cols_to_add = [
            ("token_version", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")),
            ("creator_brand_name", sa.Column("creator_brand_name", sa.String(255), nullable=True)),
            ("creator_store_slug", sa.Column("creator_store_slug", sa.String(100), nullable=True)),
            ("creator_logo_url", sa.Column("creator_logo_url", sa.String(500), nullable=True)),
            ("creator_banner_url", sa.Column("creator_banner_url", sa.String(500), nullable=True)),
            ("creator_tagline", sa.Column("creator_tagline", sa.String(255), nullable=True)),
            ("creator_bio", sa.Column("creator_bio", sa.Text(), nullable=True)),
            ("creator_support_email", sa.Column("creator_support_email", sa.String(255), nullable=True)),
            ("creator_website", sa.Column("creator_website", sa.String(500), nullable=True)),
            ("creator_social_links", sa.Column("creator_social_links", sa.JSON(), nullable=True)),
            ("payout_method", sa.Column("payout_method", sa.String(50), nullable=True, server_default="stripe")),
            ("payout_stripe_email", sa.Column("payout_stripe_email", sa.String(255), nullable=True)),
            ("payout_paypal_email", sa.Column("payout_paypal_email", sa.String(255), nullable=True)),
            ("payout_razorpay_vpa", sa.Column("payout_razorpay_vpa", sa.String(255), nullable=True)),
            ("creator_payout_details", sa.Column("creator_payout_details", sa.JSON(), nullable=True)),
            ("storefront_distribution", sa.Column("storefront_distribution", sa.String(50), nullable=True, server_default="both")),
            ("is_creator_onboarding_completed", sa.Column("is_creator_onboarding_completed", sa.Boolean(), nullable=False, server_default="false")),
        ]
        
        for col_name, col_obj in user_cols_to_add:
            if col_name not in columns:
                try:
                    op.add_column("users", col_obj)
                except Exception:
                    pass

        try:
            op.create_index("ix_users_creator_store_slug", "users", ["creator_store_slug"], unique=True)
        except Exception:
            pass

    # 2. Add forked_from_template_id to templates if missing
    if "templates" in existing_tables:
        columns = [c["name"] for c in insp.get_columns("templates")]
        if "forked_from_template_id" not in columns:
            if bind.dialect.name == "postgresql":
                op.add_column("templates", sa.Column("forked_from_template_id", postgresql.UUID(as_uuid=True), nullable=True))
            else:
                op.add_column("templates", sa.Column("forked_from_template_id", sa.String(36), nullable=True))
            try:
                op.create_index("ix_templates_forked_from_template_id", "templates", ["forked_from_template_id"])
            except Exception:
                pass

    # 3. Add missing columns to creator_earnings
    if "creator_earnings" in existing_tables:
        columns = [c["name"] for c in insp.get_columns("creator_earnings")]
        if "holding_until" not in columns:
            op.add_column("creator_earnings", sa.Column("holding_until", sa.DateTime(timezone=True), nullable=True))
        if "platform_fee" not in columns:
            op.add_column("creator_earnings", sa.Column("platform_fee", sa.Numeric(10, 2), nullable=True, server_default="0.00"))
        if "net_creator_earning" not in columns:
            op.add_column("creator_earnings", sa.Column("net_creator_earning", sa.Numeric(10, 2), nullable=True, server_default="0.00"))
        if "payout_request_id" not in columns:
            if bind.dialect.name == "postgresql":
                op.add_column("creator_earnings", sa.Column("payout_request_id", postgresql.UUID(as_uuid=True), nullable=True))
            else:
                op.add_column("creator_earnings", sa.Column("payout_request_id", sa.String(36), nullable=True))
            try:
                op.create_index("ix_creator_earnings_payout_request_id", "creator_earnings", ["payout_request_id"])
            except Exception:
                pass

    # 4. Create webhook_events table if missing
    if "webhook_events" not in existing_tables:
        if bind.dialect.name == "postgresql":
            id_col = sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)
        else:
            id_col = sa.Column("id", sa.String(36), primary_key=True)

        op.create_table(
            "webhook_events",
            id_col,
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("event_id", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event_id")
        )
        try:
            op.create_index("ix_webhook_events_provider_event_id", "webhook_events", ["provider", "event_id"])
        except Exception:
            pass


def downgrade() -> None:
    pass
