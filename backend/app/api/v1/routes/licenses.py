"""
Endpoints for User Purchased Licenses & Deployment Activation Keys.
Allows buyers to view purchased templates, generate deployment keys,
and import templates into their deployment dashboard for editing and publishing.
"""

import uuid
import re
import json
import random
import string
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.license import License, LicenseType
from app.models.template import Template, TemplateStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.models.deployment import Deployment
from app.services.template_service import create_or_get_buyer_draft_copy

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_license_notes(notes: Optional[str]) -> dict:
    if not notes:
        return {}
    trimmed = notes.strip()
    if trimmed.startswith("{"):
        try:
            return json.loads(trimmed)
        except Exception:
            pass
    meta = {}
    if "custom_draft_id=" in notes:
        try:
            meta["custom_draft_id"] = notes.split("custom_draft_id=")[-1].split()[0].strip()
        except Exception:
            pass
    return meta


class ProjectTokenItem(BaseModel):
    name: str
    token_id: str
    created_at: Optional[str] = None


class PurchasedTemplateResponse(BaseModel):
    license_id: str
    license_key: str
    deployment_key: str
    token_id: str
    project_tokens: List[ProjectTokenItem] = []
    template_id: str
    template_title: str
    template_slug: str
    thumbnail_url: Optional[str] = None
    framework: str = "HTML"
    order_id: Optional[str] = None
    order_number: Optional[str] = None
    purchased_at: Optional[str] = None
    license_type: str = "regular"
    is_active: bool = True
    seller_name: str = "Verified Creator"
    custom_draft_id: Optional[str] = None
    studio_edit_url: str
    deploy_url: str
    preview_url: str


class GenerateKeyRequest(BaseModel):
    template_id: Optional[str] = None
    license_id: Optional[str] = None


class CreateProjectTokenRequest(BaseModel):
    license_id: str
    project_name: str = Field(..., min_length=2, max_length=80)


class KeyActivationRequest(BaseModel):
    key: Optional[str] = Field(default=None, max_length=100)
    license_id: Optional[str] = None
    template_id: Optional[str] = None
    project_name: Optional[str] = None


