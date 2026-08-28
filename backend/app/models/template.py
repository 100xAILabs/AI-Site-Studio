"""
Template ORM model — the core product entity.
"""

import enum
import uuid
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    String, Text, Boolean, Integer, Numeric, Float,
    ForeignKey, JSON, Uuid, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.review import Review
    from app.models.wishlist import WishlistItem
    from app.models.favorite import Favorite
    from app.models.order import OrderItem
    from app.models.download import Download
    from app.models.user import User


from sqlalchemy.types import TypeDecorator

class StringList(TypeDecorator):
    """
    A custom type that uses PostgreSQL's native ARRAY(String) if using PostgreSQL,
    and fallback JSON/Text type on SQLite.
    """
    impl = JSON
    cache_ok = True  # Safe: no mutable instance state; all behaviour is dialect-driven

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import ARRAY
            return dialect.type_descriptor(ARRAY(String))
        else:
            return dialect.type_descriptor(JSON)


class TemplateFramework(str, enum.Enum):
    REACT = "react"
    NEXTJS = "nextjs"
    VUE = "vue"
    NUXT = "nuxt"
    HTML = "html"
    ASTRO = "astro"
    TAILWIND = "tailwind"
    ANGULAR = "angular"
    SVELTE = "svelte"


class TemplateLicense(str, enum.Enum):
    REGULAR = "regular"
    EXTENDED = "extended"


class TemplateStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Template(UUIDMixin, TimestampMixin, Base):
    """
    Website template product listing.
    Includes all metadata required for marketplace display and filtering.
    """

    __tablename__ = "templates"

    # ── Core Info ─────────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(280), unique=True, index=True, nullable=False)
    short_description: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Pricing ───────────────────────────────────────────────────────────────
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_currency: Mapped[Optional[str]] = mapped_column(String(10), default="USD", nullable=True)
    original_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    is_on_sale: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Media ─────────────────────────────────────────────────────────────────
    thumbnail_url: Mapped[str] = mapped_column(String(500), nullable=False)
    preview_url: Mapped[Optional[str]] = mapped_column(String(500))  # live demo URL
    video_url: Mapped[Optional[str]] = mapped_column(String(500))
    gallery_images: Mapped[Optional[List[str]]] = mapped_column(StringList)

    # ── Taxonomy ──────────────────────────────────────────────────────────────
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tags: Mapped[Optional[List[str]]] = mapped_column(StringList)
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    color_scheme: Mapped[Optional[str]] = mapped_column(String(50))

    # ── Technical ─────────────────────────────────────────────────────────────
    framework: Mapped[Optional[TemplateFramework]] = mapped_column(SAEnum(TemplateFramework))
    pages_count: Mapped[int] = mapped_column(Integer, default=1)
    has_dark_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    is_responsive: Mapped[bool] = mapped_column(Boolean, default=True)
    is_rtl_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ai_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    compatibility: Mapped[Optional[List[str]]] = mapped_column(StringList)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")

    # ── License ───────────────────────────────────────────────────────────────
    license_type: Mapped[TemplateLicense] = mapped_column(
        SAEnum(TemplateLicense), default=TemplateLicense.REGULAR
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[TemplateStatus] = mapped_column(
        SAEnum(TemplateStatus), default=TemplateStatus.PUBLISHED, index=True
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_bestseller: Mapped[bool] = mapped_column(Boolean, default=False)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Statistics ────────────────────────────────────────────────────────────
    downloads_count: Mapped[int] = mapped_column(Integer, default=0)
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── Developer / Author ────────────────────────────────────────────────────
    developer_name: Mapped[Optional[str]] = mapped_column(String(200))
    developer_avatar: Mapped[Optional[str]] = mapped_column(String(500))

    # ── Seller / Owner ────────────────────────────────────────────────────────
    # Permanently links this template to the uploading seller's account.
    seller_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Download Assets ───────────────────────────────────────────────────────
    # JSON for flexible asset storage: {react: "url", html: "url", zip: "url"}
    download_assets: Mapped[Optional[dict]] = mapped_column(JSON)
    changelog: Mapped[Optional[dict]] = mapped_column(JSON)
    included_pages: Mapped[Optional[List[str]]] = mapped_column(StringList)

    # ── AI / Search ───────────────────────────────────────────────────────────
    # Qdrant vector ID (stored for sync)
    vector_id: Mapped[Optional[str]] = mapped_column(String(100))
    seo_keywords: Mapped[Optional[List[str]]] = mapped_column(StringList)

    # ── Relationships ─────────────────────────────────────────────────────────
    category: Mapped["Category"] = relationship(back_populates="templates")
    seller: Mapped[Optional["User"]] = relationship(back_populates="uploaded_templates", lazy="select")
    reviews: Mapped[List["Review"]] = relationship(back_populates="template", lazy="select", cascade="all, delete-orphan")
    wishlist_items: Mapped[List["WishlistItem"]] = relationship(back_populates="template", lazy="select", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="template", lazy="select", cascade="all, delete-orphan")
    order_items: Mapped[List["OrderItem"]] = relationship(back_populates="template", lazy="select", cascade="all, delete-orphan")
    downloads: Mapped[List["Download"]] = relationship(back_populates="template", lazy="select", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Template {self.title} [{self.status}]>"
