"""
Deployment ORM model.
"""

import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.template import Template


class Deployment(UUIDMixin, TimestampMixin, Base):
    """Represents a Vercel/Netlify/GitHub Pages project deployment."""

    __tablename__ = "deployments"

    # Foreign Keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Configuration & Metadata
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # vercel, netlify, github_pages
    status: Mapped[str] = mapped_column(String(50), default="building", nullable=False)  # building, success, failed
    subdomain: Mapped[str] = mapped_column(String(255), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    commit_message: Mapped[str] = mapped_column(String(255), default="Initial deploy", nullable=False)
    build_command: Mapped[str] = mapped_column(String(255), default="npm run build", nullable=False)
    output_dir: Mapped[str] = mapped_column(String(255), default="dist", nullable=False)
    
    # Deployment Outputs
    logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    live_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(lazy="select")
    template: Mapped[Optional["Template"]] = relationship(lazy="select")

    def __repr__(self) -> str:
        return f"<Deployment {self.project_name} [{self.status}] provider={self.provider}>"
