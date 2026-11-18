"""
Template Rights Service — single source of truth for template download,
watermarking, clean ZIP decisions, and deployment authorization.
Evaluates caller rights against the root marketplace template for forked/custom drafts.
"""

import uuid
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.template import Template, TemplateStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.models.user import User


async def rights_root(db: AsyncSession, template: Template) -> Optional[Template]:
    """
    Returns the originating marketplace template root.
    If the template is not a fork, returns the template itself.
    """
    fork_id = getattr(template, "forked_from_template_id", None)
    if not fork_id:
        return template
    return await db.get(Template, fork_id)


async def source_rights(
    db: AsyncSession, user: Optional[User], template: Template
) -> Tuple[bool, Optional[OrderItem], Optional[Template]]:
    """
    Single source of truth for download/clean/deploy authorization.
    Returns: (has_rights, order_item, root_template)
    """
    root = await rights_root(db, template)
    if user is None:
        return False, None, root

    role = str(getattr(user.role, "value", user.role)).lower()
    if role in ("admin", "super_admin"):
        return True, None, root

    if root is None:
        return False, None, None

    # Originating creator owns their original template
    if root.seller_id == user.id:
        return True, None, root

    # Free, published marketplace templates can be deployed or downloaded
    if root.is_free and root.status == TemplateStatus.PUBLISHED:
        return True, None, root

    # Check if caller has an active completed order for the root template
    stmt = (
        select(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            OrderItem.template_id == root.id,
            Order.user_id == user.id,
            Order.status == OrderStatus.COMPLETED,
        )
        .limit(1)
    )
    res = await db.execute(stmt)
    order_item = res.scalar_one_or_none()
    if order_item:
        return True, order_item, root

    return False, None, root
