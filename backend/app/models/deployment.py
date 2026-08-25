"""
Deployment, DeploymentVersion, Domain, and DeploymentLog ORM models.
Multi-Tenant Control Plane architecture.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import ForeignKey, String, Text, Uuid, Boolean, JSON, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.template import Template


class Deployment(UUIDMixin, TimestampMixin, Base):
    """Represents an isolated tenant website deployment."""

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

    # Unique Stable Site Identifier (e.g. SITE-8F72A)
    site_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)

    # Configuration & Metadata
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="local", nullable=False)  # local, vercel, netlify, docker
    status: Mapped[str] = mapped_column(String(50), default="created", nullable=False)  # created, queued, building, live, failed, suspended, stopped
    current_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)
    deployment_type: Mapped[str] = mapped_column(String(50), default="static", nullable=False)  # static, container
    health_status: Mapped[str] = mapped_column(String(50), default="healthy", nullable=False)  # healthy, degraded, down

    subdomain: Mapped[str] = mapped_column(String(255), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    commit_message: Mapped[str] = mapped_column(String(255), default="Initial deploy", nullable=False)
    build_command: Mapped[str] = mapped_column(String(255), default="npm run build", nullable=False)
    output_dir: Mapped[str] = mapped_column(String(255), default="dist", nullable=False)
    
    # Deployment Outputs & Security
    logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    live_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    custom_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    deployment_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    env_vars: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(lazy="select")
    template: Mapped[Optional["Template"]] = relationship(lazy="select")
    versions: Mapped[List["DeploymentVersion"]] = relationship(
        "DeploymentVersion", back_populates="deployment", cascade="all, delete-orphan", lazy="select"
    )
    domains: Mapped[List["Domain"]] = relationship(
        "Domain", back_populates="deployment", cascade="all, delete-orphan", lazy="select"
    )
    deployment_logs: Mapped[List["DeploymentLog"]] = relationship(
        "DeploymentLog", back_populates="deployment", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Deployment {self.project_name} [{self.status}] site={self.site_id} version={self.current_version}>"


class DeploymentVersion(UUIDMixin, TimestampMixin, Base):
    """Tracks multi-version history (v1, v2, v3) for 1-click zero-downtime rollback."""

    __tablename__ = "deployment_versions"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)  # v1.0, v1.1, etc.
    build_reference: Mapped[str] = mapped_column(String(500), nullable=False)  # local or storage path
    status: Mapped[str] = mapped_column(String(50), default="previous", nullable=False)  # live, previous, failed
    commit_message: Mapped[str] = mapped_column(String(255), default="Automated build", nullable=False)
    build_logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="versions")

    def __repr__(self) -> str:
        return f"<DeploymentVersion {self.version} [{self.status}] for deployment={self.deployment_id}>"


class Domain(UUIDMixin, TimestampMixin, Base):
    """Manages custom domains and subdomains with verification and SSL tracking."""

    __tablename__ = "domains"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    domain_type: Mapped[str] = mapped_column(String(50), default="subdomain", nullable=False)  # subdomain, custom
    verification_status: Mapped[str] = mapped_column(String(50), default="pending_verification", nullable=False)  # verified, pending_verification, failed
    ssl_status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, pending, self_signed
    verification_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationship
    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="domains")

    def __repr__(self) -> str:
        return f"<Domain {self.domain} [{self.verification_status}]>"


class DeploymentLog(UUIDMixin, Base):
    """Real-time structured deployment log event."""

    __tablename__ = "deployment_logs"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    level: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)  # INFO, WARN, ERROR, SUCCESS
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationship
    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="deployment_logs")

    def __repr__(self) -> str:
        return f"<DeploymentLog [{self.level}] {self.message[:30]}>"
