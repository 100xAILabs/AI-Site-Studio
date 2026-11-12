"""
TamperAlert ORM model — tracks unauthorized removal or tampering of template watermarks and license guards.
"""

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class TamperAlert(UUIDMixin, TimestampMixin, Base):
    """
    Records stealth telemetry beacons triggered when a Standard Edition template's
    embedded watermark, license files, or runtime guards are removed or modified.
    """

    __tablename__ = "tamper_alerts"

    template_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    template_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    license_key: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    buyer_email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    violation_type: Mapped[str] = mapped_column(String(100), nullable=False, default="watermark_removed")
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<TamperAlert {self.id} template={self.template_id} violation={self.violation_type} domain={self.domain}>"

