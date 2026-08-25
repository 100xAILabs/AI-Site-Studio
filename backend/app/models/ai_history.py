"""
AIHistory ORM model — logs all AI API calls for billing and analytics.
"""

import uuid
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, JSON, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class AIHistory(UUIDMixin, TimestampMixin, Base):
    """Logs each AI API call with token usage and cost tracking."""

    __tablename__ = "ai_history"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Feature that triggered the call
    feature: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. "content_generator", "seo_generator", "template_recommendation",
    #       "color_palette", "image_generator", "chat_assistant", "preview_fill"

    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Approximate cost in USD
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6))

    # Credits deducted from user
    credits_used: Mapped[int] = mapped_column(Integer, default=1)

    # Request / response snapshot (for debugging)
    request_summary: Mapped[Optional[str]] = mapped_column(Text)
    response_summary: Mapped[Optional[str]] = mapped_column(Text)
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON)

    # Relationships
    user: Mapped[Optional["User"]] = relationship()

    def __repr__(self) -> str:
        return f"<AIHistory {self.feature} tokens={self.total_tokens}>"