@router.get("/my-purchases", response_model=List[PurchasedTemplateResponse])
async def get_my_purchased_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all templates purchased by the authenticated user with their
    active commercial licenses, deployment keys, and direct Studio/Deployment URLs.
    """
    stmt = (
        select(License)
        .options(
            selectinload(License.template).selectinload(Template.seller),
            selectinload(License.order),
        )
        .where(
            License.user_id == current_user.id,
            License.is_active.is_(True),
        )
        .order_by(desc(License.created_at))
    )
    result = await db.execute(stmt)
    licenses = result.scalars().all()

    # Also fetch all buyer draft projects to link existing custom_draft_ids
    drafts_stmt = select(Template).where(
        Template.seller_id == current_user.id,
        Template.status == TemplateStatus.DRAFT,
        Template.is_deleted.is_(False),
    )
    drafts_res = await db.execute(drafts_stmt)
    user_drafts = drafts_res.scalars().all()

    draft_by_origin = {}
    for d in user_drafts:
        if d.forked_from_template_id:
            draft_by_origin[str(d.forked_from_template_id)] = str(d.id)

    response_items = []

    for lic in licenses:
        t = lic.template
        if not t:
            continue

        meta = _parse_license_notes(lic.notes)

        # Generate a clean, unified deployment key and site- token ID
        raw_key = lic.license_key or f"LIC-{lic.id.hex[:12].upper()}"
        clean_code = raw_key.replace("LIC-", "").replace("DEP-", "").replace("site-", "").replace("SITE-", "").strip().upper()
        deployment_key = f"DEP-{clean_code}"
        primary_token_id = f"site-{clean_code.lower()}"

        # Resolve draft project ID if existing
        draft_id = draft_by_origin.get(str(t.id))
        if not draft_id and meta.get("custom_draft_id"):
            draft_id = meta.get("custom_draft_id")

        target_project_id = draft_id or str(t.id)

        # Seller brand name
        seller_brand = "Verified Creator"
        if t.seller:
            seller_brand = (
                t.seller.creator_brand_name
                or t.seller.full_name
                or t.seller.username
                or "Verified Creator"
            )

        purchased_date_str = lic.created_at.isoformat() if lic.created_at else None

        # Build list of named project tokens (always starting with site-)
        existing_tokens = list(meta.get("project_tokens") or [])
        if not existing_tokens:
            existing_tokens = [
                {
                    "name": "Main Site Project",
                    "token_id": primary_token_id,
                    "created_at": purchased_date_str,
                }
            ]
        elif not any(tok.get("token_id") == primary_token_id for tok in existing_tokens):
            existing_tokens.insert(0, {
                "name": "Main Site Project",
                "token_id": primary_token_id,
                "created_at": purchased_date_str,
            })

        project_token_objs = [
            ProjectTokenItem(
                name=tok.get("name", "Project Site"),
                token_id=tok.get("token_id", primary_token_id),
                created_at=tok.get("created_at"),
            )
            for tok in existing_tokens
        ]

        response_items.append(
            PurchasedTemplateResponse(
                license_id=str(lic.id),
                license_key=raw_key,
                deployment_key=deployment_key,
                token_id=primary_token_id,
                project_tokens=project_token_objs,
                template_id=str(t.id),
                template_title=t.title or "Website Template",
                template_slug=t.slug or "",
                thumbnail_url=t.thumbnail_url,
                framework=t.framework.value if hasattr(t.framework, "value") else str(t.framework or "HTML"),
                order_id=str(lic.order_id) if lic.order_id else None,
                order_number=lic.order.order_number if lic.order else None,
                purchased_at=purchased_date_str,
                license_type=lic.license_type.value if hasattr(lic.license_type, "value") else str(lic.license_type or "regular"),
                is_active=bool(lic.is_active),
                seller_name=seller_brand,
                custom_draft_id=draft_id,
                studio_edit_url=f"/preview?template={target_project_id}&mode=live",
                deploy_url=f"/studio/deploy?template={target_project_id}",
                preview_url=f"/preview?template={target_project_id}&mode=live",
            )
        )

    return response_items


@router.post("/create-project-token")
async def create_project_token(
    payload: CreateProjectTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new custom named Project Token ID (starts with 'site-') for an owned template.
    Allows buyers to organize multiple client or deployment projects from a single template.
    """
    try:
        lic_uuid = uuid.UUID(payload.license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid license ID format")

    stmt = select(License).options(selectinload(License.template)).where(
        License.id == lic_uuid,
        License.user_id == current_user.id,
        License.is_active.is_(True),
    )
    res = await db.execute(stmt)
    lic = res.scalar_one_or_none()

    if not lic:
        raise HTTPException(status_code=404, detail="Active purchase license not found under your account.")

    # Format new token starting with site-
    clean_name = re.sub(r"[^a-zA-Z0-9]+", "-", payload.project_name.strip().lower()).strip("-")
    if not clean_name:
        clean_name = "site"
    clean_name = clean_name[:24]

    unique_suffix = uuid.uuid4().hex[:6]
    token_id = f"site-{clean_name}-{unique_suffix}"

    meta = _parse_license_notes(lic.notes)
    tokens = list(meta.get("project_tokens") or [])

    # Ensure default primary token is present
    raw_key = lic.license_key or f"LIC-{lic.id.hex[:12].upper()}"
    clean_code = raw_key.replace("LIC-", "").replace("DEP-", "").replace("site-", "").replace("SITE-", "").strip().upper()
    default_token = f"site-{clean_code.lower()}"
    if not any(t.get("token_id") == default_token for t in tokens):
        tokens.insert(0, {
            "name": "Main Site Project",
            "token_id": default_token,
            "created_at": lic.created_at.isoformat() if lic.created_at else None,
        })

    new_item = {
        "name": payload.project_name.strip(),
        "token_id": token_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    tokens.append(new_item)
    meta["project_tokens"] = tokens
    lic.notes = json.dumps(meta)
    await db.commit()

    return {
        "success": True,
        "token_id": token_id,
        "project_name": payload.project_name.strip(),
        "project_tokens": tokens,
        "message": f"Created new project token '{token_id}' for '{payload.project_name.strip()}'!",
    }


@router.post("/generate-key")
async def generate_deployment_key(
    payload: GenerateKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates or retrieves a formatted Deployment Key (site-...) for a purchased template.
    """
    stmt = (
        select(License)
        .options(selectinload(License.template))
        .where(
            License.user_id == current_user.id,
            License.is_active.is_(True),
        )
    )
    if payload.license_id:
        try:
            lic_uuid = uuid.UUID(payload.license_id)
            stmt = stmt.where(License.id == lic_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid license ID format")
    elif payload.template_id:
        try:
            tmpl_uuid = uuid.UUID(payload.template_id)
            stmt = stmt.where(License.template_id == tmpl_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid template ID format")
    else:
        raise HTTPException(status_code=400, detail="Provide either template_id or license_id")

    res = await db.execute(stmt)
    lic = res.scalar_one_or_none()

    if not lic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active purchase license found for this template under your account.",
        )

    # Clean and build standardized DEP key and site- token
    raw_key = lic.license_key or f"LIC-{lic.id.hex[:12].upper()}"
    clean_code = raw_key.replace("LIC-", "").replace("DEP-", "").replace("site-", "").replace("SITE-", "").strip().upper()
    deployment_key = f"DEP-{clean_code}"
    token_id = f"site-{clean_code.lower()}"

    template_title = lic.template.title if lic.template else "Website Template"

    return {
        "success": True,
        "deployment_key": deployment_key,
        "token_id": token_id,
        "license_key": raw_key,
        "template_id": str(lic.template_id),
        "template_title": template_title,
        "message": f"Deployment token ready for '{template_title}'! Paste '{token_id}' into the Deployment Dashboard to import.",
    }


@router.post("/activate-key")
async def activate_deployment_key(
    payload: KeyActivationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates the user's owned License (by license_id, template_id, or token/key), clones/attaches
    their private editable draft copy, and prepares it for Studio editing and Cloud deployment.
    Strictly tenant-scoped to `current_user.id`.
    """
    raw_input = (payload.key or "").strip()
    if not raw_input and not payload.license_id and not payload.template_id:
        raise HTTPException(status_code=400, detail="Provide a valid license, template, or deployment key.")

    resolved_project_name = payload.project_name

    # Fetch ONLY the authenticated user's active licenses (prevents cross-tenant key hijack)
    all_user_lics_res = await db.execute(
        select(License)
        .options(
            selectinload(License.template).selectinload(Template.seller),
            selectinload(License.order),
        )
        .where(
            License.user_id == current_user.id,
            License.is_active.is_(True),
        )
        .order_by(desc(License.created_at))
    )
    user_licenses = all_user_lics_res.scalars().all()
    license_record = None

    # 1. Direct lookup by license_id or template_id
    if payload.license_id:
        for cand in user_licenses:
            if str(cand.id) == str(payload.license_id).strip():
                license_record = cand
                break
    if not license_record and payload.template_id:
        target_tid = str(payload.template_id).strip()
        for cand in user_licenses:
            meta = _parse_license_notes(cand.notes)
            if str(cand.template_id) == target_tid or str(meta.get("custom_draft_id") or "") == target_tid:
                license_record = cand
                break

    # 2. Match exact project_tokens in License notes for this user
    if not license_record and raw_input:
        for cand in user_licenses:
            meta = _parse_license_notes(cand.notes)
            for tok in (meta.get("project_tokens") or []):
                if tok.get("token_id", "").strip().lower() == raw_input.lower():
                    license_record = cand
                    if not resolved_project_name:
                        resolved_project_name = tok.get("name")
                    break
            if license_record:
                break

    # 3. Exact normalized key match ONLY within the authenticated user's licenses
    if not license_record and raw_input:
        clean_code = raw_input
        for pfx in ["site-", "SITE-", "site_", "SITE_", "DEP-", "dep-", "LIC-", "lic-"]:
            if clean_code.startswith(pfx):
                clean_code = clean_code[len(pfx):]
        clean_code = clean_code.strip().upper()

        if len(clean_code) >= 4:
            target_lic_key = f"LIC-{clean_code}"
            target_dep_key = f"DEP-{clean_code}"
            for cand in user_licenses:
                cand_key = (cand.license_key or "").strip()
                cand_upper = cand_key.upper()
                cand_base = cand_upper.replace("LIC-", "").replace("DEP-", "").strip()
                if (
                    cand_key == raw_input
                    or cand_upper == target_lic_key
                    or cand_upper == target_dep_key
                    or cand_base == clean_code
                ):
                    license_record = cand
                    break

    if not license_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active purchased template license not found under your account.",
        )

    # Strict ownership check
    if license_record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This purchased template belongs to another user account.",
        )

    marketplace_template = license_record.template
    if not marketplace_template:
        raise HTTPException(status_code=404, detail="Associated website template not found.")

    # 1. Create or get private editable draft copy under buyer's account
    try:
        buyer_draft = await create_or_get_buyer_draft_copy(db, current_user.id, marketplace_template)
        meta = _parse_license_notes(license_record.notes)
        meta["custom_draft_id"] = str(buyer_draft.id)
        license_record.notes = json.dumps(meta)
        await db.commit()
        await db.refresh(buyer_draft)
    except Exception as e_copy:
        logger.warning("Error creating buyer draft from key: %s", e_copy)
        buyer_draft = marketplace_template

    target_template_id = buyer_draft.id

    # 2. Check if user already has an active deployment for this template/draft
    dep_stmt = select(Deployment).where(
        Deployment.user_id == current_user.id,
        Deployment.template_id.in_([marketplace_template.id, buyer_draft.id]),
        Deployment.status != "deleted",
    ).order_by(desc(Deployment.created_at))
    dep_res = await db.execute(dep_stmt)
    existing_deployment = dep_res.scalars().first()

    deployment_record = existing_deployment

    # 3. If no deployment exists yet, create an initial deployment entry so it appears on the Deployments Dashboard
    if not deployment_record:
        try:
            from app.services.deployment_service import DeploymentService
            svc = DeploymentService(db, "local")
            project_title = resolved_project_name or buyer_draft.title or marketplace_template.title
            site_id = f"SITE-KEY-{uuid.uuid4().hex[:8].upper()}"
            deployment_record = await svc.create_deployment(
                user=current_user,
                project_name=project_title,
                template_id=target_template_id,
                provider_type="local",
                site_id=site_id,
            )
        except Exception as e_dep:
            logger.info("Auto deployment creation notice on key activation: %s", e_dep)

    title = resolved_project_name or buyer_draft.title or marketplace_template.title
    framework_val = marketplace_template.framework.value if hasattr(marketplace_template.framework, "value") else str(marketplace_template.framework or "HTML")

    raw_lic_key = license_record.license_key or f"LIC-{license_record.id.hex[:12].upper()}"
    clean_token = raw_input if raw_input.startswith("site-") else f"site-{raw_lic_key.replace('LIC-', '').replace('DEP-', '').lower()}"

    return {
        "success": True,
        "message": f"Website '{title}' successfully activated and added to your Deployments!",
        "token_id": clean_token,
        "deployment_key": clean_token,
        "template_id": str(marketplace_template.id),
        "draft_project_id": str(target_template_id),
        "deployment_id": str(deployment_record.id) if deployment_record else None,
        "title": title,
        "framework": framework_val,
        "thumbnail_url": buyer_draft.thumbnail_url or marketplace_template.thumbnail_url,
        "studio_edit_url": f"/preview?template={target_template_id}&mode=live",
        "deploy_url": f"/studio/deploy?template={target_template_id}",
    }
