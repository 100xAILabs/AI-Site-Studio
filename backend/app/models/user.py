"""
User ORM model.
"""

import uuid
import enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SAEnum, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.review import Review
    from app.models.wishlist import WishlistItem
    from app.models.favorite import Favorite
    from app.models.download import Download
    from app.models.template import Template


class UserRole(str, enum.Enum):
    USER = "user"
    BUYER = "buyer"
    SELLER = "seller"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(UUIDMixin, TimestampMixin, Base):
    """Represents an authenticated user synced from Clerk."""

    __tablename__ = "users"

    # OAuth Integrations
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    facebook_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    github_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    github_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Profile
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    bio: Mapped[Optional[str]] = mapped_column(Text)

    # Auth
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), default=UserRole.USER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # AI Credits
    ai_credits: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Billing
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255))
    razorpay_customer_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    orders: Mapped[List["Order"]] = relationship(back_populates="user", lazy="select", cascade="all, delete-orphan")
    reviews: Mapped[List["Review"]] = relationship(back_populates="user", lazy="select", cascade="all, delete-orphan")
    wishlist_items: Mapped[List["WishlistItem"]] = relationship(back_populates="user", lazy="select", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="user", lazy="select", cascade="all, delete-orphan")
    downloads: Mapped[List["Download"]] = relationship(back_populates="user", lazy="select", cascade="all, delete-orphan")
    # Templates uploaded by this seller — permanently stored per account
    uploaded_templates: Mapped[List["Template"]] = relationship(
        back_populates="seller", lazy="select", foreign_keys="Template.seller_id", cascade="all, delete-orphan"
    )

    @property
    def has_github_token(self) -> bool:
        return self.github_access_token is not None and len(self.github_access_token.strip()) > 0

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role}]>"
