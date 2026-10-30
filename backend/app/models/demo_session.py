"""
DemoSession ORM model — tracks temporary live demo sessions.
Enforces 30-minute access locks and automated permanent deletion of generated website data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.template import Template


class DemoSession(UUIDMixin, TimestampMixin, Base):
    """
    Tracks an active 30-minute user live demo session on a generated website.
    When expired, abandoned, tab closed, or server stopped, all details
    shared inside the generated website are permanently wiped.
    """

    __tablename__ = "demo_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_token: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False, default=lambda: uuid.uuid4().hex
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)  # 30 minutes
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(minutes=30),
        nullable=False,
        index=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_wiped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wipe_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    custom_draft_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    wiped_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship()
    template: Mapped["Template"] = relationship()

    def is_expired(self) -> bool:
        """Check if the 30-minute demo duration has elapsed."""
        now = datetime.now(timezone.utc)
        return now >= self.expires_at

    def remaining_seconds(self) -> int:
        """Return the remaining demo duration in seconds."""
        if not self.is_active or self.is_expired():
            return 0
        now = datetime.now(timezone.utc)
        rem = int((self.expires_at - now).total_seconds())
        return max(0, rem)

    def __repr__(self) -> str:
        return f"<DemoSession {self.session_token[:8]} user={self.user_id} template={self.template_id} active={self.is_active}>"

