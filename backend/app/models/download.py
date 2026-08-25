"""
Download ORM model — tracks template file downloads after purchase.
"""

import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.template import Template


class Download(UUIDMixin, TimestampMixin, Base):
    """Records each template file download."""

    __tablename__ = "downloads"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Which format was downloaded (react | html | zip)
    format: Mapped[str] = mapped_column(String(20), default="zip")
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="downloads")
    template: Mapped["Template"] = relationship(back_populates="downloads")

    def __repr__(self) -> str:
        return f"<Download user={self.user_id} template={self.template_id} format={self.format}>"
