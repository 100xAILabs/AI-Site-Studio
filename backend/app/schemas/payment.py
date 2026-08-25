"""
Payment Pydantic schemas.
"""

from typing import Optional
from pydantic import BaseModel

from app.models.payment import PaymentGateway


class PaymentInitRequest(BaseModel):
    order_id: str
    gateway: PaymentGateway = PaymentGateway.RAZORPAY


class PaymentInitResponse(BaseModel):
    """Returned to client after creating a payment order."""
    gateway: PaymentGateway
    gateway_order_id: str
    amount: int          # in smallest currency unit (paise / cents)
    currency: str
    key_id: str          # Razorpay key_id or Stripe publishable key
    order_id: str        # Our internal order ID
    upi_uri: Optional[str] = None
    vpa: Optional[str] = None
    merchant_name: Optional[str] = None


class PaymentVerifyRequest(BaseModel):
    """Sent by client after payment completion to verify signature."""
    gateway: PaymentGateway
    gateway_payment_id: str
    gateway_order_id: str
    gateway_signature: Optional[str] = None   # Razorpay HMAC signature
    order_id: str


class PaymentVerifyResponse(BaseModel):
    success: bool
    message: str
    order_id: Optional[str] = None
