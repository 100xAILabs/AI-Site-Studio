"""
WithdrawalRequest ORM model.
"""

import uuid
import enum
from typing import Optional, TYPE_CHECKING
from decimal import Decimal

from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class WithdrawalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class WithdrawalRequest(UUIDMixin, TimestampMixin, Base):
    """Represents a withdrawal request submitted by a seller to claim their earnings."""

    __tablename__ = "withdrawal_requests"

    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    status: Mapped[WithdrawalStatus] = mapped_column(
        SAEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False, index=True
    )

    # Snapshot of bank details at the time the request was made
    bank_name: Mapped[Optional[str]] = mapped_column(String(255))
    account_number: Mapped[Optional[str]] = mapped_column(String(100))
    ifsc_code: Mapped[Optional[str]] = mapped_column(String(50))
    account_holder_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    seller: Mapped["User"] = relationship(
        "User", back_populates="withdrawal_requests", foreign_keys=[seller_id]
    )

    def __repr__(self) -> str:
        return f"<WithdrawalRequest amount={self.amount} status={self.status}>"
