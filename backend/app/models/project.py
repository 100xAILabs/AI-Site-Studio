"""
Project ORM model — Represents a tenant's customized workspace instance of a template.
"""

import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import ForeignKey, String, Text, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.template import Template


class Project(UUIDMixin, TimestampMixin, Base):
    """Represents an editable tenant website project."""

    __tablename__ = "projects"

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

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)  # draft, published, archived
    configuration: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(lazy="select")
    template: Mapped[Optional["Template"]] = relationship(lazy="select")

    def __repr__(self) -> str:
        return f"<Project {self.name} [{self.status}] user={self.user_id}>"
