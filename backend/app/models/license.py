"""
License ORM model — issued after purchase.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.template import Template
    from app.models.order import Order


class LicenseType(str, enum.Enum):
    REGULAR = "regular"
    EXTENDED = "extended"


class License(UUIDMixin, TimestampMixin, Base):
    """License key issued to a user after purchasing a template."""

    __tablename__ = "licenses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )

    license_key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    license_type: Mapped[LicenseType] = mapped_column(SAEnum(LicenseType), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Additional metadata (e.g., domain restrictions)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    user: Mapped["User"] = relationship()
    template: Mapped["Template"] = relationship()
    order: Mapped["Order"] = relationship()

    def __repr__(self) -> str:
        return f"<License {self.license_key} [{self.license_type}]>"
