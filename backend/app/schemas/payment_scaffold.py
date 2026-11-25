"""
Pydantic Schemas for Payment Engine and Scaffolding.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ScaffoldOrderItem(BaseModel):
    name: str
    unit_amount: float
    quantity: int = 1
    description: Optional[str] = None


class ScaffoldCheckoutRequest(BaseModel):
    order_id: Optional[str] = None
    amount: float = Field(..., gt=0, description="Total order amount")
    currency: str = Field(default="USD", max_length=3)
    items: List[ScaffoldOrderItem] = Field(default_factory=list)
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    provider: Optional[str] = "stripe"
    seller_id: Optional[str] = None
    destination_account: Optional[str] = None
    platform_fee_percent: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class ScaffoldCheckoutResponse(BaseModel):
    success: bool
    provider: str
    order_id: str
    session_id: str
    checkout_url: str
    amount: float
    currency: str
    publishable_key: Optional[str] = None
    client_secret: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class ScaffoldVerifyRequest(BaseModel):
    order_id: str
    payment_id: str
    signature: str
    provider: str = "stripe"


class ScaffoldVerifyResponse(BaseModel):
    valid: bool
    order_id: str
    payment_id: str
    provider: str
    status: str
    error: Optional[str] = None


class ScaffoldOrderStatusResponse(BaseModel):
    order_id: str
    status: str
    amount: float
    currency: str
    customer_email: Optional[str] = None
    created_at: Optional[str] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)


class ScaffoldWebhookResponse(BaseModel):
    status: str
    event_id: Optional[str] = None
    event_type: Optional[str] = None
    order_id: Optional[str] = None
    amount: Optional[float] = None
    provider: Optional[str] = None
