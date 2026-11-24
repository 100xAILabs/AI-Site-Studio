"""
Orders routes.
"""

import uuid
import random
import string
import logging
from typing import List, Optional, Tuple, Dict, Any
from decimal import Decimal 

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.template import Template, TemplateStatus
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
    """Tax-inclusive pricing: all prices are all-inclusive with zero extra tax added."""
    return Decimal("0.00"), subtotal, "Tax Included (0%)", 0.0


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
    from app.models.license import License
    subtotal = Decimal("0")
    order_items = []

    # Batch prefetch templates and licenses to eliminate query loops
    template_ids = [item.template_id for item in data.items]
    t_res = await db.execute(
        select(Template).where(Template.id.in_(template_ids), Template.is_deleted.is_(False))
    )
    tmpls_by_id = {t.id: t for t in t_res.scalars().all()}

    lics_res = await db.execute(
        select(License.template_id).where(
            License.user_id == current_user.id,
            License.template_id.in_(template_ids),
            License.is_active == True,
        )
    )
    owned_ids = set(lics_res.scalars().all())

    for item_data in data.items:
        template = tmpls_by_id.get(item_data.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {item_data.template_id} not found",
            )
        if template.status != TemplateStatus.PUBLISHED:
            raise HTTPException(status_code=404, detail="This template is not available for purchase.")
        if template.seller_id == current_user.id:
            raise HTTPException(status_code=400, detail="You cannot purchase your own template.")

        # Prevent duplicate purchase of already owned template
        if template.id in owned_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You already own '{template.title}'. Access it anytime in your My Purchases library.",
            )

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

    # Resolve creator attribution for the order
    creator_obj = None
    if getattr(data, "creator_slug", None):
        try:
            c_slug = str(data.creator_slug).strip().lower()
            c_stmt = select(User).where(func.lower(User.creator_store_slug) == c_slug)
            c_res = await db.execute(c_stmt)
            creator_obj = c_res.scalar_one_or_none()
        except Exception as e_c:
            logger.info("Creator slug lookup notice: %s", e_c)

    # Fallback to seller of the first template if not found by slug
    if not creator_obj and order_items:
        first_tpl = order_items[0][0]
        if first_tpl.seller_id and first_tpl.seller_id != current_user.id:
            try:
                s_stmt = select(User).where(User.id == first_tpl.seller_id)
                s_res = await db.execute(s_stmt)
                creator_obj = s_res.scalar_one_or_none()
            except Exception as e_s:
                logger.info("Seller lookup notice: %s", e_s)

    # Gating: If purchasing through a creator whose payout/bank is not set up, block checkout
    if creator_obj and creator_obj.id != current_user.id and not getattr(creator_obj, "is_payout_setup_completed", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Purchasing from {creator_obj.creator_brand_name or 'this creator'} is temporarily paused: the creator has not connected their bank account or verified payout gateway yet."
        )

    # Auto-attribute client in user database if not already linked
    if creator_obj and creator_obj.id != current_user.id and not current_user.client_of_creator_id:
        current_user.client_of_creator_id = creator_obj.id
        current_user.client_of_creator_slug = creator_obj.creator_store_slug
        current_user.client_of_brand = creator_obj.creator_brand_name or creator_obj.username
        meta = dict(current_user.extra_metadata or {})
        meta["client_of_creator_id"] = str(creator_obj.id)
        meta["client_of_creator_slug"] = creator_obj.creator_store_slug
        meta["client_of_brand"] = creator_obj.creator_brand_name or creator_obj.username
        current_user.extra_metadata = meta

    order_meta = {
        "currency": primary_currency,
        "country_code": country_code,
        "tax_label": tax_label,
        "tax_rate": tax_rate_val,
    }
    if creator_obj:
        order_meta["creator_id"] = str(creator_obj.id)
        order_meta["creator_slug"] = creator_obj.creator_store_slug
        order_meta["creator_brand_name"] = creator_obj.creator_brand_name or creator_obj.username

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
        extra_metadata=order_meta,
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
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.template),
            selectinload(Order.payment),
            selectinload(Order.user),
        )
        .where(Order.id == order.id)
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
            selectinload(Order.payment),
            selectinload(Order.user),
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
        refreshed = await db.execute(query)
        order = refreshed.scalar_one()

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
