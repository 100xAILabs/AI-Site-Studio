"""
Admin routes — platform-level management.
"""

from typing import Optional, List
from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.template import Template
from app.models.order import Order
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserResponse, UserAdminUpdate
from app.schemas.common import PaginatedResponse
import uuid

router = APIRouter()


@router.get("/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Platform-wide statistics and revenue calculations."""
    from app.models.template import Template, TemplateStatus
    from app.models.user import User as UserModel
    from app.models.order import Order as OrderModel, OrderStatus

    total_users = (await db.execute(select(func.count(UserModel.id)))).scalar_one()
    total_templates = (await db.execute(
        select(func.count(Template.id)).where(Template.status == TemplateStatus.PUBLISHED)
    )).scalar_one()
    pending_templates = (await db.execute(
        select(func.count(Template.id)).where(Template.status == TemplateStatus.DRAFT)
    )).scalar_one()
    total_orders = (await db.execute(select(func.count(OrderModel.id)))).scalar_one()

    # Calculate actual revenue from completed orders
    revenue_res = (await db.execute(
        select(func.sum(OrderModel.total)).where(OrderModel.status == OrderStatus.COMPLETED)
    )).scalar_one() or 0.0
    
    gross_revenue = float(revenue_res)
    commission_revenue = round(gross_revenue * 0.20, 2)
    net_seller_revenue = round(gross_revenue * 0.80, 2)

    return {
        "total_users": total_users,
        "total_templates": total_templates,
        "pending_templates": pending_templates,
        "total_orders": total_orders,
        "gross_revenue": gross_revenue,
        "commission_revenue": commission_revenue,
        "net_seller_revenue": net_seller_revenue,
    }


@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Get all templates, including drafts/reviews."""
    result = await db.execute(
        select(Template).order_by(Template.created_at.desc())
    )
    templates = result.scalars().all()
    return [{
        "id": t.id,
        "title": t.title,
        "slug": t.slug,
        "price": float(t.price),
        "status": t.status,
        "framework": t.framework,
        "developer_name": t.developer_name or "Unknown",
        "downloads_count": t.downloads_count,
        "views_count": t.views_count,
    } for t in templates]


@router.patch("/templates/{template_id}/status")
async def update_template_status(
    template_id: uuid.UUID,
    status: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Approve/reject (publish/draft) a template in the queue."""
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
        "id": template.id,
        "title": template.title,
        "status": template.status
    }


@router.get("/users", response_model=PaginatedResponse[UserResponse])
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
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 1,
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
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
        "buyer_email": o.user.email,
        "total": float(o.total),
        "status": o.status,
        "created_at": o.created_at.isoformat(),
        "items": [item.template.title for item in o.items if item.template]
    } for o in orders]


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

    return {
        "sellers_count": sellers_count,
        "buyers_count": buyers_count,
        "total_templates": total_templates,
        "total_deployments": total_deployments,
        "active_live_deployments": active_deployments,
        "gross_sales_usd": float(gross_sales),
        "platform_fee_revenue_usd": round(float(gross_sales) * 0.20, 2),
    }
