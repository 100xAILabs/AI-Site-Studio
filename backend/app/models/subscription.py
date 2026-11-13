"""
Subscription, Entitlement, Usage Ledger, and Trial Models.

Provides authoritative database entities for:
- UserSubscription: Primary recurring subscription independent of per-deployment hosting
- SubscriptionEvent: Durable, idempotent webhook and lifecycle event store
- UsageLedger: Auditable event ledger for AI compute, operations, and infrastructure costs
- TrialHistory: Permanent record of template & deployment trials per user account
- AutoHealRegistration: Persistent registration of websites authorized for autonomous healing
- PromotionalDomainCredit: Safe single-use promotional domain registration credits
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.deployment import Deployment
    from app.models.template import Template


class UserSubscription(UUIDMixin, TimestampMixin, Base):
    """
    Primary user subscription record.
    Tracks user-level plan entitlements (Free, Pro, Extreme), independent of
    per-deployment HostingSubscription records.
    """

    __tablename__ = "user_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    plan_id: Mapped[str] = mapped_column(
        String(50), default="free", server_default="free", nullable=False, index=True
    )  # free, pro, extreme
    billing_cycle: Mapped[str] = mapped_column(
        String(20), default="monthly", server_default="monthly", nullable=False
    )  # monthly, annual
    payment_provider: Mapped[str] = mapped_column(
        String(50), default="manual", server_default="manual", nullable=False
    )  # razorpay, stripe, manual

    provider_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)

    status: Mapped[str] = mapped_column(
        String(50), default="active", server_default="active", nullable=False, index=True
    )  # active, past_due, canceled, unpaid, trialing, incomplete

    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    next_billing_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    trial_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    last_successful_payment_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failed_payment_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="select")

    def __repr__(self) -> str:
        return f"<UserSubscription user={self.user_id} plan={self.plan_id} status={self.status}>"


class SubscriptionEvent(UUIDMixin, TimestampMixin, Base):
    """
    Durable, idempotent webhook and subscription lifecycle event store.
    Guarantees that duplicate webhooks (from Razorpay or Stripe) are not processed repeatedly.
    """

    __tablename__ = "subscription_events"

    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # razorpay, stripe
    provider_event_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )  # Unique provider ID (e.g. evt_..., event_xxx)
    provider_event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="processed", server_default="processed", nullable=False
    )  # processed, failed, ignored
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SubscriptionEvent {self.provider}:{self.provider_event_id} type={self.provider_event_type} status={self.status}>"


class UsageLedger(UUIDMixin, Base):
    """
    Auditable usage ledger.
    Measures every AI generation, conversational edit, auto-heal, deployment build,
    storage, bandwidth, and add-on with estimated provider costs.
    """

    __tablename__ = "usage_ledger"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deployment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deployments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    operation: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=1.0, nullable=False)
    credits_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_provider_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0.000000"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="gemini", nullable=False)  # gemini, openai, anthropic, etc.
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<UsageLedger user={self.user_id} op={self.operation} credits={self.credits_consumed} cost=${self.estimated_provider_cost}>"


class TrialHistory(UUIDMixin, Base):
    """
    Permanent audit history of template and deployment trials per user account.
    Enforces:
    - 1 free trial per template per account permanently.
    - Trial history is never wiped by deployment deletions or plan changes.
    """

    __tablename__ = "trial_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_slug: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    deployment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deployments.id", ondelete="SET NULL"),
        nullable=True,
    )
    trial_type: Mapped[str] = mapped_column(
        String(50), default="deployment", nullable=False
    )  # deployment, generation
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<TrialHistory user={self.user_id} template={self.template_slug} active={self.is_active}>"


class AutoHealRegistration(UUIDMixin, TimestampMixin, Base):
    """
    Persistent registration of websites designated for autonomous AI Auto-Heal.
    Enforces:
    - Free: 0 sites.
    - Pro: exactly 1 persistently registered site per billing month.
    - Extreme: up to 3 registered sites per billing month.
    """

    __tablename__ = "auto_heal_registrations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    site_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    repair_count_current_period: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_healed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    deployment: Mapped["Deployment"] = relationship("Deployment", lazy="select")

    def __repr__(self) -> str:
        return f"<AutoHealRegistration user={self.user_id} deployment={self.deployment_id} active={self.active} repairs={self.repair_count_current_period}>"


class PromotionalDomainCredit(UUIDMixin, TimestampMixin, Base):
    """
    Capped promotional domain credit tracking.
    Enforces maximum monetary cap, single redemption, live registrar quote validation,
    and records actual registrar cost.
    """

    __tablename__ = "promotional_domain_credits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    max_credit_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("15.00"), nullable=False
    )
    credit_used_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    domain_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(40), default="available", server_default="available", nullable=False
    )  # available, redeemed, expired
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<PromotionalDomainCredit user={self.user_id} status={self.status} used=${self.credit_used_usd}/${self.max_credit_usd}>"

