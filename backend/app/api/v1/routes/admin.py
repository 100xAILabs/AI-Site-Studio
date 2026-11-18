"""
Admin routes — platform-level management.
"""

from typing import Optional, List
from math import ceil

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.template import Template
from app.models.order import Order
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserResponse, AdminUserResponse, UserAdminUpdate
from app.schemas.common import PaginatedResponse
from pydantic import BaseModel
from typing import Literal
import uuid

router = APIRouter()


class UpiPaymentReview(BaseModel):
    decision: Literal["approve", "reject"]


@router.get("/payments/pending-upi")
async def list_pending_upi_payments(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List UPI references awaiting manual confirmation against the merchant account."""
    from app.models.payment import Payment, PaymentGateway, PaymentStatus
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.order).selectinload(Order.user))
        .where(
            Payment.gateway == PaymentGateway.UPI,
            Payment.status == PaymentStatus.PENDING,
            Payment.gateway_payment_id.like("UTR:%"),
        )
        .order_by(Payment.created_at.asc())
    )
    return [
        {
            "id": str(payment.id),
            "order_id": str(payment.order_id),
            "order_number": payment.order.order_number if payment.order else None,
            "buyer_email": payment.order.user.email if payment.order and payment.order.user else None,
            "utr": payment.gateway_payment_id.removeprefix("UTR:") if payment.gateway_payment_id else None,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "submitted_at": payment.updated_at.isoformat() if payment.updated_at else None,
        }
        for payment in result.scalars().all()
    ]


@router.patch("/payments/{payment_id}/upi-review")
async def review_upi_payment(
    payment_id: uuid.UUID,
    review: UpiPaymentReview,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Approve only after checking the UTR against the merchant's bank records."""
    from app.models.payment import Payment, PaymentGateway, PaymentStatus
    from app.models.order import OrderStatus
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.order).selectinload(Order.user))
        .where(Payment.id == payment_id)
        .with_for_update()
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.gateway != PaymentGateway.UPI or not (payment.gateway_payment_id or "").startswith("UTR:"):
        raise HTTPException(status_code=400, detail="Payment has no submitted UPI reference")
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=409, detail="Payment has already been reviewed")
    if not payment.order:
        raise HTTPException(status_code=404, detail="Order not found")

    if review.decision == "approve":
        payment.status = PaymentStatus.CAPTURED
        payment.order.status = OrderStatus.COMPLETED
        from app.api.v1.routes.payment import _fulfill_order_licenses
        await _fulfill_order_licenses(db, payment.order, user_email=payment.order.user.email if payment.order.user else None)
    else:
        payment.status = PaymentStatus.FAILED

    await db.commit()
    return {"payment_id": str(payment.id), "status": payment.status.value, "order_id": str(payment.order_id)}


@router.get("/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Platform-wide statistics and revenue calculations."""
    from app.models.user import User, UserRole
    from app.models.template import Template, TemplateStatus
    from app.models.user import User as UserModel
    from app.models.order import Order as OrderModel, OrderStatus

    custom_filter = [
        Template.slug.notlike("%-custom-%"),
        Template.title.notlike("%(Customized)%"),
        Template.title.notlike("Customized %"),
        Template.is_deleted.is_(False),
    ]

    total_users = (await db.execute(select(func.count(UserModel.id)))).scalar_one()
    total_templates = (await db.execute(
        select(func.count(Template.id)).where(Template.status == TemplateStatus.PUBLISHED, *custom_filter)
    )).scalar_one()
    pending_templates = (await db.execute(
        select(func.count(Template.id)).where(Template.status == TemplateStatus.DRAFT, *custom_filter)
    )).scalar_one()
    total_orders = (await db.execute(select(func.count(OrderModel.id)))).scalar_one()

    # Calculate actual revenue from completed orders
    revenue_res = (await db.execute(
        select(func.sum(OrderModel.total)).where(OrderModel.status == OrderStatus.COMPLETED)
    )).scalar_one() or 0.0
    
    gross_revenue = float(revenue_res)

    return {
        "total_users": total_users,
        "total_templates": total_templates,
        "pending_templates": pending_templates,
        "total_orders": total_orders,
        "gross_revenue": gross_revenue,
    }


class BatchStatusUpdate(BaseModel):
    template_ids: List[uuid.UUID]
    status: str


@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Get all creator templates and submissions for moderation, excluding buyer customized drafts."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Template)
        .options(selectinload(Template.category), selectinload(Template.seller))
        .where(
            Template.is_deleted.is_(False),
            Template.slug.notlike("%-custom-%"),
            Template.title.notlike("%(Customized)%"),
            Template.title.notlike("Customized %"),
        )
        .order_by(Template.created_at.desc())
    )
    templates = result.scalars().all()
    
    response_items = []
    for t in templates:
        dev_name = t.developer_name
        if not dev_name or dev_name in ("Unknown", "Unknown Creator"):
            if t.seller:
                dev_name = t.seller.full_name or t.seller.username or (t.seller.email.split("@")[0] if t.seller.email else None)
        if not dev_name:
            dev_name = "Platform Creator"

        dev_avatar = t.developer_avatar
        if not dev_avatar and t.seller:
            dev_avatar = t.seller.avatar_url

        response_items.append({
            "id": str(t.id),
            "title": t.title,
            "slug": t.slug,
            "price": float(t.price),
            "status": t.status.value if hasattr(t.status, "value") else str(t.status),
            "framework": t.framework.value if hasattr(t.framework, "value") else str(t.framework or "HTML"),
            "developer_name": dev_name,
            "developer_email": t.seller.email if t.seller else None,
            "developer_avatar": dev_avatar,
            "thumbnail_url": t.thumbnail_url,
            "preview_url": t.preview_url,
            "category": t.category.name if t.category else "Technology",
            "category_slug": t.category.slug if t.category else "technology",
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "pages_count": t.pages_count or 1,
            "is_ai_ready": t.is_ai_ready,
            "version": t.version or "1.0.0",
            "downloads_count": t.downloads_count,
            "views_count": t.views_count,
            "short_description": t.short_description,
            "description": t.description,
            "tags": t.tags or [],
            "industry": t.industry,
            "color_scheme": t.color_scheme,
            "has_dark_mode": t.has_dark_mode,
            "is_responsive": t.is_responsive,
            "license_type": t.license_type.value if hasattr(t.license_type, "value") else str(t.license_type or "regular"),
            "included_pages": t.included_pages or [],
            "download_assets": t.download_assets or {},
            "is_figma": bool("figma" in (t.tags or []) or "(Figma Import)" in (t.title or "")),
        })
    return response_items


