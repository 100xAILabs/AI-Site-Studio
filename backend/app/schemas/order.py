"""
Order Pydantic schemas.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel

from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    template_id: uuid.UUID
    license_type: str = "regular"


class OrderCreate(BaseModel):
    items: List[OrderItemCreate]
    coupon_code: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    quantity: int
    price: Decimal
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    slug: Optional[str] = None
    preview_url: Optional[str] = None

    model_config = {"from_attributes": True}


class OrderUserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    status: OrderStatus
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    coupon_code: Optional[str] = None
    items: List[OrderItemResponse] = []
    user: Optional[OrderUserResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
