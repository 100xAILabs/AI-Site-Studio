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
    gateway: PaymentGateway = PaymentGateway.RAZORPAY
    gateway_order_id: str
    amount: int          # in smallest currency unit (paise / cents)
    currency: str = "INR"
    key_id: str          # Razorpay key_id
    order_id: str        # Our internal order ID
    checkout_url: Optional[str] = None
    upi_uri: Optional[str] = None
    vpa: Optional[str] = None
    merchant_name: Optional[str] = None


class PaymentVerifyRequest(BaseModel):
    """Sent by client after payment completion to verify signature."""
    gateway: PaymentGateway = PaymentGateway.RAZORPAY
    gateway_payment_id: str
    gateway_order_id: str
    gateway_signature: Optional[str] = None   # Razorpay HMAC signature or verification token
    order_id: str
    upi_utr: Optional[str] = None


class PaymentVerifyResponse(BaseModel):
    success: bool
    message: str
    order_id: Optional[str] = None


class PurchaseTokensRequest(BaseModel):
    pack_id: str
    gateway: PaymentGateway = PaymentGateway.RAZORPAY


class PurchasePlanRequest(BaseModel):
    plan_id: str
    billing_cycle: str = "monthly"
    gateway: PaymentGateway = PaymentGateway.RAZORPAY
