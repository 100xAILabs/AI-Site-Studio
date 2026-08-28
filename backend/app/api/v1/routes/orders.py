"""
Orders routes.
"""

import uuid
import random
import string
from typing import List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatus
from app.repositories.template_repo import TemplateRepository
from app.schemas.order import OrderCreate, OrderResponse

router = APIRouter()


def _generate_order_number() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"ASS-{suffix}"


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new order. Returns the order with PENDING status ready for payment."""
    template_repo = TemplateRepository(db)
    subtotal = Decimal("0")
    order_items = []

    for item_data in data.items:
        template = await template_repo.get_by_id(item_data.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {item_data.template_id} not found",
            )
        subtotal += template.price
        order_items.append((template, item_data.license_type))

    order = Order(
        user_id=current_user.id,
        order_number=_generate_order_number(),
        status=OrderStatus.PENDING,
        subtotal=subtotal,
        discount=Decimal("0"),
        tax=Decimal("0"),
        total=subtotal,
        coupon_code=data.coupon_code,
        notes=data.notes,
    )
    db.add(order)
    await db.flush()

    for template, license_type in order_items:
        item = OrderItem(
            order_id=order.id,
            template_id=template.id,
            price=template.price,
            license_type=license_type,
        )
        db.add(item)

    await db.flush()
    await db.commit()
    
    refreshed = await db.execute(
        select(Order).options(selectinload(Order.items).selectinload(OrderItem.template)).where(Order.id == order.id)
    )
    return OrderResponse.model_validate(refreshed.scalar_one())


@router.get("", response_model=List[OrderResponse])
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all orders for the current user."""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.template),
            selectinload(Order.user)
        )
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return [OrderResponse.model_validate(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific order by UUID or order_number."""
    order_uuid = None
    try:
        order_uuid = uuid.UUID(str(order_id))
    except (ValueError, TypeError):
        pass

    query = (
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.template),
            selectinload(Order.user)
        )
    )
    if order_uuid:
        query = query.where(or_(Order.id == order_uuid, Order.order_number == str(order_id)))
    else:
        query = query.where(Order.order_number == str(order_id))

    result = await db.execute(query)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    user_role = getattr(current_user.role, "value", str(current_user.role)).lower()
    is_admin = user_role in ("admin", "super_admin")
    is_buyer = str(order.user_id) == str(current_user.id)
    is_seller_of_item = any(
        item.template and str(item.template.seller_id) == str(current_user.id)
        for item in (order.items or [])
    )

    if not (is_buyer or is_admin or is_seller_of_item):
        raise HTTPException(status_code=403, detail="Access denied to this order receipt")

    return OrderResponse.model_validate(order)
