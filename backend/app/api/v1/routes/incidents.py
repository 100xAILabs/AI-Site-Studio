"""
Incident Reporting & AI Auto-Healing Routes.
Allows visitors and site owners to report broken websites, view incident history,
and trigger autonomous zero-downtime healing via the AI Site Doctor.
"""

import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user_optional, get_current_user
from app.models.user import User
from app.models.deployment import Deployment, DeploymentLog
from app.models.incident import SiteIncident
from app.schemas.incident import (
    IncidentCreate,
    IncidentResponse,
    AutoFixRequest,
    AutoFixResponse,
)
from app.services.deployment_healing_service import DeploymentHealingService

router = APIRouter()


@router.post("/report/{deployment_id}", response_model=dict, status_code=status.HTTP_201_CREATED)
async def report_broken_website(
    deployment_id: uuid.UUID,
    payload: IncidentCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a broken website report for a deployment.
    Optionally triggers the AI Site Doctor immediately if auto_heal_with_ai is True.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    reporter_email = payload.reporter_email or (current_user.email if current_user else None)
    reporter_name = payload.reporter_name or (current_user.full_name if current_user else "Visitor")

    # Create Incident Record
    incident = SiteIncident(
        deployment_id=deployment.id,
        site_id=deployment.site_id,
        reporter_email=reporter_email,
        reporter_name=reporter_name,
        issue_type=payload.issue_type,
        title=payload.title,
        description=payload.description,
        error_logs=payload.error_logs,
        page_url=payload.page_url or deployment.live_url,
        severity=payload.severity,
        status="open",
    )
    db.add(incident)

    # Mark deployment health status as degraded
    deployment.health_status = "degraded"

    # Log report event
    db.add(DeploymentLog(
        deployment_id=deployment.id,
        level="WARN",
        message=f"[Incident Reported] {payload.title} ({payload.issue_type}) by {reporter_email or 'Visitor'}",
        timestamp=datetime.now(timezone.utc),
    ))

    await db.commit()
    await db.refresh(incident)

    auto_heal_result = None
    if payload.auto_heal_with_ai:
        healing_service = DeploymentHealingService(db)
        try:
            auto_heal_result = await healing_service.auto_heal_deployment(
                deployment=deployment,
                incident=incident,
                issue_type=payload.issue_type,
                issue_description=payload.description,
                error_logs=payload.error_logs,
                page_url=payload.page_url,
            )
        except Exception as e:
            auto_heal_result = {
                "success": False,
                "error_message": f"AI Site Doctor encountered an issue: {str(e)}",
            }

    return {
        "message": "Incident reported successfully.",
        "incident": IncidentResponse(
            id=incident.id,
            deployment_id=incident.deployment_id,
            site_id=incident.site_id,
            project_name=deployment.project_name,
            live_url=deployment.live_url,
            subdomain=deployment.subdomain,
            reporter_email=incident.reporter_email,
            reporter_name=incident.reporter_name,
            issue_type=incident.issue_type,
            title=incident.title,
            description=incident.description,
            error_logs=incident.error_logs,
            page_url=incident.page_url,
            severity=incident.severity,
            status=incident.status,
            resolved_by=incident.resolved_by,
            resolution_notes=incident.resolution_notes,
            ai_diagnosis=incident.ai_diagnosis,
            ai_patch_summary=incident.ai_patch_summary,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
            resolved_at=incident.resolved_at,
        ),
        "auto_heal_result": auto_heal_result,
    }


@router.post("/report-by-site/{site_id}", response_model=dict, status_code=status.HTTP_201_CREATED)
async def report_broken_website_by_site_id(
    site_id: str,
    payload: IncidentCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a failure report using the stable site_id (e.g. SITE-D80B07) or subdomain.
    Designed for error boundaries embedded in live sites.
    """
    clean_site_id = site_id.strip().upper()
    stmt = select(Deployment).where(
        (Deployment.site_id == clean_site_id) |
        (Deployment.subdomain == site_id.strip().lower())
    )
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail=f"No deployment found for site '{site_id}'.")

    return await report_broken_website(
        deployment_id=deployment.id,
        payload=payload,
        current_user=current_user,
        db=db,
    )


@router.get("/deployment/{deployment_id}", response_model=List[IncidentResponse])
async def list_deployment_incidents(
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Lists incident history for a specific deployment.
    """
    stmt = (
        select(SiteIncident)
        .where(SiteIncident.deployment_id == deployment_id)
        .order_by(desc(SiteIncident.created_at))
    )
    res = await db.execute(stmt)
    incidents = res.scalars().all()
    return incidents


@router.post("/deployments/{deployment_id}/auto-fix", response_model=AutoFixResponse)
async def auto_fix_deployment(
    deployment_id: uuid.UUID,
    payload: Optional[AutoFixRequest] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes the Autonomous AI Site Doctor on a deployment.
    Reads website files, prompts Gemini, patches broken code, tests health, and redeploys.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    incident = None
    if payload and payload.incident_id:
        inc_res = await db.execute(select(SiteIncident).where(SiteIncident.id == payload.incident_id))
        incident = inc_res.scalar_one_or_none()

    healing_service = DeploymentHealingService(db)
    result = await healing_service.auto_heal_deployment(
        deployment=deployment,
        incident=incident,
        issue_type="broken_website",
        issue_description=payload.issue_description if payload and payload.issue_description else "Automated failure recovery requested.",
        error_logs=payload.error_logs if payload else None,
    )

    return AutoFixResponse(
        success=result.get("success", False),
        incident_id=incident.id if incident else None,
        site_id=deployment.site_id,
        live_url=result.get("live_url"),
        diagnosis=result.get("diagnosis", "Autonomous diagnosis finished."),
        root_cause=result.get("root_cause"),
        patch_summary=result.get("patch_summary", "Site code updated."),
        patched_files=result.get("patched_files", []),
        health_status=result.get("health_status", "healthy"),
        error_message=result.get("error_message"),
    )
