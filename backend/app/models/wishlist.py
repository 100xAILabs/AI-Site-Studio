"""
WishlistItem ORM model.
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


class WishlistItem(UUIDMixin, TimestampMixin, Base):
    """Tracks templates a user has added to their wishlist."""

    __tablename__ = "wishlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "template_id", name="unique_wishlist_item"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="wishlist_items")
    template: Mapped["Template"] = relationship(back_populates="wishlist_items")

    def __repr__(self) -> str:
        return f"<WishlistItem user={self.user_id} template={self.template_id}>"