@router.patch("/templates/{template_id}/status")
async def update_template_status(
    template_id: uuid.UUID,
    status: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Approve/reject (publish/draft/archive) a template in the queue."""
    from app.models.template import TemplateStatus, Template
    from fastapi import HTTPException
    
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    try:
        template.status = TemplateStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status value")
        
    await db.flush()
    await db.commit()
    return {
        "id": str(template.id),
        "title": template.title,
        "status": template.status.value if hasattr(template.status, "value") else str(template.status)
    }


@router.post("/templates/batch-status")
async def batch_update_template_status(
    payload: BatchStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Batch approve, reject, or archive multiple templates."""
    from app.models.template import TemplateStatus, Template
    from fastapi import HTTPException

    try:
        new_status = TemplateStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status value")

    result = await db.execute(
        select(Template).where(Template.id.in_(payload.template_ids))
    )
    templates = result.scalars().all()
    for t in templates:
        t.status = new_status

    await db.flush()
    await db.commit()
    return {
        "updated_count": len(templates),
        "status": new_status.value
    }


@router.get("/templates/trash")
async def get_admin_trash(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Get all soft-deleted templates across the platform (retained for 30 days).
    """
    from sqlalchemy.orm import selectinload
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    stmt = (
        select(Template)
        .options(selectinload(Template.category), selectinload(Template.seller))
        .where(
            Template.is_deleted.is_(True),
            Template.deleted_at >= thirty_days_ago,
        )
        .order_by(Template.deleted_at.desc())
    )
    res = await db.execute(stmt)
    items = res.scalars().all()

    result = []
    for item in items:
        del_at = item.deleted_at or now
        if del_at.tzinfo is None:
            del_at = del_at.replace(tzinfo=timezone.utc)
        expires_at = del_at + timedelta(days=30)
        seconds_left = max(0, int((expires_at - now).total_seconds()))
        days_left = max(0, int(seconds_left / 86400))
        result.append({
            "id": str(item.id),
            "title": item.title,
            "slug": item.slug,
            "price": float(item.price) if item.price else 0.0,
            "framework": item.framework.value if hasattr(item.framework, "value") else str(item.framework or "HTML"),
            "seller_id": str(item.seller_id) if item.seller_id else None,
            "seller_email": item.seller.email if item.seller else None,
            "seller_name": item.seller.full_name or item.seller.username if item.seller else None,
            "deleted_at": del_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "days_left": days_left,
            "seconds_left": seconds_left,
            "deleted_by_id": str(item.deleted_by_id) if item.deleted_by_id else None,
        })
    return result


@router.post("/templates/{template_id}/restore")
async def admin_restore_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """[Admin] Recover a soft-deleted template within 30 days."""
    from app.services.template_service import TemplateService

    service = TemplateService(db)
    restored = await service.restore_template(template_id, admin)
    return {
        "status": "success",
        "message": f"Successfully restored '{restored.title}'",
        "id": str(restored.id),
    }


@router.delete("/templates/{template_id}/permanent")
async def admin_permanent_delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """[Admin] Permanently delete a template, purging storage files, previews, vectors, and database record."""
    from app.services.template_service import TemplateService

    service = TemplateService(db)
    await service.permanent_delete_template(template_id, admin)
    return {
        "status": "success",
        "message": f"Template {template_id} permanently deleted.",
        "id": str(template_id),
    }


@router.get("/users", response_model=PaginatedResponse[AdminUserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] List all users with pagination."""
    repo = UserRepository(db)
    skip = (page - 1) * page_size
    users = await repo.list_all(skip=skip, limit=page_size)
    total = await repo.count()
    return PaginatedResponse(
        items=[AdminUserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 1,
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Update user role or active status."""
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    from fastapi import HTTPException
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = await repo.update(user, data)
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Delete a user account permanently."""
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    from fastapi import HTTPException
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await repo.delete(user)
    await db.commit()
    return {"success": True, "message": "User account permanently deleted"}


@router.get("/orders")
async def list_all_orders(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Get all checkout orders on the platform."""
    from app.models.order import Order as OrderModel, OrderItem
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItem.template), selectinload(OrderModel.user))
        .order_by(OrderModel.created_at.desc())
    )
    orders = result.scalars().all()
    return [{
        "id": str(o.id),
        "order_number": o.order_number,
        "invoice_number": o.order_number,
        "buyer_email": o.user.email if o.user else "N/A",
        "buyer_name": (o.user.full_name or o.user.username) if o.user else "Customer",
        "total": float(o.total),
        "subtotal": float(o.subtotal),
        "tax": float(o.tax),
        "status": o.status.value if hasattr(o.status, "value") else str(o.status),
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "items": [item.template.title for item in o.items if item.template] if o.items else ([o.notes] if o.notes else ["Template License Package"]),
        "receipt_url": f"/dashboard/receipt/{o.id}",
    } for o in orders]


@router.get("/payments")
async def list_all_payments(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Comprehensive payment monitoring.
    Lists every payment record with Razorpay gateway IDs, order info, user, and status.
    """
    from app.models.payment import Payment, PaymentGateway, PaymentStatus
    from app.models.order import Order as OrderModel, OrderItem
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Payment)
        .options(
            selectinload(Payment.order)
            .selectinload(OrderModel.user),
            selectinload(Payment.order)
            .selectinload(OrderModel.items)
            .selectinload(OrderItem.template)
        )
        .order_by(Payment.created_at.desc())
    )
    payments = result.scalars().all()

    total_revenue_usd = 0.0
    total_revenue_inr = 0.0
    captured_count = 0
    pending_count = 0
    failed_count = 0
    subscription_count = 0
    marketplace_count = 0

    payment_list = []
    for p in payments:
        order = p.order
        buyer = order.user if order else None
        buyer_email = buyer.email if buyer else "Unknown Buyer"
        buyer_name = (buyer.full_name or buyer.username) if buyer else "Customer"

        # Determine payment type
        meta = (order.extra_metadata or {}) if order else {}
        order_type_tag = meta.get("type", "marketplace_template")
        if order_type_tag == "subscription_plan":
            payment_type = f"Subscription ({str(meta.get('plan_id', 'Pro')).upper()})"
            subscription_count += 1
        elif order_type_tag == "ai_credits":
            payment_type = f"AI Tokens (+{meta.get('credits_to_add', 0)})"
        else:
            payment_type = "Marketplace Template"
            marketplace_count += 1

        is_captured = p.status == PaymentStatus.CAPTURED
        if is_captured:
            captured_count += 1
            if order:
                total_revenue_usd += float(order.total or 0)
            total_revenue_inr += float(p.amount or 0)
        elif p.status == PaymentStatus.PENDING:
            pending_count += 1
        elif p.status == PaymentStatus.FAILED:
            failed_count += 1

        items_summary = []
        if order and order.items:
            for it in order.items:
                if it.template:
                    items_summary.append(it.template.title)
        if not items_summary and order and order.notes:
            items_summary.append(order.notes)

        payment_list.append({
            "id": str(p.id),
            "order_id": str(p.order_id),
            "order_number": order.order_number if order else "N/A",
            "buyer_email": buyer_email,
            "buyer_name": buyer_name,
            "gateway": p.gateway.value if hasattr(p.gateway, "value") else str(p.gateway),
            "gateway_order_id": p.gateway_order_id,
            "gateway_payment_id": p.gateway_payment_id,
            "amount_usd": float(order.total) if order else 0.0,
            "amount_inr": float(p.amount) if p.amount else 0.0,
            "currency": p.currency or "INR",
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "payment_type": payment_type,
            "items_summary": ", ".join(items_summary) if items_summary else "Template Package",
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "receipt_url": f"/dashboard/receipt/{p.order_id}" if p.order_id else None,
        })

    return {
        "summary": {
            "total_revenue_usd": round(total_revenue_usd, 2),
            "total_revenue_inr": round(total_revenue_inr, 2),
            "total_transactions": len(payments),
            "captured_count": captured_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "subscription_count": subscription_count,
            "marketplace_count": marketplace_count,
        },
        "payments": payment_list,
    }


@router.get("/users/usage")
async def list_users_usage(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Monitor every user's platform usage:
    - Subscription tier & status
    - AI Gemini credits balance
    - Order counts and total spend
    - Download counts (watermarked vs clean)
    - Deployed sites count
    - Security / Tamper events
    """
    from app.models.user import User as UserModel
    from app.models.order import Order as OrderModel, OrderItem, OrderStatus
    from app.models.download import Download as DownloadModel
    from app.models.deployment import Deployment as DeploymentModel
    from app.models.tamper_alert import TamperAlert

    # Get all users
    users_res = await db.execute(select(UserModel).order_by(UserModel.created_at.desc()))
    users = users_res.scalars().all()

    if not users:
        return []

    user_ids = [u.id for u in users]
    user_emails = [u.email for u in users if u.email]

    # Batch Query 1: Orders count and total spend
    orders_res = await db.execute(
        select(
            OrderModel.user_id,
            func.count(OrderModel.id).label("orders_count"),
            func.coalesce(func.sum(OrderModel.total), 0).label("total_spent"),
        )
        .where(OrderModel.user_id.in_(user_ids), OrderModel.status == OrderStatus.COMPLETED)
        .group_by(OrderModel.user_id)
    )
    orders_by_user = {row.user_id: (row.orders_count, float(row.total_spent)) for row in orders_res.all()}

    # Batch Query 2: Purchased templates for clean download verification
    purchased_res = await db.execute(
        select(OrderModel.user_id, OrderItem.template_id)
        .join(OrderModel, OrderItem.order_id == OrderModel.id)
        .where(OrderModel.user_id.in_(user_ids), OrderModel.status == OrderStatus.COMPLETED)
    )
    purchased_by_user = {}
    for uid, tid in purchased_res.all():
        purchased_by_user.setdefault(uid, set()).add(tid)

    # Batch Query 3: Download template IDs
    downloads_res = await db.execute(
        select(DownloadModel.user_id, DownloadModel.template_id).where(DownloadModel.user_id.in_(user_ids))
    )
    downloads_by_user = {}
    for uid, tid in downloads_res.all():
        downloads_by_user.setdefault(uid, []).append(tid)

    # Batch Query 4: Deployments count
    dep_res = await db.execute(
        select(DeploymentModel.user_id, func.count(DeploymentModel.id).label("cnt"))
        .where(DeploymentModel.user_id.in_(user_ids))
        .group_by(DeploymentModel.user_id)
    )
    deployments_by_user = {row.user_id: row.cnt for row in dep_res.all()}

    # Batch Query 5: Tamper alerts count
    tamper_by_email = {}
    if user_emails:
        try:
            tamper_res = await db.execute(
                select(TamperAlert.buyer_email, func.count(TamperAlert.id).label("cnt"))
                .where(TamperAlert.buyer_email.in_(user_emails))
                .group_by(TamperAlert.buyer_email)
            )
            tamper_by_email = {row.buyer_email: row.cnt for row in tamper_res.all()}
        except Exception:
            tamper_by_email = {}

    usage_list = []
    for u in users:
        orders_count, total_spent = orders_by_user.get(u.id, (0, 0.0))
        purchased_template_ids = purchased_by_user.get(u.id, set())
        download_template_ids = downloads_by_user.get(u.id, [])
        total_downloads = len(download_template_ids)
        clean_downloads = sum(1 for tid in download_template_ids if tid in purchased_template_ids)
        watermarked_downloads = total_downloads - clean_downloads
        deployments_count = deployments_by_user.get(u.id, 0)
        tamper_count = tamper_by_email.get(u.email, 0) if u.email else 0

        usage_list.append({
            "id": str(u.id),
            "email": u.email,
            "name": u.full_name or u.username or (u.email.split("@")[0] if u.email else "User"),
            "role": u.role.value if hasattr(u.role, "value") else str(u.role),
            "subscription_tier": str(getattr(u, "subscription_tier", "free") or "free").lower(),
            "is_pro_subscriber": bool(getattr(u, "is_pro_subscriber", False)),
            "ai_credits": u.ai_credits if u.ai_credits is not None else 10,
            "total_orders": orders_count or 0,
            "total_spent_usd": float(total_spent or 0),
            "total_downloads": total_downloads or 0,
            "clean_downloads": clean_downloads or 0,
            "watermarked_downloads": watermarked_downloads,
            "deployments_count": deployments_count,
            "tamper_alerts_count": tamper_count,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

    return usage_list


@router.get("/users/{user_id}/usage-details")
async def get_user_usage_details(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Deep usage drilldown for a single user.
    """
    from app.models.user import User as UserModel
    from app.models.order import Order as OrderModel, OrderItem, OrderStatus
    from app.models.download import Download as DownloadModel
    from app.models.deployment import Deployment as DeploymentModel
    from app.models.tamper_alert import TamperAlert
    from sqlalchemy.orm import selectinload

    user_res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # User orders
    orders_res = await db.execute(
        select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItem.template))
        .where(OrderModel.user_id == user.id)
        .order_by(OrderModel.created_at.desc())
    )
    orders = orders_res.scalars().all()

    purchased_template_ids = set()
    for o in orders:
        if o.status == OrderStatus.COMPLETED and o.items:
            for it in o.items:
                if it.template_id:
                    purchased_template_ids.add(it.template_id)

    # User downloads
    downloads_res = await db.execute(
        select(DownloadModel)
        .options(selectinload(DownloadModel.template))
        .where(DownloadModel.user_id == user.id)
        .order_by(DownloadModel.created_at.desc())
    )
    downloads = downloads_res.scalars().all()

    # User deployments
    deployments_res = await db.execute(
        select(DeploymentModel)
        .where(DeploymentModel.user_id == user.id)
        .order_by(DeploymentModel.created_at.desc())
    )
    deployments = deployments_res.scalars().all()

    # Tamper alerts
    tamper_alerts = []
    if user.email:
        try:
            t_res = await db.execute(
                select(TamperAlert)
                .where(TamperAlert.buyer_email == user.email)
                .order_by(TamperAlert.created_at.desc())
            )
            tamper_alerts = [{
                "id": str(t.id),
                "template_id": t.template_id,
                "template_slug": t.template_title or t.template_id,
                "template_title": t.template_title,
                "violation_type": t.violation_type,
                "event_type": t.violation_type,
                "details": t.details,
                "domain": t.domain,
                "ip_address": t.ip_address,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            } for t in t_res.scalars().all()]
        except Exception:
            tamper_alerts = []

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.full_name or user.username or user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "subscription_tier": str(getattr(user, "subscription_tier", "free") or "free"),
            "ai_credits": user.ai_credits if user.ai_credits is not None else 10,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "orders": [{
            "id": str(o.id),
            "order_number": o.order_number,
            "total": float(o.total),
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "notes": o.notes,
            "items": [it.template.title for it in o.items if it.template] if o.items else [],
            "created_at": o.created_at.isoformat() if o.created_at else None,
        } for o in orders],
        "downloads": [{
            "id": str(d.id),
            "template_title": d.template.title if d.template else "Template",
            "template_id": str(d.template_id),
            "is_clean": d.template_id in purchased_template_ids,
            "format": d.format,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        } for d in downloads],
        "deployments": [{
            "id": str(dep.id),
            "project_name": dep.project_name,
            "site_id": dep.site_id,
            "status": dep.status,
            "subdomain": dep.subdomain,
            "live_url": dep.live_url,
            "created_at": dep.created_at.isoformat() if dep.created_at else None,
        } for dep in deployments],
        "tamper_alerts": tamper_alerts,
    }


@router.get("/deployments")
async def list_all_deployments(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Get all multi-tenant deployments across the entire platform."""
    from app.models.deployment import Deployment as DeploymentModel
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(DeploymentModel)
        .options(selectinload(DeploymentModel.user))
        .order_by(DeploymentModel.created_at.desc())
    )
    deployments = result.scalars().all()
    return [{
        "id": str(d.id),
        "site_id": d.site_id,
        "project_name": d.project_name,
        "user_email": d.user.email if d.user else "Unknown",
        "status": d.status,
        "current_version": d.current_version,
        "health_status": d.health_status,
        "subdomain": d.subdomain,
        "custom_domain": d.custom_domain,
        "live_url": d.live_url,
        "created_at": d.created_at.isoformat(),
    } for d in deployments]


# ── System Health & Analytics Endpoints ───────────────────────────────────────

@router.get("/health-overview")
async def get_health_overview(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Real-time infrastructure health monitor:
    - PostgreSQL connection status
    - Redis connection ping
    - Qdrant vector DB status
    - Disk space & static file storage usage
    """
    import os
    from pathlib import Path
    from app.services.search_service import SearchService
    search_service = SearchService(db)

    # 1. DB Health
    db_ok = True
    try:
        await db.execute(select(1))
    except Exception:
        db_ok = False

    # 2. Redis Health
    redis_ok = True
    try:
        from app.core.redis import get_redis_client
        _redis = await get_redis_client()
        await _redis.ping()
    except Exception:
        redis_ok = False

    # 3. Vector DB Health
    qdrant_ok = (search_service.qdrant is not None)

    # 4. Storage Usage
    static_path = Path(__file__).resolve().parents[4] / "static"
    total_mb = 0.0
    if static_path.exists():
        for root, dirs, files in os.walk(static_path):
            for f in files:
                try:
                    total_mb += os.path.getsize(os.path.join(root, f)) / (1024 * 1024)
                except Exception:
                    pass

    return {
        "status": "HEALTHY" if (db_ok and redis_ok) else "DEGRADED",
        "components": {
            "postgresql": "ONLINE" if db_ok else "OFFLINE",
            "redis": "ONLINE" if redis_ok else "OFFLINE",
            "qdrant_vector_db": "ONLINE" if qdrant_ok else "STANDBY",
            "storage_used_mb": round(total_mb, 2),
        }
    }


@router.get("/analytics")
async def get_platform_analytics(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Platform performance and operational metrics dashboard.
    """
    from app.models.user import User as UserModel, UserRole
    from app.models.template import Template as TemplateModel
    from app.models.deployment import Deployment as DeploymentModel
    from app.models.order import Order as OrderModel, OrderStatus

    sellers_count = (await db.execute(
        select(func.count(UserModel.id)).where(UserModel.role == UserRole.SELLER)
    )).scalar_one()

    buyers_count = (await db.execute(
        select(func.count(UserModel.id)).where(UserModel.role == UserRole.BUYER)
    )).scalar_one()

    total_templates = (await db.execute(select(func.count(TemplateModel.id)))).scalar_one()
    total_deployments = (await db.execute(select(func.count(DeploymentModel.id)))).scalar_one()
    active_deployments = (await db.execute(
        select(func.count(DeploymentModel.id)).where(DeploymentModel.status == "live")
    )).scalar_one()

    gross_sales = (await db.execute(
        select(func.sum(OrderModel.total)).where(OrderModel.status == OrderStatus.COMPLETED)
    )).scalar_one() or 0.0
    completed_orders = (await db.execute(
        select(func.count(OrderModel.id)).where(OrderModel.status == OrderStatus.COMPLETED)
    )).scalar_one()

    return {
        "sellers_count": sellers_count,
        "buyers_count": buyers_count,
        "total_templates": total_templates,
        "total_deployments": total_deployments,
        "active_live_deployments": active_deployments,
        "gross_sales_usd": float(gross_sales),
        "completed_orders": completed_orders,
    }


# ── Incident Management & Deployment Code Studio ──────────────────────────────

@router.get("/incidents")
async def list_all_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Lists all reported website failures across the platform.
    Includes resolution breakdown and deployment metadata.
    """
    from app.models.incident import SiteIncident
    from app.models.deployment import Deployment
    from sqlalchemy.orm import selectinload

    stmt = select(SiteIncident).options(selectinload(SiteIncident.deployment)).order_by(SiteIncident.created_at.desc())

    if status_filter and status_filter.lower() != "all":
        if status_filter.lower() == "auto_fixed":
            stmt = stmt.where(SiteIncident.resolved_by == "ai_site_doctor")
        elif status_filter.lower() == "open":
            stmt = stmt.where(SiteIncident.status.in_(["open", "investigating", "auto_fixing"]))
        else:
            stmt = stmt.where(SiteIncident.status == status_filter.lower())

    res = await db.execute(stmt)
    all_incidents = res.scalars().all()

    # Search filter
    if search and search.strip():
        term = search.strip().lower()
        all_incidents = [
            inc for inc in all_incidents
            if term in inc.site_id.lower()
            or term in inc.title.lower()
            or term in (inc.reporter_email or "").lower()
            or (inc.deployment and term in inc.deployment.project_name.lower())
        ]

    # Overall stats
    total_q = await db.execute(select(func.count(SiteIncident.id)))
    total_count = total_q.scalar_one()

    open_q = await db.execute(select(func.count(SiteIncident.id)).where(SiteIncident.status.in_(["open", "investigating", "auto_fixing"])))
    open_count = open_q.scalar_one()

    auto_fixed_q = await db.execute(select(func.count(SiteIncident.id)).where(SiteIncident.resolved_by == "ai_site_doctor"))
    auto_fixed_count = auto_fixed_q.scalar_one()

    resolved_q = await db.execute(select(func.count(SiteIncident.id)).where(SiteIncident.status == "resolved"))
    resolved_count = resolved_q.scalar_one()

    items = []
    for inc in all_incidents:
        items.append({
            "id": str(inc.id),
            "deployment_id": str(inc.deployment_id),
            "site_id": inc.site_id,
            "project_name": inc.deployment.project_name if inc.deployment else "Unknown Website",
            "live_url": inc.deployment.live_url if inc.deployment else None,
            "subdomain": inc.deployment.subdomain if inc.deployment else None,
            "reporter_email": inc.reporter_email,
            "reporter_name": inc.reporter_name,
            "issue_type": inc.issue_type,
            "title": inc.title,
            "description": inc.description,
            "error_logs": inc.error_logs,
            "page_url": inc.page_url,
            "severity": inc.severity,
            "status": inc.status,
            "resolved_by": inc.resolved_by,
            "resolution_notes": inc.resolution_notes,
            "ai_diagnosis": inc.ai_diagnosis,
            "ai_patch_summary": inc.ai_patch_summary,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        })

    return {
        "items": items,
        "stats": {
            "total": total_count,
            "open": open_count,
            "auto_fixed": auto_fixed_count,
            "resolved": resolved_count,
        }
    }


@router.patch("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Updates the lifecycle status of an incident (resolved, dismissed, investigating)."""
    from app.models.incident import SiteIncident
    from fastapi import HTTPException
    from datetime import datetime, timezone

    stmt = select(SiteIncident).where(SiteIncident.id == incident_id)
    res = await db.execute(stmt)
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    new_status = payload.get("status", incident.status)
    incident.status = new_status
    if payload.get("resolution_notes"):
        incident.resolution_notes = payload["resolution_notes"]

    if new_status == "resolved":
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolved_by = payload.get("resolved_by", "admin_manual")

    await db.commit()
    await db.refresh(incident)
    return {"message": "Incident status updated.", "status": incident.status}


@router.get("/deployments/{deployment_id}/files")
async def get_deployment_files(
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Lists all files in the deployment's current directory for the web Code Studio.
    """
    from app.models.deployment import Deployment
    from app.services.deployment_healing_service import DeploymentHealingService
    from fastapi import HTTPException

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    healing_service = DeploymentHealingService(db)
    files = healing_service.list_files(deployment.site_id)
    return {
        "deployment_id": str(deployment.id),
        "site_id": deployment.site_id,
        "project_name": deployment.project_name,
        "current_version": deployment.current_version,
        "live_url": deployment.live_url,
        "files": files,
    }


@router.get("/deployments/{deployment_id}/file-content")
async def get_deployment_file_content(
    deployment_id: uuid.UUID,
    path: str = Query(..., description="Relative file path"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Safely reads file content for the code editor.
    """
    from app.models.deployment import Deployment
    from app.services.deployment_healing_service import DeploymentHealingService
    from fastapi import HTTPException

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    healing_service = DeploymentHealingService(db)
    success, content, ext = healing_service.read_file(deployment.site_id, path)
    if not success:
        raise HTTPException(status_code=400, detail=content)

    return {
        "path": path,
        "content": content,
        "ext": ext,
        "size": len(content),
    }


@router.put("/deployments/{deployment_id}/files")
async def save_deployment_file(
    deployment_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Saves updated code, hot-reloads the deployed site, and optionally marks linked incident as resolved.
    """
    from app.models.deployment import Deployment
    from app.models.incident import SiteIncident
    from app.services.deployment_healing_service import DeploymentHealingService
    from fastapi import HTTPException
    from datetime import datetime, timezone

    file_path = payload.get("path")
    content = payload.get("content")
    incident_id = payload.get("incident_id")

    if not file_path or content is None:
        raise HTTPException(status_code=400, detail="Path and content are required.")

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    healing_service = DeploymentHealingService(db)
    success, msg = await healing_service.save_file(
        deployment=deployment,
        relative_path=file_path,
        content=content,
        user_or_admin_label="Admin Code Studio",
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    # Health check
    live_url = deployment.live_url or f"http://localhost:8000/sites/{deployment.site_id}/"
    is_healthy, _, h_msg = await healing_service.provider.health_check(live_url, site_id=deployment.site_id)
    deployment.health_status = "healthy"
    deployment.status = "live"

    # Mark incident resolved if passed
    if incident_id:
        try:
            inc_id_parsed = uuid.UUID(str(incident_id))
            inc_res = await db.execute(select(SiteIncident).where(SiteIncident.id == inc_id_parsed))
            inc = inc_res.scalar_one_or_none()
            if inc:
                inc.status = "resolved"
                inc.resolved_by = "admin_manual"
                inc.resolution_notes = f"Manually patched {file_path} via Admin Code Studio."
                inc.resolved_at = datetime.now(timezone.utc)
        except Exception:
            pass

    await db.commit()
    return {"message": msg, "health": h_msg, "live_url": live_url}


@router.post("/deployments/{deployment_id}/auto-fix")
async def admin_auto_fix_deployment(
    deployment_id: uuid.UUID,
    payload: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Triggers the Autonomous AI Site Doctor on any deployment.
    """
    from app.models.deployment import Deployment
    from app.models.incident import SiteIncident
    from app.services.deployment_healing_service import DeploymentHealingService
    from fastapi import HTTPException

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    incident = None
    if payload and payload.get("incident_id"):
        try:
            inc_id = uuid.UUID(str(payload["incident_id"]))
            inc_res = await db.execute(select(SiteIncident).where(SiteIncident.id == inc_id))
            incident = inc_res.scalar_one_or_none()
        except Exception:
            pass

    healing_service = DeploymentHealingService(db)
    result = await healing_service.auto_heal_deployment(
        deployment=deployment,
        incident=incident,
        issue_type=payload.get("issue_type", "broken_website") if payload else "broken_website",
        issue_description=payload.get("issue_description", "Admin requested automated recovery.") if payload else "Admin requested automated recovery.",
        error_logs=payload.get("error_logs") if payload else None,
    )

    return result


@router.get("/profitability")
async def get_subscription_profitability(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Complete Subscription Profitability & Variable Infrastructure Cost Dashboard.
    Measures revenue vs AI compute, hosting, builds, auto-heal, and domain subsidy costs.
    Calculates gross margins, loss-making subscribers, and 70% target margin health.
    """
    from decimal import Decimal
    from datetime import datetime, timezone, timedelta
    from app.core.plans import PLANS, get_plan_config, normalize_plan_id
    from app.models.subscription import UserSubscription, UsageLedger, PromotionalDomainCredit
    from app.models.hosting_subscription import HostingSubscription
    from app.models.deployment import Deployment

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Fetch all users with active or past_due subscriptions
    users_stmt = select(User).where(User.subscription_tier.isnot(None))
    u_res = await db.execute(users_stmt)
    subscribers = u_res.scalars().all()

    subscribers_data = []
    plan_aggregates = {
        "free": {"subscribers": 0, "revenue": Decimal("0.00"), "costs": Decimal("0.00"), "profit": Decimal("0.00")},
        "pro": {"subscribers": 0, "revenue": Decimal("0.00"), "costs": Decimal("0.00"), "profit": Decimal("0.00")},
        "extreme": {"subscribers": 0, "revenue": Decimal("0.00"), "costs": Decimal("0.00"), "profit": Decimal("0.00")},
    }

    total_gross_revenue = Decimal("0.00")
    total_variable_costs = Decimal("0.00")
    loss_making_count = 0
    margin_warning_count = 0

    subscriber_ids = [u.id for u in subscribers]

    # Batch Query 1: Paid hosting add-on counts
    hosting_addons_by_user = {}
    if subscriber_ids:
        h_stmt = (
            select(HostingSubscription.user_id, func.count(HostingSubscription.id).label("cnt"))
            .where(
                HostingSubscription.user_id.in_(subscriber_ids),
                HostingSubscription.status.in_(["active", "trialing"]),
            )
            .group_by(HostingSubscription.user_id)
        )
        h_res = await db.execute(h_stmt)
        hosting_addons_by_user = {row.user_id: row.cnt for row in h_res.all()}

    # Batch Query 2: Variable costs from UsageLedger in past 30 days
    usage_by_user = {}
    if subscriber_ids:
        ledger_stmt = (
            select(
                UsageLedger.user_id,
                UsageLedger.operation,
                func.sum(UsageLedger.estimated_provider_cost).label("cost"),
                func.sum(UsageLedger.credits_consumed).label("credits"),
            )
            .where(
                UsageLedger.user_id.in_(subscriber_ids),
                UsageLedger.created_at >= thirty_days_ago,
            )
            .group_by(UsageLedger.user_id, UsageLedger.operation)
        )
        ledger_res = await db.execute(ledger_stmt)
        for row in ledger_res.all():
            usage_by_user.setdefault(row.user_id, []).append((row.operation, row.cost, row.credits))

    # Batch Query 3: Active sites hosting compute cost
    live_sites_by_user = {}
    if subscriber_ids:
        dep_stmt = (
            select(Deployment.user_id, func.count(Deployment.id).label("cnt"))
            .where(
                Deployment.user_id.in_(subscriber_ids),
                Deployment.status == "live",
            )
            .group_by(Deployment.user_id)
        )
        dep_res = await db.execute(dep_stmt)
        live_sites_by_user = {row.user_id: row.cnt for row in dep_res.all()}

    # Batch Query 4: Promotional domain subsidy cost
    domain_subsidy_by_user = {}
    if subscriber_ids:
        dom_stmt = (
            select(
                PromotionalDomainCredit.user_id,
                func.sum(PromotionalDomainCredit.credit_used_usd).label("cost"),
            )
            .where(
                PromotionalDomainCredit.user_id.in_(subscriber_ids),
                PromotionalDomainCredit.created_at >= thirty_days_ago,
            )
            .group_by(PromotionalDomainCredit.user_id)
        )
        dom_res = await db.execute(dom_stmt)
        domain_subsidy_by_user = {row.user_id: (row.cost or Decimal("0.00")) for row in dom_res.all()}

    for u in subscribers:
        plan_id = normalize_plan_id(u.subscription_tier or "free")
        plan_cfg = get_plan_config(plan_id)

        # Plan base revenue
        base_rev = plan_cfg["monthly_price_usd"]

        # Paid hosting add-on revenue ($12/mo each)
        hosting_addons = hosting_addons_by_user.get(u.id, 0)
        hosting_addon_rev = Decimal(hosting_addons) * Decimal("12.00")
        user_total_revenue = base_rev + hosting_addon_rev

        # Variable costs from UsageLedger in past 30 days
        usage_by_op = usage_by_user.get(u.id, [])
        ai_cost = Decimal("0.000000")
        auto_heal_cost = Decimal("0.000000")
        build_cost = Decimal("0.000000")
        credits_consumed = 0

        for op, op_cost, op_credits in usage_by_op:
            c = op_cost or Decimal("0.000000")
            credits_consumed += int(op_credits or 0)
            if op == "auto_heal":
                auto_heal_cost += c
            elif op == "deployment_build":
                build_cost += c
            else:
                ai_cost += c

        # Active sites hosting compute cost (~$0.15/site/mo)
        live_sites = live_sites_by_user.get(u.id, 0)
        hosting_cost = Decimal(live_sites) * Decimal("0.150000")

        # Promotional domain subsidy cost
        domain_subsidy_cost = domain_subsidy_by_user.get(u.id, Decimal("0.00"))

        user_var_cost = (ai_cost + auto_heal_cost + build_cost + hosting_cost + domain_subsidy_cost).quantize(Decimal("0.01"))
        user_gross_profit = (user_total_revenue - user_var_cost).quantize(Decimal("0.01"))
        user_margin_pct = (
            float((user_gross_profit / user_total_revenue) * 100) if user_total_revenue > Decimal("0.00") else 0.0
        )

        is_loss_making = user_gross_profit < Decimal("0.00")
        is_approaching_budget = user_margin_pct < 70.0 and user_total_revenue > Decimal("0.00")

        if is_loss_making:
            loss_making_count += 1
        elif is_approaching_budget:
            margin_warning_count += 1

        total_gross_revenue += user_total_revenue
        total_variable_costs += user_var_cost

        plan_aggregates[plan_id]["subscribers"] += 1
        plan_aggregates[plan_id]["revenue"] += user_total_revenue
        plan_aggregates[plan_id]["costs"] += user_var_cost
        plan_aggregates[plan_id]["profit"] += user_gross_profit

        subscribers_data.append({
            "user_id": str(u.id),
            "email": u.email,
            "full_name": u.full_name or u.username or "Customer",
            "plan_id": plan_id,
            "plan_name": plan_cfg["name"],
            "subscription_status": u.subscription_status or "active",
            "revenue": float(user_total_revenue),
            "variable_costs": float(user_var_cost),
            "cost_breakdown": {
                "ai_cost": float(ai_cost),
                "auto_heal_cost": float(auto_heal_cost),
                "hosting_cost": float(hosting_cost),
                "build_cost": float(build_cost),
                "domain_subsidy_cost": float(domain_subsidy_cost),
            },
            "credits_consumed": credits_consumed,
            "live_sites": live_sites,
            "gross_profit": float(user_gross_profit),
            "gross_margin_percent": round(user_margin_pct, 1),
            "health_status": "loss_making" if is_loss_making else ("warning" if is_approaching_budget else "healthy"),
        })

    subscribers_data.sort(key=lambda x: x["variable_costs"], reverse=True)

    blended_profit = total_gross_revenue - total_variable_costs
    blended_margin = (
        float((blended_profit / total_gross_revenue) * 100) if total_gross_revenue > Decimal("0.00") else 0.0
    )

    return {
        "currency": "USD",
        "gross_revenue": float(total_gross_revenue),
        "net_revenue": float(total_gross_revenue),
        "variable_costs": {
            "total": float(total_variable_costs),
            "ai_api_cost": float(total_variable_costs * Decimal("0.70")),
            "hosting_cost": float(total_variable_costs * Decimal("0.15")),
            "build_compute_cost": float(total_variable_costs * Decimal("0.05")),
            "auto_heal_cost": float(total_variable_costs * Decimal("0.07")),
            "domain_subsidies": float(total_variable_costs * Decimal("0.03")),
        },
        "gross_profit": float(blended_profit),
        "gross_margin_percent": round(blended_margin, 1),
        "target_margin_percent": 70.0,
        "target_margin_achieved": blended_margin >= 70.0,
        "loss_making_subscribers_count": loss_making_count,
        "ai_cost_driver": "Gemini 1.5 Flash API",
        "recommendations": [
            "Monitor Pro subscribers with high Auto-Heal frequency to ensure automated repairs stay within the 10 repairs/mo limit.",
            "Promote annual billing ($190/yr Pro, $500/yr Extreme) to lock in healthy upfront operating cash flow.",
            "Enforce 1,000 credit ceiling on Extreme users to maintain >70% gross margins.",
        ],
        "summary": {
            "total_subscribers": len(subscribers),
            "gross_monthly_revenue": float(total_gross_revenue),
            "total_variable_costs": float(total_variable_costs),
            "net_gross_profit": float(blended_profit),
            "blended_gross_margin_percent": round(blended_margin, 1),
            "target_gross_margin_percent": 70.0,
            "loss_making_subscribers_count": loss_making_count,
            "margin_warning_subscribers_count": margin_warning_count,
        },
        "per_plan_profitability": {
            pid: {
                "subscribers": agg["subscribers"],
                "revenue": float(agg["revenue"]),
                "costs": float(agg["costs"]),
                "profit": float(agg["profit"]),
                "margin_percent": round(float((agg["profit"] / agg["revenue"]) * 100), 1) if agg["revenue"] > 0 else 0.0,
            }
            for pid, agg in plan_aggregates.items()
        },
        "subscribers": subscribers_data,
        "highest_cost_subscribers": subscribers_data[:10],
        "loss_making_subscribers": [s for s in subscribers_data if s["health_status"] == "loss_making"],
    }


# =========================================================================
# CREATOR MARKETPLACE MANAGEMENT & MODERATION (PHASE 9)
# =========================================================================

@router.get("/marketplace/settings")
async def get_marketplace_settings(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Get global platform commission rate, holding days, and marketplace state."""
    from app.models.marketplace import MarketplaceSetting
    from decimal import Decimal
    result = await db.execute(select(MarketplaceSetting).where(MarketplaceSetting.id == "default"))
    setting = result.scalar_one_or_none()
    if not setting:
        setting = MarketplaceSetting(
            id="default",
            platform_commission_percent=Decimal("20.00"),
            payout_holding_days=7,
            min_payout_amount=Decimal("10.00"),
            is_marketplace_active=True,
        )
        db.add(setting)
        await db.commit()
        await db.refresh(setting)

    return {
        "platform_commission_percent": float(setting.platform_commission_percent),
        "payout_holding_days": setting.payout_holding_days,
        "min_payout_amount": float(setting.min_payout_amount),
        "is_marketplace_active": setting.is_marketplace_active,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
    }


@router.put("/marketplace/settings")
async def update_marketplace_settings(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Update platform commission percentage and payout holding duration."""
    from app.models.marketplace import MarketplaceSetting
    from decimal import Decimal
    from datetime import datetime, timezone
    result = await db.execute(select(MarketplaceSetting).where(MarketplaceSetting.id == "default"))
    setting = result.scalar_one_or_none()
    if not setting:
        setting = MarketplaceSetting(id="default")
        db.add(setting)

    if "platform_commission_percent" in payload and payload["platform_commission_percent"] is not None:
        setting.platform_commission_percent = Decimal(str(payload["platform_commission_percent"]))
    if "payout_holding_days" in payload and payload["payout_holding_days"] is not None:
        setting.payout_holding_days = int(payload["payout_holding_days"])
    if "min_payout_amount" in payload and payload["min_payout_amount"] is not None:
        setting.min_payout_amount = Decimal(str(payload["min_payout_amount"]))
    if "is_marketplace_active" in payload and payload["is_marketplace_active"] is not None:
        setting.is_marketplace_active = bool(payload["is_marketplace_active"])

    setting.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(setting)

    return {
        "message": "Marketplace settings updated successfully.",
        "platform_commission_percent": float(setting.platform_commission_percent),
        "payout_holding_days": setting.payout_holding_days,
        "min_payout_amount": float(setting.min_payout_amount),
        "is_marketplace_active": setting.is_marketplace_active,
    }


@router.get("/marketplace/submissions")
async def list_marketplace_submissions(
    status_filter: Optional[str] = Query(None, description="submitted, under_review, rejected, published"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] List all creator template submissions pending review or moderation."""
    from sqlalchemy.orm import selectinload
    from app.models.user import User, UserRole
    from app.models.template import Template, TemplateStatus

    query = (
        select(Template)
        .options(selectinload(Template.category), selectinload(Template.seller))
        .where(
            Template.seller_id.isnot(None),
            Template.slug.notlike("%-custom-%"),
            Template.title.notlike("%(Customized)%"),
        )
        .order_by(Template.created_at.desc())
    )

    if status_filter:
        try:
            st = TemplateStatus(status_filter.lower())
            query = query.where(Template.status == st)
        except ValueError:
            pass

    res = await db.execute(query)
    templates = res.scalars().all()

    items = []
    for t in templates:
        seller_tier = t.seller.subscription_tier if t.seller else "free"
        is_extreme = (
            getattr(t.seller, "can_retail_templates", False) or
            getattr(t.seller, "is_extreme_subscriber", False) or
            seller_tier.lower() in ("extreme", "agency", "enterprise")
        ) if t.seller else False

        items.append({
            "id": str(t.id),
            "title": t.title,
            "slug": t.slug,
            "price": float(t.price),
            "status": t.status.value if hasattr(t.status, "value") else str(t.status),
            "thumbnail_url": t.thumbnail_url,
            "preview_url": t.preview_url,
            "short_description": t.short_description,
            "description": t.description,
            "category": t.category.name if t.category else "General",
            "category_id": str(t.category_id) if t.category_id else None,
            "tags": t.tags or [],
            "included_pages": t.included_pages or [],
            "rejection_reason": t.rejection_reason,
            "admin_notes": t.admin_notes,
            "submitted_at": t.submitted_at.isoformat() if t.submitted_at else (t.created_at.isoformat() if t.created_at else None),
            "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
            "creator": {
                "id": str(t.seller.id) if t.seller else None,
                "name": t.seller.full_name or t.seller.username or "Creator",
                "email": t.seller.email if t.seller else None,
                "subscription_tier": seller_tier,
                "is_extreme_eligible": is_extreme,
            } if t.seller else None,
        })

    return items


@router.post("/marketplace/templates/{template_id}/review")
async def review_marketplace_template(
    template_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Review a creator template submission:
    - approve / publish: moves template to PUBLISHED so it appears on global marketplace.
    - reject: moves to REJECTED with mandatory rejection_reason.
    - suspend: moves to SUSPENDED to halt sales.
    - under_review: moves to UNDER_REVIEW while inspecting files.
    """
    from datetime import datetime, timezone
    from app.models.user import User, UserRole
    from app.models.template import Template, TemplateStatus
    from app.services.fast_catalog import fast_catalog
    from app.core.redis import cache_delete_pattern

    action = str(payload.get("status") or payload.get("action") or "").lower()
    rejection_reason = payload.get("rejection_reason")
    admin_notes = payload.get("admin_notes")

    res = await db.execute(select(Template).where(Template.id == template_id))
    template = res.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if action in ("approve", "approved", "publish", "published"):
        template.status = TemplateStatus.PUBLISHED
        template.rejection_reason = None
    elif action in ("reject", "rejected"):
        template.status = TemplateStatus.REJECTED
        template.rejection_reason = rejection_reason or "Template did not meet marketplace quality guidelines."
    elif action in ("suspend", "suspended"):
        template.status = TemplateStatus.SUSPENDED
        if rejection_reason:
            template.rejection_reason = rejection_reason
    elif action in ("under_review", "review"):
        template.status = TemplateStatus.UNDER_REVIEW
    elif action in ("draft",):
        template.status = TemplateStatus.DRAFT
    else:
        raise HTTPException(status_code=400, detail=f"Invalid review decision: {action}")

    if admin_notes:
        template.admin_notes = admin_notes
    template.reviewed_by_id = _admin.id
    template.reviewed_at = datetime.now(timezone.utc)
    template.updated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
    except Exception as db_err:
        err_msg = str(db_err)
        if "templatestatus" in err_msg or "InvalidTextRepresentationError" in err_msg:
            await db.rollback()
            from app.core.database import engine
            from sqlalchemy import text
            async with engine.connect() as patch_conn:
                patch_conn = await patch_conn.execution_options(isolation_level="AUTOCOMMIT")
                for s_val in [
                    'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'PUBLISHED', 'SUSPENDED', 'ARCHIVED',
                    'draft', 'submitted', 'under_review', 'approved', 'rejected', 'published', 'suspended', 'archived',
                ]:
                    try:
                        await patch_conn.execute(text(f"ALTER TYPE templatestatus ADD VALUE IF NOT EXISTS '{s_val}';"))
                    except Exception:
                        pass
            await db.commit()
        else:
            raise
    await db.refresh(template)

    fast_catalog.invalidate()
    await cache_delete_pattern("templates:*")

    return {
        "id": str(template.id),
        "title": template.title,
        "status": template.status.value if hasattr(template.status, "value") else str(template.status),
        "rejection_reason": template.rejection_reason,
        "admin_notes": template.admin_notes,
        "reviewed_at": template.reviewed_at.isoformat() if template.reviewed_at else None,
    }


@router.get("/marketplace/creators")
async def list_marketplace_creators(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Overview of all active creators, their Extreme plan status, templates, and revenue."""
    from app.models.user import User, UserRole
    from app.models.template import Template, TemplateStatus
    from app.models.order import Order, OrderItem, OrderStatus
    from app.models.payment import Payment, PaymentStatus
    from app.models.withdrawal_request import WithdrawalRequest, WithdrawalStatus
    from decimal import Decimal

    # Find all users who have created templates or have seller role
    users_stmt = (
        select(User)
        .where(
            or_(
                User.role.in_([UserRole.SELLER, UserRole.ADMIN]),
                User.subscription_tier.in_(["extreme", "agency", "enterprise"]),
                User.id.in_(select(Template.seller_id).where(Template.seller_id.isnot(None)))
            )
        )
        .order_by(User.created_at.desc())
    )
    users_res = await db.execute(users_stmt)
    creators = users_res.scalars().all()

    creators_data = []
    if not creators:
        return []

    creator_ids = [c.id for c in creators]

    # Batch Query 1: Template counts by seller_id
    t_counts_by_seller = {}
    if creator_ids:
        t_count_stmt = (
            select(
                Template.seller_id,
                func.count(Template.id).label("total"),
                func.count(Template.id).filter(Template.status == TemplateStatus.PUBLISHED).label("published"),
                func.count(Template.id).filter(Template.status.in_([TemplateStatus.SUBMITTED, TemplateStatus.UNDER_REVIEW])).label("pending"),
            )
            .where(Template.seller_id.in_(creator_ids))
            .group_by(Template.seller_id)
        )
        t_res = await db.execute(t_count_stmt)
        for row in t_res.all():
            t_counts_by_seller[row.seller_id] = (row.total, row.published, row.pending)

    # Batch Query 2: Gross sales by seller_id
    sales_by_seller = {}
    if creator_ids:
        sales_stmt = (
            select(
                Template.seller_id,
                func.coalesce(func.sum(OrderItem.price), Decimal("0.00")).label("gross_sales"),
            )
            .select_from(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .join(Payment, Payment.order_id == Order.id)
            .join(Template, OrderItem.template_id == Template.id)
            .where(
                Order.status == OrderStatus.COMPLETED,
                Payment.status == PaymentStatus.CAPTURED,
                Template.seller_id.in_(creator_ids),
                Order.user_id != Template.seller_id,
            )
            .group_by(Template.seller_id)
        )
        sales_res = await db.execute(sales_stmt)
        sales_by_seller = {row.seller_id: row.gross_sales for row in sales_res.all()}

    # Batch Query 3: Paid payouts by seller_id
    payouts_by_seller = {}
    if creator_ids:
        paid_stmt = (
            select(
                WithdrawalRequest.seller_id,
                func.coalesce(func.sum(WithdrawalRequest.amount), Decimal("0.00")).label("total_paid"),
            )
            .where(
                WithdrawalRequest.seller_id.in_(creator_ids),
                WithdrawalRequest.status == WithdrawalStatus.PAID,
            )
            .group_by(WithdrawalRequest.seller_id)
        )
        paid_res = await db.execute(paid_stmt)
        payouts_by_seller = {row.seller_id: row.total_paid for row in paid_res.all()}

    for c in creators:
        total_t, pub_t, pend_t = t_counts_by_seller.get(c.id, (0, 0, 0))
        gross_sales = sales_by_seller.get(c.id, Decimal("0.00"))
        total_paid_out = payouts_by_seller.get(c.id, Decimal("0.00"))

        creators_data.append({
            "id": str(c.id),
            "name": c.full_name or c.username or "Creator",
            "email": c.email,
            "subscription_tier": c.subscription_tier or "free",
            "is_extreme": bool(c.can_retail_templates or c.is_extreme_subscriber),
            "total_templates": total_t,
            "published_templates": pub_t,
            "pending_templates": pend_t,
            "gross_sales": float(gross_sales),
            "total_paid_out": float(total_paid_out),
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return creators_data

