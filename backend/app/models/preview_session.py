"""
PreviewSession ORM model — stores AI-generated preview configurations.
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.template import Template


class PreviewSession(UUIDMixin, TimestampMixin, Base):
    """
    Stores a live preview configuration for a template.
    Generated when user fills the preview form (business info, colors, etc.)
    """

    __tablename__ = "preview_sessions"

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Business info provided by the user
    business_data: Mapped[Optional[dict]] = mapped_column(JSON)
    # {
    #   "business_name": "...",
    #   "industry": "...",
    #   "logo_url": "...",
    #   "primary_color": "#...",
    #   "secondary_color": "#...",
    #   "about": "...",
    #   "services": [...],
    #   "contact": {...},
    #   "location": "...",
    #   "social_links": {...},
    # }

    # Generated preview content (AI-filled)
    generated_content: Mapped[Optional[dict]] = mapped_column(JSON)

    # The watermarked preview image/URL
    preview_image_url: Mapped[Optional[str]] = mapped_column(String(500))

    is_ai_filled: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    template: Mapped["Template"] = relationship()

    def __repr__(self) -> str:
        return f"<PreviewSession {self.id} template={self.template_id}>"
