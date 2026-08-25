"""
Follow ORM model.
"""

import uuid
from sqlalchemy import ForeignKey, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Follow(UUIDMixin, TimestampMixin, Base):
    """Tracks users following sellers."""

    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "seller_id", name="uq_follower_seller"),
    )

    follower_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    follower = relationship("User", foreign_keys=[follower_id], backref="following_follows")
    seller = relationship("User", foreign_keys=[seller_id], backref="follower_follows")

    def __repr__(self) -> str:
        return f"<Follow follower={self.follower_id} seller={self.seller_id}>"
