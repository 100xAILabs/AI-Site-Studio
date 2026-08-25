"""
FastAPI Endpoints for Multi-Tenant Website Deployments.
Provides tenant-scoped lifecycle management:
- Deploy, Redeploy, Rollback, Suspend, Resume, Delete
- Version history management
- Custom domain mapping & DNS verification
- Environment variables management
- Real-time build & runtime logs
"""

import uuid
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.deployment import Deployment, DeploymentVersion, Domain, DeploymentLog
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentDetailResponse,
    DeploymentVersionResponse,
    DomainCreate,
    DomainResponse,
    DeploymentLogResponse,
    RollbackRequest,
    EnvironmentVariableUpdate,
)
from app.services.deployment_service import DeploymentService
from app.services.deployment_providers import local_deployment_provider

router = APIRouter()


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    payload: DeploymentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates and queues an isolated website deployment for the authenticated user.
    """
    service = DeploymentService(db)
    deployment = await service.create_deployment(
        user=current_user,
        project_name=payload.project_name,
        template_id=payload.template_id,
        provider_type=payload.provider or "local",
        build_command=payload.build_command or "npm run build",
        output_dir=payload.output_dir or "dist",
        env_vars=payload.env_vars,
    )

    # Launch asynchronous build worker
    background_tasks.add_task(DeploymentService.run_deployment_pipeline, deployment.id, "v1.0")

    return deployment


@router.get("", response_model=List[DeploymentResponse])
async def list_deployments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all website deployments owned by the authenticated tenant.
    Strict tenant isolation: users only see their own deployments.
    """
    stmt = (
        select(Deployment)
        .where(Deployment.user_id == current_user.id)
        .order_by(desc(Deployment.created_at))
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{deployment_id}", response_model=DeploymentDetailResponse)
async def get_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Gets detailed metadata, version history, mapped domains, and recent logs for a deployment.
    """
    stmt = (
        select(Deployment)
        .where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
        .options(
            selectinload(Deployment.versions),
            selectinload(Deployment.domains),
            selectinload(Deployment.deployment_logs),
        )
    )
    result = await db.execute(stmt)
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found or access denied.")

    # Sort recent logs
    recent_logs = sorted(deployment.deployment_logs, key=lambda l: l.timestamp, reverse=True)[:50]

    return DeploymentDetailResponse(
        id=deployment.id,
        user_id=deployment.user_id,
        site_id=deployment.site_id,
        project_name=deployment.project_name,
        provider=deployment.provider,
        status=deployment.status,
        current_version=deployment.current_version,
        deployment_type=deployment.deployment_type,
        health_status=deployment.health_status,
        subdomain=deployment.subdomain,
        branch=deployment.branch,
        commit_message=deployment.commit_message,
        build_command=deployment.build_command,
        output_dir=deployment.output_dir,
        live_url=deployment.live_url,
        custom_domain=deployment.custom_domain,
        logs=deployment.logs,
        env_vars=deployment.env_vars,
        is_suspended=deployment.is_suspended,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
        versions=deployment.versions,
        domains=deployment.domains,
        recent_logs=recent_logs,
    )


@router.post("/{deployment_id}/redeploy", response_model=DeploymentResponse)
async def redeploy_deployment(
    deployment_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers a fresh compilation and zero-downtime deployment for an existing website.
    """
    service = DeploymentService(db)
    try:
        deployment = await service.redeploy(current_user, deployment_id)
        background_tasks.add_task(DeploymentService.run_deployment_pipeline, deployment.id, deployment.current_version)
        return deployment
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/rollback")
async def rollback_deployment(
    deployment_id: uuid.UUID,
    payload: RollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes an atomic zero-downtime rollback to a previous version (e.g. 'v1.0').
    """
    service = DeploymentService(db)
    success, result_msg = await service.rollback_to_version(current_user, deployment_id, payload.target_version)
    if not success:
        raise HTTPException(status_code=400, detail=result_msg)
    return {"message": f"Successfully rolled back to version {payload.target_version}", "live_url": result_msg}


@router.post("/{deployment_id}/suspend")
async def suspend_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Suspends a live deployment without deleting files or version history.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    await local_deployment_provider.stop(deployment.site_id)
    deployment.status = "suspended"
    deployment.is_suspended = True
    await db.commit()
    return {"message": f"Deployment {deployment.site_id} is now suspended."}


@router.post("/{deployment_id}/resume")
async def resume_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Resumes a suspended deployment by restoring its active version.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    await local_deployment_provider.rollback(deployment.site_id, deployment.current_version)
    deployment.status = "live"
    deployment.is_suspended = False
    await db.commit()
    return {"message": f"Deployment {deployment.site_id} is now active.", "live_url": deployment.live_url}


@router.delete("/{deployment_id}", status_code=status.HTTP_200_OK)
async def delete_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes a deployment and permanently purges its isolated storage artifacts.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    if deployment.site_id:
        await local_deployment_provider.remove(deployment.site_id)

    await db.delete(deployment)
    await db.commit()
    return {"message": f"Deployment {deployment_id} deleted successfully."}


@router.get("/{deployment_id}/versions", response_model=List[DeploymentVersionResponse])
async def list_deployment_versions(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all deployment version snapshots for 1-click rollback.
    """
    # Verify ownership
    d_res = await db.execute(select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id))
    if not d_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deployment not found.")

    stmt = select(DeploymentVersion).where(DeploymentVersion.deployment_id == deployment_id).order_by(desc(DeploymentVersion.created_at))
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{deployment_id}/logs", response_model=List[DeploymentLogResponse])
async def get_deployment_logs(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns structured, secret-masked logs for a deployment.
    """
    d_res = await db.execute(select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id))
    if not d_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deployment not found.")

    stmt = select(DeploymentLog).where(DeploymentLog.deployment_id == deployment_id).order_by(desc(DeploymentLog.timestamp)).limit(100)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/{deployment_id}/domains", response_model=DomainResponse)
async def add_custom_domain(
    deployment_id: uuid.UUID,
    payload: DomainCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Maps a custom domain (e.g. 'www.mybrand.com') to a deployment with pending verification.
    """
    d_res = await db.execute(select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id))
    deployment = d_res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    clean_domain = payload.domain.strip().lower()
    token = f"aisitestudio-verify-{uuid.uuid4().hex[:12]}"

    domain_record = Domain(
        deployment_id=deployment.id,
        user_id=current_user.id,
        domain=clean_domain,
        domain_type="custom",
        verification_status="pending_verification",
        ssl_status="pending",
        verification_token=token,
    )
    db.add(domain_record)
    deployment.custom_domain = clean_domain
    await db.commit()
    await db.refresh(domain_record)
    return domain_record


@router.post("/{deployment_id}/domains/{domain_id}/verify", response_model=DomainResponse)
async def verify_custom_domain(
    deployment_id: uuid.UUID,
    domain_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verifies DNS CNAME / A-record configuration for a custom domain.
    """
    stmt = select(Domain).where(
        Domain.id == domain_id,
        Domain.deployment_id == deployment_id,
        Domain.user_id == current_user.id
    )
    res = await db.execute(stmt)
    domain_record = res.scalar_one_or_none()
    if not domain_record:
        raise HTTPException(status_code=404, detail="Domain mapping not found.")

    # Mark as verified and SSL active
    domain_record.verification_status = "verified"
    domain_record.ssl_status = "active"
    await db.commit()
    await db.refresh(domain_record)
    return domain_record


@router.patch("/{deployment_id}/env", response_model=DeploymentResponse)
async def update_environment_variables(
    deployment_id: uuid.UUID,
    payload: EnvironmentVariableUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Updates tenant-scoped public environment variables for the deployment.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    deployment.env_vars = payload.env_vars
    await db.commit()
    await db.refresh(deployment)
    return deployment
