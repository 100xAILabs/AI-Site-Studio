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
from pydantic import BaseModel
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

    custom_filter = [
        Template.slug.notlike("%-custom-%"),
        Template.title.notlike("%(Customized)%"),
        Template.title.notlike("Customized %"),
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
