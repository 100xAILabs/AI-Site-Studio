"""
Order and OrderItem ORM models.
"""

import enum
import uuid
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, JSON, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.template import Template
    from app.models.payment import Payment


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Order(UUIDMixin, TimestampMixin, Base):
    """Represents a user purchase order."""

    __tablename__ = "orders"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False, index=True
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    coupon_code: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payment: Mapped[Optional["Payment"]] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Order {self.order_number} [{self.status}]>"


class OrderItem(UUIDMixin, TimestampMixin, Base):
    """Individual line item within an order."""

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.id", ondelete="RESTRICT"), nullable=False
    )

    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    license_type: Mapped[str] = mapped_column(String(50), default="regular")

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="items")
    template: Mapped["Template"] = relationship(back_populates="order_items")

    @property
    def title(self) -> Optional[str]:
        return self.template.title if self.template else "Template Package"

    @property
    def thumbnail_url(self) -> Optional[str]:
        return self.template.thumbnail_url if self.template else None

    @property
    def slug(self) -> Optional[str]:
        return self.template.slug if self.template else None

    @property
    def preview_url(self) -> Optional[str]:
        return self.template.preview_url if self.template else None
