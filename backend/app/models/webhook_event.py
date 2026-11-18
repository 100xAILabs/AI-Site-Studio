"""
WebhookEvent ORM model — tracks processed webhook event IDs across payment providers
(Razorpay, Stripe) for strict database-level deduplication and replay attack prevention.
"""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class WebhookEvent(UUIDMixin, TimestampMixin, Base):
    """
    Immutable ledger of processed webhook events.
    Enforces that every webhook event ID is claimed and processed at most once.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )

    provider: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<WebhookEvent {self.id} provider={self.provider} event={self.event_id}>"
