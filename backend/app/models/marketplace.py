"""
Creator Marketplace ORM Models — Platform settings and creator earnings ledger.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Text, Boolean, Integer, Numeric, DateTime,
    ForeignKey, Uuid, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.template import Template
    from app.models.order import Order, OrderItem
    from app.models.withdrawal_request import WithdrawalRequest


class EarningStatus(str, enum.Enum):
    PENDING = "pending"       # Within dispute/refund holding period
    AVAILABLE = "available"   # Past holding period, available for withdrawal
    PAID = "paid"             # Successfully paid out to creator
    REFUNDED = "refunded"     # Order was refunded or reversed


class CreatorEarning(UUIDMixin, TimestampMixin, Base):
    """
    Individual earning ledger entry for each template sale,
    tracking gross amount, platform commission fee, creator net earning,
    and the dispute/refund holding period.
    """
    __tablename__ = "creator_earnings"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    gross_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    platform_commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("20.00"), nullable=False)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    net_creator_earning: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)

    holding_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[EarningStatus] = mapped_column(
        SAEnum(EarningStatus), default=EarningStatus.PENDING, nullable=False, index=True
    )

    payout_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("withdrawal_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_id])
    template: Mapped["Template"] = relationship("Template", foreign_keys=[template_id])
    order: Mapped["Order"] = relationship("Order", foreign_keys=[order_id])
    order_item: Mapped["OrderItem"] = relationship("OrderItem", foreign_keys=[order_item_id])
    withdrawal_request: Mapped[Optional["WithdrawalRequest"]] = relationship("WithdrawalRequest", foreign_keys=[payout_request_id])

    def __repr__(self) -> str:
        return f"<CreatorEarning order={self.order_id} creator={self.creator_id} net={self.net_creator_earning} [{self.status}]>"


class MarketplaceSetting(Base):
    """
    Global platform configuration for the Creator Marketplace.
    Singleton record with id='default'.
    """
    __tablename__ = "marketplace_settings"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default="default")
    platform_commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("20.00"), nullable=False)
    payout_holding_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    min_payout_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("10.00"), nullable=False)
    is_marketplace_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<MarketplaceSetting commission={self.platform_commission_percent}% holding_days={self.payout_holding_days}>"
