"""
Analytics ORM model — page views and custom events.
"""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class AnalyticsEvent(UUIDMixin, TimestampMixin, Base):
    """Records page views and custom events for analytics."""

    __tablename__ = "analytics_events"

    # Optional user reference
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. "page_view", "template_view", "preview_started", "purchase", "download"

    # Generic entity reference
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Context
    page_path: Mapped[Optional[str]] = mapped_column(String(500))
    referrer: Mapped[Optional[str]] = mapped_column(String(500))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    country: Mapped[Optional[str]] = mapped_column(String(2))  # ISO 3166-1 alpha-2

    # Arbitrary payload
    properties: Mapped[Optional[dict]] = mapped_column(JSON)

    def __repr__(self) -> str:
        return f"<AnalyticsEvent {self.event_type}>"
