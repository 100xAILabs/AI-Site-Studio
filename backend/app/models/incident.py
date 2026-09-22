"""
SiteIncident ORM Model.
Tracks website failure reports, runtime crashes, error logs, and AI auto-healing resolution history.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import ForeignKey, String, Text, Uuid, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.deployment import Deployment


class SiteIncident(UUIDMixin, TimestampMixin, Base):
    """Represents a reported website failure or crash incident for an isolated deployment."""

    __tablename__ = "site_incidents"

    # Associated Deployment
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    site_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Reporter Info
    reporter_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reporter_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Incident Details
    issue_type: Mapped[str] = mapped_column(
        String(100), default="broken_script", nullable=False
    )  # broken_script, asset_404, styling_broken, page_crash, build_error, form_error, other
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    error_logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    severity: Mapped[str] = mapped_column(
        String(50), default="high", nullable=False
    )  # critical, high, medium, low

    # Resolution & Lifecycle
    status: Mapped[str] = mapped_column(
        String(50), default="open", nullable=False
    )  # open, investigating, auto_fixing, resolved, dismissed
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # ai_site_doctor, admin_manual, user_redeploy
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_patch_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="incidents", lazy="select")

    def __repr__(self) -> str:
        return f"<SiteIncident {self.site_id} [{self.issue_type}] status={self.status}>"
