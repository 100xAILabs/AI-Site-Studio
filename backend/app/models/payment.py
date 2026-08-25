"""
Payment ORM model.
"""

import enum
import uuid
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, JSON, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class PaymentGateway(str, enum.Enum):
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    UPI = "upi"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(UUIDMixin, TimestampMixin, Base):
    """Payment record linked to an order."""

    __tablename__ = "payments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    gateway: Mapped[PaymentGateway] = mapped_column(
        SAEnum(PaymentGateway, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False
    )

    # Gateway-specific IDs
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    gateway_order_id: Mapped[Optional[str]] = mapped_column(String(255))
    gateway_signature: Mapped[Optional[str]] = mapped_column(String(500))

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    # Raw webhook / response payload
    gateway_response: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="payment")

    def __repr__(self) -> str:
        return f"<Payment {self.gateway_payment_id} [{self.status}]>"
