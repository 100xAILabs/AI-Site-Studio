"""
Category ORM model — supports nested categories via parent_id.
"""

import uuid
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.template import Template


class Category(UUIDMixin, TimestampMixin, Base):
    """
    Hierarchical category for templates.
    Supports one level of parent → child nesting.
    """

    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(String(100))  # Lucide icon name
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    color: Mapped[Optional[str]] = mapped_column(String(20))  # hex color
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)

    # Self-referencing FK for subcategories
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )
    children: Mapped[List["Category"]] = relationship(
        "Category", back_populates="parent", lazy="select"
    )
    templates: Mapped[List["Template"]] = relationship(
        back_populates="category", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Category {self.name}>"
