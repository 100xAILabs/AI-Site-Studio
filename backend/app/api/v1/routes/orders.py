"""
Orders routes.
"""

import uuid
import random
import string
from typing import List, Optional, Tuple, Dict, Any
from decimal import Decimal 

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.template import TemplateStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.repositories.template_repo import TemplateRepository
from app.schemas.order import OrderCreate, OrderResponse

router = APIRouter()


COUNTRY_TAX_RATES = {
    "IN": {"name": "India", "rate": Decimal("0.18"), "label": "GST (18%)"},
    "US": {"name": "United States", "rate": Decimal("0.08"), "label": "Sales Tax (8%)"},
    "GB": {"name": "United Kingdom", "rate": Decimal("0.20"), "label": "VAT (20%)"},
    "DE": {"name": "Germany", "rate": Decimal("0.19"), "label": "EU VAT (19%)"},
    "FR": {"name": "France", "rate": Decimal("0.20"), "label": "EU VAT (20%)"},
    "ES": {"name": "Spain", "rate": Decimal("0.21"), "label": "EU VAT (21%)"},
    "IT": {"name": "Italy", "rate": Decimal("0.22"), "label": "EU VAT (22%)"},
    "NL": {"name": "Netherlands", "rate": Decimal("0.21"), "label": "EU VAT (21%)"},
    "CA": {"name": "Canada", "rate": Decimal("0.13"), "label": "HST/GST (13%)"},
    "AU": {"name": "Australia", "rate": Decimal("0.10"), "label": "GST (10%)"},
    "SG": {"name": "Singapore", "rate": Decimal("0.09"), "label": "GST (9%)"},
    "JP": {"name": "Japan", "rate": Decimal("0.10"), "label": "JCT (10%)"},
    "AE": {"name": "United Arab Emirates", "rate": Decimal("0.05"), "label": "VAT (5%)"},
    "BR": {"name": "Brazil", "rate": Decimal("0.10"), "label": "Digital Tax (10%)"},
}

def calculate_country_tax(subtotal: Decimal, country_code: Optional[str] = None) -> tuple[Decimal, Decimal, str, float]:
    code = (country_code or "US").upper()
    info = COUNTRY_TAX_RATES.get(code, {"name": "Other", "rate": Decimal("0.10"), "label": "Digital Goods Tax (10%)"})
    rate = info["rate"]
    tax = (subtotal * rate).quantize(Decimal("0.01"))
    total = subtotal + tax
    return tax, total, info["label"], float(rate)


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
    if settings.TEMPLATE_DOWNLOADS_FREE:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Marketplace templates are free to download right now. Open a template and choose Free Download.",
        )
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
        if template.status != TemplateStatus.PUBLISHED:
            raise HTTPException(status_code=404, detail="This template is not available for purchase.")
        if template.seller_id == current_user.id:
            raise HTTPException(status_code=400, detail="You cannot purchase your own template.")
        subtotal += template.price
        # The listing defines the entitlement. Never let a buyer promote a regular
        # checkout to an extended license by editing the request payload.
        order_items.append((template, template.license_type.value))

    # Detect primary template currency (e.g. INR for ₹5 template)
    currencies = [str(getattr(t, "price_currency", "USD") or "USD").upper() for t, _ in order_items]
    if len(set(currencies)) != 1 or currencies[0] not in {"USD", "INR"}:
        raise HTTPException(status_code=400, detail="All items in an order must use the same supported currency (USD or INR).")
    primary_currency = currencies[0]

    country_code = (data.country_code or getattr(current_user, "country", None) or "US").upper()
    tax_amount, total_amount, tax_label, tax_rate_val = calculate_country_tax(subtotal, country_code)

    order = Order(
        user_id=current_user.id,
        order_number=_generate_order_number(),
        status=OrderStatus.PENDING,
        subtotal=subtotal,
        discount=Decimal("0"),
        tax=tax_amount,
        total=total_amount,
        coupon_code=data.coupon_code,
        notes=data.notes,
        extra_metadata={
            "currency": primary_currency,
            "country_code": country_code,
            "tax_label": tax_label,
            "tax_rate": tax_rate_val,
        },
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
            selectinload(Order.user),
            selectinload(Order.payment),
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

    # Persist immutable invoice metadata if missing
    meta = dict(order.extra_metadata or {})
    changed = False
    if "invoice_number" not in meta:
        meta["invoice_number"] = order.order_number
        meta["invoice_issued_at"] = order.created_at.isoformat() if order.created_at else None
        changed = True
    if changed:
        order.extra_metadata = meta
        await db.commit()

    resp = OrderResponse.model_validate(order)
    if not resp.items:
        item_title = order.notes or "Official AI Site Studio License Package"
        if order.extra_metadata and order.extra_metadata.get("type") == "ai_credits":
            credits = order.extra_metadata.get("credits_to_add", "")
            item_title = f"AI Gemini Compute Pack (+{credits} Credits)"
        elif order.extra_metadata and order.extra_metadata.get("type") == "subscription_plan":
            plan_id = order.extra_metadata.get("plan_id", "Pro")
            item_title = f"Site Studio Subscription: {str(plan_id).title()}"
        
        from app.schemas.order import OrderItemResponse
        resp.items = [
            OrderItemResponse(
                id=order.id,
                template_id=None,
                quantity=1,
                price=order.total,
                price_currency=(order.extra_metadata or {}).get("currency", "USD"),
                title=item_title,
                license_type="commercial",
                framework="Production Codebase",
                developer_name="Site Studio Creator",
            )
        ]

    return resp
