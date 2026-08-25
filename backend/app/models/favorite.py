"""
Favorite ORM model — similar to wishlist but separate concept (liked/bookmarked).
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.template import Template


class Favorite(UUIDMixin, TimestampMixin, Base):
    """Tracks templates a user has liked/favorited."""

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "template_id", name="unique_favorite"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="favorites")
    template: Mapped["Template"] = relationship(back_populates="favorites")

    def __repr__(self) -> str:
        return f"<Favorite user={self.user_id} template={self.template_id}>"
