"""
Preview routes — create preview sessions and serve watermarked previews.
"""

import os
import re
import io
import json
import uuid
import shutil
import tempfile
import asyncio
import zipfile
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Body, Response, Request, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models.user import User
from app.models.template import Template, TemplateStatus
from app.models.stored_file import StoredFile
from app.models.order import Order, OrderItem, OrderStatus
from app.services.preview_service import PreviewService
from app.services.ai_service import ai_service
from app.services.security_scanner import security_scanner
from app.repositories.template_repo import TemplateRepository
from pydantic import BaseModel, Field

router = APIRouter()


class PreviewRequest(BaseModel):
    template_id: str | uuid.UUID
    business_name: str
    industry: str
    primary_color: Optional[str] = "#6366f1"
    secondary_color: Optional[str] = "#8b5cf6"
    about: Optional[str] = None
    services: Optional[list] = None
    contact: Optional[dict] = None
    location: Optional[str] = None
    social_links: Optional[dict] = None
    logo_url: Optional[str] = None
    ai_fill: bool = False  # If True, auto-generate content via AI


class PreviewResponse(BaseModel):
    session_id: uuid.UUID
    preview_image_url: Optional[str] = None
    business_data: dict
    generated_content: Optional[dict] = None
    template_id: str | uuid.UUID
class ManualEditRequest(BaseModel):
    business_name: str
    about: str
    primary_color: str
    secondary_color: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    page_edits: Optional[dict] = None
    use_ai: bool = False


class AIEditRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)




@router.post("", response_model=PreviewResponse)
async def create_preview(
    request: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Create a watermarked live preview session.

    If `ai_fill=true`, AI generates the business content automatically.
    Returns a watermarked preview image URL + session ID.
    """
    service = PreviewService(db)
    template_repo = TemplateRepository(db)

    template = await template_repo.get_by_id(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    business_data = {
        "business_name": request.business_name,
        "industry": request.industry,
        "primary_color": request.primary_color,
        "secondary_color": request.secondary_color,
        "about": request.about,
        "services": request.services or [],
        "contact": request.contact or {},
        "location": request.location,
        "social_links": request.social_links or {},
        "logo_url": request.logo_url,
    }

    generated_content = None
    if request.ai_fill and ai_service.client:
        try:
            generated_content = await ai_service.generate_business_content(
                business_name=request.business_name,
                industry=request.industry,
                template_type=template.category.name if template.category else "business",
            )
            # Merge AI content into business_data
            business_data.update(generated_content)
        except Exception:
            pass  # AI fill optional — continue without it

    user_email = current_user.email if current_user else None

    session = await service.create_session(
        template_id=request.template_id,
        business_data=business_data,
        user_email=user_email,
        is_ai_filled=request.ai_fill,
    )

    # Generate watermarked preview
    preview_url = None
    try:
        preview_url = await service.generate_preview_screenshot(
            session_id=session.id,
            template_thumbnail_url=template.thumbnail_url,
            user_email=user_email,
        )
        session.preview_image_url = preview_url
        session.generated_content = generated_content
        await db.flush()
    except Exception:
        pass  # Preview image is optional — session is still created

    return PreviewResponse(
        session_id=session.id,
        preview_image_url=preview_url,
        business_data=business_data,
        generated_content=generated_content,
        template_id=request.template_id,
    )


@router.get("/{session_id}", response_model=PreviewResponse)
async def get_preview_session(
    session_id: str | uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an existing preview session by ID."""
    try:
        session_uuid = uuid.UUID(str(session_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Preview session not found")

    from sqlalchemy import select
    from app.models.preview_session import PreviewSession

    result = await db.execute(
        select(PreviewSession).where(PreviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Preview session not found")

    return PreviewResponse(
        session_id=session.id,
        preview_image_url=session.preview_image_url,
        business_data=session.business_data or {},
        generated_content=session.generated_content,
        template_id=session.template_id,
    )


# Global locks to prevent parallel builds of the same template
_build_locks = {}
# In-memory template metadata cache for sub-millisecond preview serving
_preview_template_cache: dict[str, dict] = {}


async def _get_cached_preview_template(template_id: str, db: AsyncSession):
    """Retrieve template from RAM cache if valid (5 min TTL) to avoid multi-second Neon Oregon DB round trips."""
    import time
    now = time.time()
    cached = _preview_template_cache.get(template_id)
    if cached and (now - cached.get("cached_at", 0)) < 300:
        return cached["template"]

    from app.repositories.template_repo import TemplateRepository
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id_or_slug(template_id)
    if template:
        entry = {"template": template, "cached_at": now}
        _preview_template_cache[template_id] = entry
        if template.slug and template.slug != template_id:
            _preview_template_cache[template.slug] = entry
        if str(template.id) != template_id:
            _preview_template_cache[str(template.id)] = entry
    return template


def invalidate_preview_template_cache(template_id: str):
    """Purge cached template metadata from RAM on updates."""
    _preview_template_cache.pop(template_id, None)


@router.get("/live/{template_id}/assets")
async def list_live_preview_assets(
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List all image and media assets detected in this template preview,
    including file paths, preview URLs, and recommended format/dimension guidance.
    """
    from app.core.local_project_manager import local_project_manager
    from app.repositories.template_repo import TemplateRepository
    import time

    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id_or_slug(template_id)
    slug = template.slug if (template and template.slug) else template_id

    # 1. First check local_project_manager (generated projects)
    assets = local_project_manager.list_project_assets(slug)
    if not assets and slug != template_id:
        assets = local_project_manager.list_project_assets(template_id)

    # 2. Fallback: check tempfile preview directory if any
    if not assets:
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(template_id)
        if temp_dir.exists():
            image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico"}
            for root, _, files in os.walk(temp_dir):
                for filename in files:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in image_extensions:
                        full_path = Path(root) / filename
                        rel_path = full_path.relative_to(temp_dir).as_posix()
                        if any(part in rel_path.split("/") for part in (".git", "node_modules", "dist")):
                            continue
                        size_bytes = full_path.stat().st_size
                        size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes >= 1024 else f"{size_bytes} B"
                        stem_lower = full_path.stem.lower()
                        if any(k in stem_lower for k in ("profile", "portrait", "avatar", "person", "headshot", "owner")):
                            role = "Profile / Portrait Photo"
                            format_hint = "PNG, JPG, or WebP"
                            dim_hint = "Square (1:1, 800 × 800px)"
                        elif "logo" in stem_lower:
                            role = "Brand Logo"
                            format_hint = "PNG or SVG (Transparent)"
                            dim_hint = "Recommended 400 × 120px"
                        elif any(k in stem_lower for k in ("hero", "banner", "cover", "bg", "background")):
                            role = "Hero / Banner Image"
                            format_hint = "JPG, WebP, or PNG"
                            dim_hint = "Landscape (16:9, 1200 × 675px)"
                        else:
                            role = "Content Image"
                            format_hint = "PNG, JPG, or WebP"
                            dim_hint = "Standard resolution"
                        assets.append({
                            "filename": filename,
                            "rel_path": rel_path,
                            "size_bytes": size_bytes,
                            "size_str": size_str,
                            "extension": ext,
                            "role": role,
                            "format_hint": format_hint,
                            "dim_hint": dim_hint,
                            "updated_at": datetime.fromtimestamp(full_path.stat().st_mtime, timezone.utc).isoformat(),
                        })

    import tempfile
    backup_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "asset_backups" / str(template.id)
    slug_base = template.slug.split("-custom-")[0].split("-draft-")[0] if (template and template.slug) else template_id
    master_backup_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "pristine_master_assets" / slug_base
    ts = int(time.time())
    for a in assets:
        a["preview_url"] = f"/api/v1/preview/live/{template_id}/{a['rel_path']}?t={ts}"
        b_file = (backup_root / a["rel_path"]).resolve()
        b_orig = (backup_root / f"{a['rel_path']}.orig").resolve()
        m_file = (master_backup_root / a["rel_path"]).resolve()
        a["has_backup"] = bool(b_file.exists() or b_orig.exists() or m_file.exists())

    return {"template_id": template_id, "assets": assets, "total": len(assets)}


@router.post("/live/{template_id}/assets/replace")
async def replace_live_preview_asset(
    template_id: str,
    target_rel_path: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Replace an existing image asset on disk with the uploaded file.
    Does NOT modify the HTML, CSS, or JS code — keeping the relative path intact.
    """
    from app.core.local_project_manager import local_project_manager
    from app.repositories.template_repo import TemplateRepository
    import time

    content = await file.read()
    if not content or len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image file must be between 1 byte and 15MB")

    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id_or_slug(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    user_role = getattr(current_user.role, "value", current_user.role)
    if template.seller_id != current_user.id and str(user_role).lower() not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the owner of this private draft can replace its assets")

    from app.core.local_project_manager import _clean_rel_path
    clean_target = _clean_rel_path(target_rel_path)
    if not clean_target:
        raise HTTPException(status_code=400, detail="Invalid asset path")
    target_rel_path = clean_target
    slug = template.slug if (template and template.slug) else template_id

    # Check local_project_manager first (for Studio generated projects)
    available_assets = local_project_manager.list_project_assets(slug)
    if not any(asset.get("rel_path") == target_rel_path for asset in available_assets):
        available_assets = local_project_manager.list_project_assets(template_id)
    has_local_asset = any(asset.get("rel_path") == target_rel_path for asset in available_assets)

    # Check temp preview directory (for live template previews & drafts)
    import tempfile
    temp_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(template.id)
    temp_dest = (temp_root / target_rel_path).resolve()
    temp_file_exists = False
    try:
        temp_dest.relative_to(temp_root.resolve())
        temp_file_exists = temp_dest.is_file()
    except ValueError:
        temp_file_exists = False

    if not has_local_asset and not temp_file_exists:
        raise HTTPException(status_code=404, detail="Asset not found in this project")

    # Accept only decoded raster images. SVG and unverified uploads can execute
    # script when served inline from the application's origin.
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(content))
        image.verify()
        detected_type = Image.MIME.get(image.format)
        if detected_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            raise ValueError("Unsupported image format")
    except Exception:
        raise HTTPException(status_code=400, detail="Upload a valid PNG, JPEG, WebP, or GIF image")

    # Save original backup before replacing if not already backed up
    backup_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "asset_backups" / str(template.id)
    backup_file = (backup_root / target_rel_path).resolve()
    backup_orig = (backup_root / f"{target_rel_path}.orig").resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_orig.parent.mkdir(parents=True, exist_ok=True)

    # Master pristine assets directory that NEVER gets overwritten
    slug_base = template.slug.split("-custom-")[0].split("-draft-")[0] if (template and template.slug) else str(template_id)
    master_backup_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "pristine_master_assets" / slug_base
    master_backup_file = (master_backup_root / target_rel_path).resolve()
    master_backup_root.mkdir(parents=True, exist_ok=True)
    master_backup_file.parent.mkdir(parents=True, exist_ok=True)

    # Read original bytes before replacing
    existing_bytes = None
    if temp_file_exists and temp_dest.exists():
        try:
            existing_bytes = temp_dest.read_bytes()
        except Exception:
            pass
    elif has_local_asset:
        try:
            project_dir = local_project_manager._resolve_project_dir(slug)
            candidate_orig = project_dir / "latest" / target_rel_path
            if candidate_orig.exists():
                existing_bytes = candidate_orig.read_bytes()
        except Exception:
            pass

    if existing_bytes:
        if not master_backup_file.exists():
            try:
                master_backup_file.write_bytes(existing_bytes)
            except Exception as m_err:
                logger.warning("Could not save master pristine asset backup: %s", m_err)
        if not backup_orig.exists():
            try:
                backup_orig.write_bytes(existing_bytes)
            except Exception as b_err:
                logger.warning("Could not save .orig backup: %s", b_err)
        if not backup_file.exists():
            try:
                backup_file.write_bytes(existing_bytes)
            except Exception as b_err:
                logger.warning("Could not backup original asset: %s", b_err)

    # 1. Update in local_project_manager if this project is tracked there
    if has_local_asset:
        try:
            local_project_manager.replace_project_asset(slug, target_rel_path, content)
        except Exception:
            if slug != template_id:
                try:
                    local_project_manager.replace_project_asset(template_id, target_rel_path, content)
                except Exception as err:
                    logger.warning("Failed to save asset via local_project_manager: %s", err)

    # 2. Update temp preview directory on disk
    if temp_file_exists:
        try:
            temp_dest.write_bytes(content)
            logger.info("Replaced live preview asset on disk: %s", temp_dest)
        except Exception as disk_err:
            logger.warning("Failed to write replaced asset to disk: %s", disk_err)

    # 3. Synchronize with template's stored ZIP archive in DB
    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if zip_url:
        match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
        if match:
            from app.models.stored_file import StoredFile
            file_id = uuid.UUID(match.group(1))
            res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
            sf = res.scalar_one_or_none()
            if sf and sf.data:
                try:
                    new_zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(io.BytesIO(sf.data), "r") as z_in:
                        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
                            for item in z_in.infolist():
                                item_bytes = z_in.read(item.filename)
                                if (
                                    item.filename == target_rel_path
                                    or item.filename.replace("\\", "/") == target_rel_path
                                    or item.filename.endswith("/" + target_rel_path)
                                    or os.path.basename(item.filename) == os.path.basename(target_rel_path)
                                ):
                                    item_bytes = content
                                z_out.writestr(item, item_bytes)
                    sf.data = new_zip_buffer.getvalue()
                    sf.size = len(sf.data)
                    await db.commit()
                except Exception as zip_err:
                    logger.warning("Failed to update asset in stored ZIP: %s", zip_err)

    ts = int(time.time())
    return {
        "success": True,
        "message": "Photo replaced successfully. Zero code changes required.",
        "rel_path": target_rel_path,
        "preview_url": f"/api/v1/preview/live/{template_id}/{target_rel_path}?t={ts}",
        "size_bytes": len(content),
    }


class RestoreAssetRequest(BaseModel):
    target_rel_path: str


@router.post("/live/{template_id}/assets/restore")
async def restore_live_preview_asset(
    template_id: str,
    request: RestoreAssetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restores a replaced photo back to its original image from backup or source archive.
    """
    import tempfile
    import zipfile
    import io
    import time
    from app.core.local_project_manager import local_project_manager
    from app.repositories.template_repo import TemplateRepository

    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id_or_slug(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    target_rel_path = request.target_rel_path.lstrip("/\\").replace("\\", "/")
    slug = template.slug if (template and template.slug) else template_id

    backup_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "asset_backups" / str(template.id)
    backup_orig = (backup_root / f"{target_rel_path}.orig").resolve()
    backup_file = (backup_root / target_rel_path).resolve()

    original_bytes = None

    # Priority 0: Check permanent master pristine assets
    slug_base = template.slug.split("-custom-")[0].split("-draft-")[0] if (template and template.slug) else str(template_id)
    master_backup_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "pristine_master_assets" / slug_base
    master_backup_file = (master_backup_root / target_rel_path).resolve()
    if master_backup_file.exists() and master_backup_file.stat().st_size > 0:
        original_bytes = master_backup_file.read_bytes()

    if not original_bytes and backup_orig.exists() and backup_orig.stat().st_size > 0:
        original_bytes = backup_orig.read_bytes()
    elif not original_bytes and backup_file.exists() and backup_file.stat().st_size > 0:
        original_bytes = backup_file.read_bytes()

    # Fallback 1: Search other asset backup folders
    if not original_bytes:
        try:
            all_backups_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "asset_backups"
            for cand in all_backups_root.rglob(Path(target_rel_path).name):
                if cand.is_file() and cand.stat().st_size > 0:
                    original_bytes = cand.read_bytes()
                    break
        except Exception:
            pass

    # Fallback 2: Check master/parent marketplace template
    if not original_bytes:
        try:
            slug_base = template.slug.split("-custom-")[0].split("-draft-")[0]
            m_res = await db.execute(
                select(Template).where(
                    Template.is_marketplace == True,
                    or_(
                        Template.slug == slug_base,
                        Template.slug.like(f"{slug_base}%"),
                    )
                )
            )
            master_tmpl = m_res.scalars().first()
            if master_tmpl:
                master_preview = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(master_tmpl.id)
                cand_file = (master_preview / target_rel_path).resolve()
                if cand_file.exists():
                    original_bytes = cand_file.read_bytes()
                elif master_tmpl.download_assets and master_tmpl.download_assets.get("zip"):
                    m_zip_url = master_tmpl.download_assets.get("zip")
                    match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(m_zip_url))
                    if match:
                        from app.models.stored_file import StoredFile
                        f_res = await db.execute(select(StoredFile).where(StoredFile.id == uuid.UUID(match.group(1))))
                        m_sf = f_res.scalar_one_or_none()
                        if m_sf and m_sf.data:
                            with zipfile.ZipFile(io.BytesIO(m_sf.data), "r") as z_in:
                                for item in z_in.namelist():
                                    if (
                                        item == target_rel_path
                                        or item.replace("\\", "/") == target_rel_path
                                        or item.endswith("/" + target_rel_path)
                                        or os.path.basename(item) == os.path.basename(target_rel_path)
                                    ):
                                        original_bytes = z_in.read(item)
                                        break
        except Exception as master_err:
            logger.warning("Could not resolve original asset from master template: %s", master_err)

    # Fallback 3: check sibling live preview directories on disk
    if not original_bytes:
        try:
            all_previews_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews"
            for cand in all_previews_root.rglob(Path(target_rel_path).name):
                if cand.is_file() and str(template.id) not in str(cand):
                    original_bytes = cand.read_bytes()
                    break
        except Exception:
            pass

    # Fallback 4: check local_project_manager before_edit
    if not original_bytes:
        project_dir = local_project_manager._resolve_project_dir(slug)
        before_file = project_dir / "before_edit" / target_rel_path
        if before_file.exists():
            original_bytes = before_file.read_bytes()

    if not original_bytes:
        raise HTTPException(status_code=404, detail="Original image backup not found for this asset")

    # 1. Restore to temp preview directory on disk
    temp_root = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(template.id)
    temp_dest = (temp_root / target_rel_path).resolve()
    try:
        temp_dest.relative_to(temp_root.resolve())
        temp_dest.write_bytes(original_bytes)
        logger.info("Restored original live preview asset on disk: %s", temp_dest)
    except Exception as disk_err:
        logger.warning("Could not write restored asset to disk: %s", disk_err)

    # 2. Restore to local_project_manager if available
    try:
        local_project_manager.replace_project_asset(slug, target_rel_path, original_bytes)
    except Exception:
        if slug != template_id:
            try:
                local_project_manager.replace_project_asset(template_id, target_rel_path, original_bytes)
            except Exception:
                pass

    # 3. Synchronize with template stored ZIP archive
    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if zip_url:
        match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
        if match:
            from app.models.stored_file import StoredFile
            file_id = uuid.UUID(match.group(1))
            res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
            sf = res.scalar_one_or_none()
            if sf and sf.data:
                try:
                    new_zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(io.BytesIO(sf.data), "r") as z_in:
                        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
                            for item in z_in.infolist():
                                item_bytes = z_in.read(item.filename)
                                if (
                                    item.filename == target_rel_path
                                    or item.filename.replace("\\", "/") == target_rel_path
                                    or item.filename.endswith("/" + target_rel_path)
                                    or os.path.basename(item.filename) == os.path.basename(target_rel_path)
                                ):
                                    item_bytes = original_bytes
                                z_out.writestr(item, item_bytes)
                    sf.data = new_zip_buffer.getvalue()
                    sf.size = len(sf.data)
                    await db.commit()
                except Exception as zip_err:
                    logger.warning("Failed to restore asset in stored ZIP: %s", zip_err)

    # 4. Remove backup files now that it is restored
    for b_candidate in (backup_file, backup_orig):
        if b_candidate.exists():
            try:
                b_candidate.unlink()
            except Exception:
                pass

    ts = int(time.time())
    return {
        "success": True,
        "message": "Original photo restored successfully.",
        "rel_path": target_rel_path,
        "preview_url": f"/api/v1/preview/live/{template_id}/{target_rel_path}?t={ts}",
    }


@router.get("/live/{template_id}/extracted-data")
async def get_live_preview_extracted_data(
    template_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Dynamically extract the real template content directly from its source files:
    Real brand name, logo text, H1 headline, subtitle, navigation links, CTA buttons,
    contact info, footer copyright, and lively detected sections (no fake/unrelated sections).
    """
    import zipfile
    import io
    import re
    import tempfile
    from app.models.template import Template
    from app.models.stored_file import StoredFile
    from app.repositories.template_repo import TemplateRepository
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        template = await template_repo.get_by_slug(template_id)
        
    title = (template.title if template else None) or "Web Template"
    clean_brand = title.split("—")[0].split("-")[0].split("|")[0].strip()
    primary_color = "#4f46e5"
    if template and template.color_scheme:
        cs = template.color_scheme.strip()
        if cs.startswith("#"):
            primary_color = cs
        else:
            c_lower = cs.lower()
            if "red" in c_lower: primary_color = "#C4222C"
            elif "green" in c_lower: primary_color = "#059669"
            elif "blue" in c_lower: primary_color = "#2563eb"
            elif "purple" in c_lower or "violet" in c_lower: primary_color = "#8b5cf6"
            elif "amber" in c_lower or "orange" in c_lower: primary_color = "#d97706"

    # Also detect real applied color directly from disk (local_project_manager)
    try:
        from app.core.local_project_manager import local_project_manager
        proj_dir = local_project_manager.get_local_project_dir(template_id, version="latest")
        if not proj_dir and template and template.slug:
            proj_dir = local_project_manager.get_local_project_dir(template.slug, version="latest")
        if proj_dir and os.path.isdir(str(proj_dir)):
            for r, _, fs_list in os.walk(str(proj_dir)):
                for fn in fs_list:
                    if fn.endswith(".css"):
                        try:
                            with open(os.path.join(r, fn), "r", encoding="utf-8", errors="ignore") as _cf:
                                _snippet = _cf.read(4000)
                                _m = re.search(r'/\* \[STUDIO_APPLIED_THEME_COLOR\] \*/[\s\S]*?--primary:\s*(#[a-fA-F0-9]{3,8})', _snippet)
                                if not _m:
                                    _m = re.search(r'--(?:c-primary|color-primary|primary|theme-color):\s*(#[a-fA-F0-9]{3,8})', _snippet)
                                if _m:
                                    primary_color = _m.group(1).strip()
                                    break
                        except Exception:
                            pass
                if primary_color and primary_color != "#4f46e5":
                    break
    except Exception as _ce:
        logger.debug(f"Could not read local CSS theme color: {_ce}")

    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    if not os.path.isdir(preview_dir) and template:
        p_by_id = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template.id))
        if os.path.isdir(p_by_id):
            preview_dir = p_by_id
        elif template.slug:
            p_by_slug = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template.slug))
            if os.path.isdir(p_by_slug):
                preview_dir = p_by_slug

    if not template and not os.path.isdir(preview_dir):
        raise HTTPException(status_code=404, detail="Template not found")

    # Read content from preview_dir first (if already extracted/running), else fallback to stored ZIP
    content = ""
    if os.path.exists(preview_dir):
        candidates = []
        for root, dirs, files in os.walk(preview_dir):
            dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "dist", "build", ".output", "__MACOSX", ".venv", "vendor"]]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".html", ".jsx", ".tsx", ".vue"]:
                    candidates.append(os.path.join(root, f))
        
        main_f = None
        for c in candidates:
            if os.path.basename(c).lower() == "index.html":
                main_f = c
                break
        if not main_f:
            for c in candidates:
                if c.endswith(".html"):
                    main_f = c
                    break
        if not main_f and candidates:
            main_f = candidates[0]
            
        if main_f and os.path.exists(main_f):
            try:
                with open(main_f, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e_rf:
                logger.warning(f"Failed to read preview file {main_f}: {e_rf}")

    # Collect ALL source files from DB stored file (HTML + JSX/TSX)
    all_source_files = {}  # filename -> content string
    if not content:
        download_assets = template.download_assets or {}
        zip_url = download_assets.get("zip")
        if zip_url:
            match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
            if match:
                file_id = uuid.UUID(match.group(1))
                sf_res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
                stored_file = sf_res.scalar_one_or_none()
                if stored_file and stored_file.data:
                    if zipfile.is_zipfile(io.BytesIO(stored_file.data)):
                        with zipfile.ZipFile(io.BytesIO(stored_file.data), "r") as z_in:
                            namelist = z_in.namelist()
                            # Collect ALL source files (exclude build dirs)
                            for n in namelist:
                                is_build = any(d in n.replace("\\", "/").split("/")
                                               for d in ["node_modules", "dist", "build", "out", ".output", "__MACOSX"])
                                is_src = (n.endswith(".html") or n.endswith(".jsx") or
                                          n.endswith(".tsx") or n.endswith(".vue") or
                                          n.endswith(".js") or n.endswith(".ts"))
                                if is_src and not is_build:
                                    try:
                                        all_source_files[n] = z_in.read(n).decode("utf-8", errors="ignore")
                                    except Exception:
                                        pass
                            # Pick main file content for BS4 path (use already-read dict)
                            html_keys = [n for n in all_source_files if n.endswith("index.html") or
                                         (n.endswith(".html") and "__MACOSX" not in n)]
                            jsx_keys = [n for n in all_source_files if (n.endswith("App.jsx") or n.endswith("App.tsx"))]
                            if html_keys:
                                content = all_source_files[html_keys[0]]
                            elif jsx_keys:
                                content = all_source_files[jsx_keys[0]]
                            elif all_source_files:
                                content = next(iter(all_source_files.values()))
                    else:
                        content = stored_file.data.decode("utf-8", errors="ignore")

    # Also collect files from already-extracted preview_dir (for JSX builds)
    if not all_source_files and os.path.exists(preview_dir):
        for root, dirs, files in os.walk(preview_dir):
            dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "dist", "build", ".output", "__MACOSX", ".venv", "vendor"]]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".html", ".jsx", ".tsx", ".vue", ".js", ".ts"]:
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                            all_source_files[fpath] = fh.read()
                    except Exception:
                        pass

    from bs4 import BeautifulSoup

    def clean_text(text: str) -> str:
        if not text:
            return ""
        c = re.sub(r"<[^>]+>", " ", text)
        c = re.sub(r"\s+([.,!?:;])", r"\1", c)
        return re.sub(r"\s+", " ", c).strip()

    # ─── Universal JSX/TSX/Vue Source Code Extractor ─────────────────────────
    def extract_from_jsx_sources(src_files: dict, tmpl_title: str, tmpl_color: str):
        """Parse JSX/TSX/Vue source files using normalized BeautifulSoup and regex to extract real sections, headlines, cards, and text."""
        def file_priority(fname: str) -> int:
            fn = os.path.basename(fname).lower()
            if fn in ["home.jsx", "home.tsx", "home.vue"]:
                return 0
            if fn in ["app.jsx", "app.tsx", "app.vue"]:
                return 1
            if fn in ["index.jsx", "index.tsx", "page.jsx", "page.tsx"]:
                return 2
            if "page" in fname.lower():
                return 3
            return 4

        sorted_files = sorted(src_files.items(), key=lambda kv: file_priority(kv[0]))
        combined = "\n".join(ftext for _, ftext in sorted_files)

        # 1. Primary Color
        pcolor = tmpl_color or "#4f46e5"
        for cp in [
            r"primary(?:Color)?\s*[=:]\s*['\"`](#[0-9a-fA-F]{3,8})['\"`]",
            r"--(?:primary|accent|brand)(?:-color)?:\s*(#[0-9a-fA-F]{3,8})",
            r"--red:\s*(#[0-9a-fA-F]{3,8})",
            r"--blue:\s*(#[0-9a-fA-F]{3,8})",
            r"themeColor\s*[=:]\s*['\"`](#[0-9a-fA-F]{3,8})['\"`]",
        ]:
            m = re.search(cp, combined, re.I)
            if m:
                pcolor = m.group(1)
                break

        # Pick primary file for main DOM structure
        primary_fname, primary_code = sorted_files[0] if sorted_files else ("", "")
        soup_code = re.sub(r'\bclassName=', 'class=', primary_code)
        soup = BeautifulSoup(soup_code, "html.parser")

        # 2. Brand & Logo Text
        bname = tmpl_title
        nav_el = soup.find(["nav", "header"])
        if nav_el:
            logo_el = nav_el.find(class_=re.compile(r"logo|brand", re.I)) or nav_el.find("h1")
            if logo_el and logo_el.get_text(strip=True):
                bname = clean_text(logo_el.get_text(separator=" ", strip=True))
        if not bname or bname == tmpl_title:
            for pattern in [
                r"brandName\s*[=:]\s*['\"`]([^'\"\`]{2,50})['\"`]",
                r"business_name\s*[=:]\s*['\"`]([^'\"\`]{2,50})['\"`]",
                r"companyName\s*[=:]\s*['\"`]([^'\"\`]{2,50})['\"`]",
                r"siteName\s*[=:]\s*['\"`]([^'\"\`]{2,50})['\"`]",
                r"<title>([^<]{2,50})</title>",
            ]:
                m = re.search(pattern, combined, re.I)
                if m:
                    bname = m.group(1).split("—")[0].split("-")[0].strip()
                    break

        logo_text = re.sub(r"[^A-Z0-9]", "", bname.upper())[:7] or "BRAND"

        def classify_jsx_section(sid: str):
            k = sid.lower()
            if any(w in k for w in ["hero", "home", "banner", "intro", "landing"]):
                return "Hero & Banner", "Zap"
            if any(w in k for w in ["nav", "header", "menu"]):
                return "Header & Nav", "Monitor"
            if any(w in k for w in ["about", "story", "who", "bio"]):
                return "Content & Story", "FileText"
            if any(w in k for w in ["service", "offering", "solution", "capability", "feature"]):
                return "Capabilities & Services", "Layers"
            if any(w in k for w in ["work", "port", "project", "evidence", "case", "exhibit"]):
                return "Portfolio & Case Files", "Layers"
            if any(w in k for w in ["skill", "dossier", "stack", "tech"]):
                return "Skills & Capabilities", "Shield"
            if any(w in k for w in ["timeline", "history", "log", "experience", "resume"]):
                return "Historical Record", "Clock"
            if any(w in k for w in ["price", "pricing", "plan", "tier", "subscription"]):
                return "Conversion & Plans", "Sparkles"
            if any(w in k for w in ["review", "testimonial", "client", "rating"]):
                return "Social Proof & Reviews", "Star"
            if any(w in k for w in ["contact", "touch", "reach", "inquiry", "lead", "form"]):
                return "Inquiry & Leads", "Mail"
            if any(w in k for w in ["footer", "foot"]):
                return "Footer & Record", "Shield"
            return "Section Content", "Globe"

        out_sections = {}
        out_sections_list = []
        seen_ids = set()

        # 3. Navbar
        nav_links = []
        nav_cta = "Get Started"
        if nav_el:
            links_raw = [clean_text(a.get_text()) for a in nav_el.find_all("a") if a.get_text(strip=True)]
            nav_links = [l for l in links_raw if 0 < len(l) < 30 and l.lower() != bname.lower()]
            btn_el = nav_el.find(["button", "a"], class_=re.compile(r"btn|cta|login|signup", re.I))
            if btn_el and btn_el.get_text(strip=True):
                nav_cta = clean_text(btn_el.get_text())
        if not nav_links:
            nav_links = ["Features", "About", "Contact"]

        out_sections["navbar"] = {
            "brandName": bname,
            "logoText": logo_text,
            "navLinks": nav_links,
            "ctaText": nav_cta,
            "stickyGlass": True,
            "themeColor": pcolor
        }
        out_sections_list.append({
            "id": "navbar", "name": "Navigation Header",
            "category": "Header & Nav", "icon": "Monitor",
            "desc": "Top navigation bar with brand logo and navigation links",
            "targetSection": "navbar"
        })
        seen_ids.add("navbar")

        # 4. Discover and Parse Sections across primary and other components
        candidate_soups = [(primary_fname, soup)]
        for fname, fcode in sorted_files[1:]:
            base_lower = os.path.basename(fname).lower()
            if any(skip in base_lower for skip in ["config", "test", "spec", "setup", "router", "provider", "context", "store"]):
                continue
            if fname.endswith((".jsx", ".tsx", ".vue")):
                f_soup = BeautifulSoup(re.sub(r'\bclassName=', 'class=', fcode), "html.parser")
                candidate_soups.append((fname, f_soup))

        for cfname, csoup in candidate_soups:
            sec_elements = csoup.find_all(["section", "footer"])
            if not sec_elements:
                sec_elements = csoup.find_all(class_=re.compile(r"(?:hero|feature|about|service|pricing|contact|footer|content)-section", re.I))

            for idx, el in enumerate(sec_elements):
                tag = el.name
                sec_id = el.get("id") or ""
                sec_class = " ".join(el.get("class", [])) if el.get("class") else ""

                # Determine canonical ID
                cid = ""
                if tag == "footer" or "footer" in sec_class.lower():
                    cid = "footer"
                elif sec_id:
                    cid = sec_id.lower().replace("-", "_")

                if not cid:
                    for kw in ["hero", "feature", "about", "service", "pricing", "contact", "portfolio", "stat"]:
                        if kw in sec_class.lower():
                            cid = kw if kw != "feature" else "features"
                            break
                if not cid:
                    cid = f"section_{len(seen_ids)}"

                if cid in seen_ids:
                    continue
                seen_ids.add(cid)

                # Headline / Title
                h_tag = el.find(["h1", "h2", "h3", "h4"])
                headline = clean_text(h_tag.get_text(separator=" ", strip=True)) if h_tag else ""

                # Badge
                badge_el = el.find(class_=re.compile(r"badge|pill|tag", re.I))
                badge = clean_text(badge_el.get_text(strip=True)) if badge_el else ""

                # Description / Subtitle
                p_tags = [clean_text(p.get_text(separator=" ", strip=True)) for p in el.find_all("p") if len(clean_text(p.get_text(strip=True))) > 15]
                description = p_tags[0] if p_tags else ""

                # Buttons
                buttons = [clean_text(b.get_text(strip=True)) for b in el.find_all("button") if b.get_text(strip=True)]
                primary_cta = buttons[0] if buttons else "Get Started"
                secondary_cta = buttons[1] if len(buttons) > 1 else ""

                # Cards
                card_els = el.find_all(class_=re.compile(r"card|item", re.I))
                if not card_els:
                    grid_container = el.find(class_=re.compile(r"grid|flex-wrap", re.I))
                    if grid_container:
                        candidates = [child for child in grid_container.find_all(recursive=False) if getattr(child, "name", None) in ("div", "article", "section", "li")]
                        if len(candidates) >= 2:
                            card_els = candidates
                cards = []
                for c_idx, c in enumerate(card_els):
                    c_title = c.find(["h1", "h2", "h3", "h4", "strong"])
                    c_desc = c.find("p")
                    c_tag = c.find(class_=re.compile(r"icon|tag|badge", re.I))
                    c_link = c.find("a") or (c if c.name == "a" else None)
                    c_href = clean_text(c_link.get("href", "")) if c_link and c_link.get("href") else ""
                    t_txt = clean_text(c_title.get_text(strip=True)) if c_title else f"Item #{c_idx + 1}"
                    d_txt = clean_text(c_desc.get_text(separator=" ", strip=True)) if c_desc else ""
                    tg_txt = clean_text(c_tag.get_text(strip=True)) if c_tag else f"ITEM #{c_idx + 1}"
                    if t_txt or d_txt:
                        cards.append({"title": t_txt, "desc": d_txt, "tag": tg_txt, "stack": "", "link": c_href, "href": c_href})

                cat_name, icon_name = classify_jsx_section(cid)
                if cid == "hero":
                    disp_name = headline if (headline and 3 < len(headline) < 35) else "Hero Section"
                elif cid == "features":
                    disp_name = headline if (headline and 3 < len(headline) < 35) else "Features Section"
                elif cid == "about":
                    disp_name = headline if (headline and 3 < len(headline) < 35) else "About Section"
                elif cid == "footer":
                    disp_name = "Website Footer"
                else:
                    disp_name = headline if (headline and 3 < len(headline) < 35) else cid.replace("_", " ").title()

                sec_data = {
                    "title": headline or disp_name,
                    "headline": headline or disp_name,
                    "badgeText": badge,
                    "subheadline": description,
                    "description": description,
                    "themeColor": pcolor,
                    "primaryCta": primary_cta,
                    "secondaryCta": secondary_cta,
                }
                if cards:
                    sec_data["cards"] = cards
                    for i, c in enumerate(cards[:10], start=1):
                        sec_data[f"card{i}_title"] = c["title"]
                        sec_data[f"card{i}_desc"] = c["desc"]
                        sec_data[f"card{i}_tag"] = c["tag"]
                        if c.get("link"):
                            sec_data[f"card{i}_link"] = c["link"]
                            sec_data[f"card{i}_href"] = c["link"]

                if cid == "footer":
                    sec_data["brandName"] = bname
                    sec_data["tagline"] = description or f"{bname}. All rights reserved."
                    sec_data["copyright"] = f"© 2026 {bname}. All rights reserved."

                out_sections[cid] = sec_data
                out_sections_list.append({
                    "id": cid,
                    "name": disp_name,
                    "category": cat_name,
                    "icon": icon_name,
                    "desc": description[:80] if description else f"Template section for {disp_name}",
                    "targetSection": cid
                })

        # Ensure Footer exists
        if "footer" not in out_sections:
            out_sections["footer"] = {
                "brandName": bname,
                "tagline": f"{bname}. All rights reserved.",
                "copyright": f"© 2026 {bname}. All rights reserved.",
                "themeColor": pcolor
            }
            out_sections_list.append({
                "id": "footer", "name": "Website Footer",
                "category": "Footer & Record", "icon": "Shield",
                "desc": "Site footer with brand signature, legal copyright, and links",
                "targetSection": "footer"
            })

        return {
            "status": "success",
            "brand": {"business_name": bname, "logo_text": logo_text, "primary_color": pcolor},
            "sections": out_sections,
            "sections_list": out_sections_list
        }

    # ─── Decide: use JSX extractor OR BeautifulSoup (HTML) ──────────────────
    jsx_files_found = {k: v for k, v in all_source_files.items()
                       if k.endswith(".jsx") or k.endswith(".tsx") or k.endswith(".vue")}

    if jsx_files_found:
        # Modern React/Vue/Vite project — extract the real sections and components from source files
        result = extract_from_jsx_sources(all_source_files, title, primary_color)
        if result and len(result.get("sections_list", [])) > 1:
            return result

    soup = BeautifulSoup(content or "", "html.parser")
    
    # 1. Page Title & Clean Brand
    title_tag = soup.find("title")
    page_title = clean_text(title_tag.string) if title_tag and title_tag.string else title
    clean_brand = page_title.split("—")[0].split("-")[0].split("|")[0].strip() or title
    
    h1_tag = soup.find("h1")
    h1_text = clean_text(h1_tag.get_text()) if h1_tag else ""
    brand_el = soup.find(class_=re.compile(r"\bbrand\b|\blogo\b", re.I)) or soup.find(id=re.compile(r"brand|logo", re.I))
    if h1_text and 2 < len(h1_text) < 40 and not any(w in h1_text.lower() for w in ["welcome", "hello", "home", "loading", "main"]):
        brand_name = h1_text
    elif brand_el and brand_el.get_text(strip=True):
        brand_name = clean_text(brand_el.get_text())
    else:
        brand_name = clean_brand
    if len(brand_name) > 40:
        brand_name = clean_brand

    # Detect theme color from :root, linked CSS files, or style tags
    primary_color = "#4f46e5"
    css_pool = []
    style_tag = soup.find("style")
    if style_tag and style_tag.string:
        css_pool.append(style_tag.string)
    for fname, fcontent in (all_source_files or {}).items():
        if fname.endswith(".css"):
            css_pool.append(fcontent)

    for st in css_pool:
        # Check specific CSS root variables first (--accent-gold, --accent-amber, --primary, etc.)
        var_m = re.search(r'--(?:accent-gold|accent-amber|accent|primary-color|primary|theme-color|brand|cta-bg)\s*:\s*(#[0-9a-fA-F]{3,8})', st, re.I)
        if var_m:
            primary_color = var_m.group(1).upper()
            break
        if "--red" in st or "var(--red)" in st or "#c4222c" in st.lower():
            primary_color = "#C4222C"
            break
        elif "--blue" in st or "var(--blue)" in st or "#2563eb" in st.lower():
            primary_color = "#2563eb"
            break
        elif "--green" in st or "var(--green)" in st or "#059669" in st.lower():
            primary_color = "#059669"
            break
        elif "--orange" in st or "--amber" in st:
            primary_color = "#d97706"
            break

    sections = {}
    sections_list = []
    seen_ids = set()

    # 2. Navigation Header
    nav_el = soup.find("nav") or soup.find("header")
    if nav_el or "<nav" in content.lower() or "logo" in content.lower():
        nav_text_container = nav_el if nav_el else soup
        links = [clean_text(a.get_text()) for a in nav_text_container.find_all("a") if 0 < len(clean_text(a.get_text())) < 25]
        if links and (links[0].lower() == brand_name.lower() or len(links[0]) > 20):
            links = links[1:]
            
        btn = nav_text_container.find("button") or nav_text_container.find(class_=re.compile(r"btn|cta", re.I))
        btn_text = clean_text(btn.get_text()) if btn else (links[-1] if len(links) > 4 else "Get Started")
        
        # Remove CTA link from nav links if it matches the button text
        nav_link_list = [lnk for lnk in links if lnk.lower() != (btn_text or "").lower()]
        if not nav_link_list:
            nav_link_list = ["Home", "About", "Services", "Contact"]

        sections["navbar"] = {
            "brandName": brand_name,
            "logoText": re.sub(r"[^A-Z0-9]", "", brand_name.upper())[:7] or "BRAND",
            "navLinks": nav_link_list,     # unlimited array, all links from template
            "ctaText": btn_text or "Get Started",
            "stickyGlass": True,
            "themeColor": primary_color
        }
        sections_list.append({
            "id": "navbar",
            "name": "Navigation Header",
            "category": "Header & Nav",
            "icon": "Monitor",
            "desc": f"Top navigation bar with brand logo, {len(nav_link_list)} menu links, and action button",
            "targetSection": "navbar"
        })
        seen_ids.add("navbar")

    # 2b. Hero & Banner Section
    hero_el = soup.find(id=re.compile(r"hero|banner|intro", re.I)) or soup.find(class_=re.compile(r"hero|banner|intro|header-wrapper|header-clip", re.I))
    hero_h1 = hero_el.find("h1") if hero_el else soup.find("h1")
    hero_h2 = hero_el.find(["h2", "h3"]) if hero_el else soup.find(["h2", "h3"])
    hero_p = hero_el.find("p") if hero_el else None
    hero_cta = hero_el.find(["a", "button"], class_=re.compile(r"scroll|btn|cta|btn-primary", re.I)) if hero_el else None

    if hero_h1 or hero_h2 or hero_el:
        h1_val = clean_text(hero_h1.get_text()) if hero_h1 else brand_name
        h2_val = clean_text(hero_h2.get_text()) if hero_h2 else (clean_text(hero_p.get_text()) if hero_p else "")
        cta_val = clean_text(hero_cta.get_text()) if hero_cta else "Explore More"
        sections["hero"] = {
            "title": h1_val,
            "headline": h1_val,
            "subheadline": h2_val,
            "description": h2_val,
            "primaryCta": cta_val,
            "themeColor": primary_color
        }
        sections_list.append({
            "id": "hero",
            "name": "Hero & Banner",
            "category": "Hero & Banner",
            "icon": "Zap",
            "desc": "Primary introduction banner with headline and action callout",
            "targetSection": "hero"
        })
        seen_ids.add("hero")

    def classify_section(sid: str, stitle: str):
        k = (sid + " " + stitle).lower()
        if any(w in k for w in ["hero", "home", "banner", "intro"]):
            return "Hero & Banner", "Zap"
        if any(w in k for w in ["about", "story", "who", "bio"]):
            return "Content & Story", "FileText"
        if any(w in k for w in ["service", "offering", "solution", "capability", "feature"]):
            return "Capabilities & Services", "Layers"
        if any(w in k for w in ["work", "port", "project", "evidence", "case", "exhibit"]):
            return "Portfolio & Case Files", "Layers"
        if any(w in k for w in ["skill", "dossier", "stack", "tech"]):
            return "Skills & Capabilities", "Shield"
        if any(w in k for w in ["timeline", "history", "log", "experience", "resume"]):
            return "Historical Record", "Clock"
        if any(w in k for w in ["price", "pricing", "plan", "tier"]):
            return "Conversion & Plans", "Sparkles"
        if any(w in k for w in ["review", "testimonial", "client", "rating"]):
            return "Social Proof & Reviews", "Star"
        if any(w in k for w in ["contact", "touch", "reach", "inquiry", "lead"]):
            return "Inquiry & Leads", "Mail"
        if any(w in k for w in ["info", "address", "phone", "location"]):
            return "Direct Reach & Contact", "Phone"
        if any(w in k for w in ["social", "network"]):
            return "Social Channels", "Share2"
        if any(w in k for w in ["career", "job", "training"]):
            return "Opportunities & Programs", "Globe"
        return "Section Content", "Globe"

    # 3. Discover True Top-Level Sections
    raw_sections = soup.find_all("section")
    if not raw_sections:
        candidates = soup.find_all("div", id=re.compile(r"^[a-zA-Z0-9_-]+$"))
        class_candidates = soup.find_all("div", class_=re.compile(r"\b(review|reviews|testimonial|testimonials|client|clients|about|services|skills|resume|portfolio|work|contact|info|social)\b", re.I))
        for cc in class_candidates:
            if cc not in candidates and not any(cand in cc.parents for cand in candidates):
                candidates.append(cc)

        raw_sections = []
        for c in candidates:
            cid = c.get("id", "").lower()
            cclass = " ".join(c.get("class", [])).lower()
            if cclass in ["footer", "header", "nav", "row", "container", "wrap", "wrapper", "header-clip"]:
                continue
            if any(skip in cid for skip in ["header-clip", "header", "nav", "root", "app", "tab-content", "tab-pane", "clip", "modal", "overlay", "container", "row"]):
                continue
            if c.find_parent("section") or c.find_parent("div", id=re.compile(r"^(?!wrap|main|root|app).*$")):
                continue
            if c.find(["h1", "h2", "h3", "h4", "form", "img"]) or len(clean_text(c.get_text())) > 25:
                raw_sections.append(c)

    for idx, s in enumerate(raw_sections):
        s_id = s.get("id") or (s.get("class", [""])[0] if s.get("class") else f"sec_{idx}")
        s_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(s_id)).lower()
        if not s_id or s_id in seen_ids or s_id in ["header", "nav", "footer", "header_clip"]:
            continue
        seen_ids.add(s_id)

        # Headings
        h_tag = s.find(["h1", "h2", "h3", "h4"])
        headline = clean_text(h_tag.get_text()) if h_tag else ""
        
        # Badge / Pill Tag
        badge_el = s.find(class_=re.compile(r"badge|tag|status|stamp|pill", re.I))
        badge = clean_text(badge_el.get_text()) if badge_el else ""
        
        # Narrative / Description / Bio — extract BOTH subtitle and full narrative
        p_tags = s.find_all("p")
        p_clean = [clean_text(p.get_text()) for p in p_tags if len(clean_text(p.get_text())) > 5]
        subtitle = ""
        story = ""
        if len(p_clean) == 1:
            subtitle = p_clean[0]
            story = p_clean[0]
        elif len(p_clean) >= 2:
            if len(p_clean[0]) < 80:
                subtitle = p_clean[0]
                story = "\n\n".join(p_clean[1:])
            else:
                subtitle = p_clean[0]
                story = "\n\n".join(p_clean)
        narrative = story or subtitle

        # Form Inspection (STRICT: only real fields that exist in this section)
        form_el = s.find("form")
        inputs = [clean_text(inp.get("placeholder") or inp.get("name") or "") for inp in s.find_all("input") if inp.get("type") not in ["hidden", "submit"]]
        textareas = [clean_text(ta.get("placeholder") or ta.get("name") or "") for ta in s.find_all("textarea")]
        submit_btn = s.find(["button", "input"], type=re.compile(r"submit|button", re.I)) or s.find("button")
        submit_text = clean_text(submit_btn.get_text()) if submit_btn and hasattr(submit_btn, "get_text") else "Submit"
        has_form = bool(form_el or (inputs and len(inputs) >= 1))

        # Check Phone & Address STRICTLY in template code
        s_text = s.get_text()
        phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', s_text)
        has_phone = bool(phone_match or s.find(href=re.compile(r"^tel:", re.I)) or s.find("input", type="tel"))
        phone_val = phone_match.group(0) if phone_match else ""

        has_address = bool(s.find("address") or re.search(r'\b(?:\d{2,}\s+[A-Za-z]+|\b[A-Z]{2}\s+\d{5}\b|suite\s+\d+|floor\s+\d+)\b', s_text, re.I))
        address_val = ""
        if has_address:
            addr_tag = s.find("address")
            address_val = clean_text(addr_tag.get_text()) if addr_tag else ""

        # Key-Value Meta Items (e.g. <div>ROLE<span>...</span></div> or .stat)
        meta_items = []
        div_spans = s.find_all(lambda tag: tag.name == "div" and tag.find("span") and len(tag.get_text(strip=True)) < 60)
        for ds in div_spans:
            sp = ds.find("span")
            k = clean_text(ds.get_text().replace(sp.get_text(), ""))
            v = clean_text(sp.get_text())
            if k and v and len(k) < 20 and len(v) < 35:
                meta_items.append({"label": k, "value": v})

        # Cards / Child items extraction with deduplication & specialized support
        card_items = []
        seen_card_keys = set()

        # 1. Timeline / Resume Milestones
        timeline_lis = []
        for rl in s.find_all(class_=re.compile(r"resume-list|timeline", re.I)):
            timeline_lis.extend(rl.find_all("li", recursive=False))
        if not timeline_lis:
            timeline_lis = s.find_all("li", class_=re.compile(r"timeline", re.I))

        if timeline_lis:
            for tli in timeline_lis:
                date_el = tli.find(class_=re.compile(r"timeline-image|date|year", re.I))
                date_text = clean_text(date_el.get_text()) if date_el else ""
                h_els = tli.find_all(["h4", "h3", "h5", "strong"])
                title_text = ""
                sub_text = ""
                for h in h_els:
                    ht = clean_text(h.get_text())
                    if ht == date_text:
                        continue
                    if not title_text:
                        title_text = ht
                    elif not sub_text:
                        sub_text = ht
                desc_el = tli.find("p")
                desc_text = clean_text(desc_el.get_text()) if desc_el else ""
                t_a = tli.find("a") or (tli if tli.name == "a" else None)
                t_href = clean_text(t_a.get("href", "")) if t_a and t_a.get("href") else ""
                if title_text:
                    key = (title_text.lower(), desc_text[:30].lower())
                    if key not in seen_card_keys:
                        seen_card_keys.add(key)
                        card_items.append({
                            "title": title_text,
                            "desc": desc_text,
                            "tag": date_text,
                            "stack": sub_text,
                            "link": t_href,
                            "href": t_href
                        })

        # 2. Skills / Circular progress meters
        skill_els = s.find_all(class_=re.compile(r"\bskill\b", re.I)) or s.find_all(attrs={"data-percent": True})
        if skill_els and not card_items:
            for sk in skill_els:
                name_el = sk.find(["h4", "h5", "h6", "strong"]) or sk.find("span")
                percent_attr = sk.get("data-percent") or (sk.find(attrs={"data-percent": True}) or {}).get("data-percent")
                percent_el = sk.find(class_=re.compile(r"percent", re.I))
                pct = percent_attr or (clean_text(percent_el.get_text()) if percent_el else "")
                name = clean_text(name_el.get_text()) if name_el else ""
                if name and pct:
                    if name == pct:
                        h = sk.find(["h4", "h5", "h6", "strong"])
                        if h: name = clean_text(h.get_text())
                    key = name.lower()
                    if key not in seen_card_keys:
                        seen_card_keys.add(key)
                        card_items.append({
                            "title": name,
                            "desc": f"Mastery Level: {pct}%",
                            "tag": f"{pct}%",
                            "stack": f"Proficiency: {pct}%"
                        })

        # 3. Portfolio / Projects (e.g. .filtr-item, .portfolio-thumb)
        portfolio_items = s.find_all(class_=re.compile(r"filtr-item|portfolio-thumb", re.I))
        if any("filtr-item" in " ".join(pi.get("class", [])) for pi in portfolio_items):
            portfolio_items = [pi for pi in portfolio_items if "filtr-item" in " ".join(pi.get("class", []))]
        if portfolio_items and not card_items:
            for idx_p, pi in enumerate(portfolio_items):
                th = pi.find(["h3", "h4", "h5", "strong"])
                t_val = clean_text(th.get_text()) if th else f"Project #{idx_p+1}"
                img_el = pi.find("img")
                a_el = pi.find("a")
                img_src = img_el.get("src", "") if img_el else ""
                href = a_el.get("href", "") if a_el else ""
                card_items.append({
                    "title": t_val,
                    "desc": href or f"Portfolio Project #{idx_p+1}",
                    "tag": f"Project #{idx_p+1}",
                    "stack": img_src or href
                })

        # 4. Client Logos / Partners
        logo_imgs = s.find_all("img", class_=re.compile(r"logo|client|partner", re.I))
        if logo_imgs and not card_items:
            for idx_l, img in enumerate(logo_imgs):
                alt = clean_text(img.get("alt", "")) or f"Partner #{idx_l+1}"
                src = img.get("src", "")
                card_items.append({
                    "title": alt.title() if len(alt) < 25 else f"Partner #{idx_l+1}",
                    "desc": f"Client Partner Asset: {src}",
                    "tag": f"Partner {idx_l+1}",
                    "stack": src
                })

        # 5. Reviews / Testimonials
        review_els = s.find_all(class_=re.compile(r"review-wrap|testimonial-wrap|swiper-slide", re.I))
        if any("review-wrap" in " ".join(re_el.get("class", [])) for re_el in review_els):
            review_els = [re_el for re_el in review_els if "review-wrap" in " ".join(re_el.get("class", []))]
        if review_els and not card_items:
            for idx_r, r_el in enumerate(review_els):
                rt = r_el.find(class_=re.compile(r"review-text|testimonial-text", re.I)) or r_el.find("p")
                rn = r_el.find(["h4", "h3", "h5", "strong"])
                img = r_el.find("img")
                r_text = clean_text(rt.get_text()) if rt else ""
                r_author = clean_text(rn.get_text()) if rn else f"Client #{idx_r+1}"
                img_src = img.get("src", "") if img else ""
                card_items.append({
                    "title": r_author,
                    "desc": r_text,
                    "tag": f"Review #{idx_r+1}",
                    "stack": img_src or "5-Star Rating"
                })

        # 6. Social Networks (if social container or footer-social)
        if any(w in s_id for w in ["social", "network"]):
            social_links = s.find_all("a")
            if social_links and not card_items:
                for idx_s, sa in enumerate(social_links):
                    sh = sa.find(["h4", "h5", "span"])
                    sname = clean_text(sh.get_text()) if sh else clean_text(sa.get_text())
                    href = sa.get("href", "#")
                    card_items.append({
                        "title": sname.title() if sname else f"Social #{idx_s+1}",
                        "desc": href,
                        "tag": "Social Profile",
                        "stack": href
                    })

        # 7. Standard Cards / Services / Features (with parent-child deduplication)
        if not card_items:
            # Prefer innermost card wrappers to prevent parent/child duplicate matches
            card_els = s.find_all(class_=re.compile(r"\b(?:card|service-wrap|service-item|service|feature-item|feature|thumb|exhibit|portfolio-item|pricing-card)\b", re.I))
            if not card_els:
                card_els = s.find_all(class_=re.compile(r"col-", re.I))

            for c in card_els:
                if h_tag and (h_tag in c.find_all(["h1", "h2", "h3", "h4"]) or c == h_tag):
                    continue
                ch = c.find(["h3", "h4", "h5", "strong"])
                ctitle = clean_text(ch.get_text()) if ch else ""
                if not ctitle or ctitle.lower() == headline.lower():
                    continue
                cp = c.find("p")
                cdesc = clean_text(cp.get_text()) if cp else ""
                ctag = c.find(class_=re.compile(r"tag|badge|date|year", re.I))
                ctag_text = clean_text(ctag.get_text()) if ctag else ""
                cstack = c.find(class_=re.compile(r"stack|tech|tools", re.I))
                cstack_text = clean_text(cstack.get_text()) if cstack else ""
                c_a = c.find("a") or (c if c.name == "a" else None)
                c_href = clean_text(c_a.get("href", "")) if c_a and c_a.get("href") else ""

                key = (ctitle.lower(), cdesc[:30].lower())
                if key not in seen_card_keys:
                    seen_card_keys.add(key)
                    card_items.append({
                        "title": ctitle,
                        "desc": cdesc,
                        "tag": ctag_text,
                        "stack": cstack_text,
                        "link": c_href,
                        "href": c_href
                    })

        # Check tabs in section (e.g. resume / timeline tabs)
        tabs = []
        for tb in s.find_all(["button", "a"], class_=re.compile(r"nav-link|tab", re.I)):
            t_txt = clean_text(tb.get_text())
            if t_txt and t_txt not in tabs and len(t_txt) < 30:
                tabs.append(t_txt)

        # Check category filter tags (e.g. portfolio work categories)
        filters = []
        filter_els = s.find_all(lambda tag: tag.name in ["li", "button", "a"] and (tag.has_attr("data-filter") or re.search(r"filtr|filter|category", " ".join(tag.get("class", [])))))
        if not filter_els:
            filter_menu = s.find(["ul", "div"], class_=re.compile(r"filter|control|portfolio-menu", re.I))
            if filter_menu:
                filter_els = filter_menu.find_all(["li", "button", "a"])
        for fel in filter_els:
            f_txt = clean_text(fel.get_text())
            if f_txt and f_txt not in filters and 0 < len(f_txt) < 30:
                filters.append(f_txt)

        # Social links extraction
        social_links = []
        if any(w in s_id for w in ["social", "network"]) or s.find(class_=re.compile(r"social", re.I)):
            seen_soc = set()
            for sa in s.find_all("a"):
                stxt = clean_text(sa.get_text())
                shref = sa.get("href", "#")
                if stxt and stxt.lower() not in seen_soc:
                    seen_soc.add(stxt.lower())
                    social_links.append({"platform": stxt.capitalize(), "url": shref})

        cat_name, icon_name = classify_section(s_id, headline)
        if s_id == "info" or any(w in s_id for w in ["contact_info", "reach_us"]):
            disp_name = "Contact Details"
            cat_name = "Direct Reach & Contact"
            icon_name = "Phone"
        elif any(w in s_id for w in ["social", "network"]):
            disp_name = "Social Networks"
            cat_name = "Social Channels"
            icon_name = "Share2"
        elif s_id in ["review", "reviews"]:
            disp_name = "Client Reviews"
            cat_name = "Social Proof & Reviews"
            icon_name = "Star"
        elif headline and 3 < len(headline) < 32:
            disp_name = headline
        elif s_id and len(s_id) > 2:
            disp_name = s_id.replace("_", " ").replace("-", " ").title()
        else:
            disp_name = f"Section {idx+1}"

        sec_data = {
            "title": headline or disp_name,
            "headline": headline or disp_name,
            "badgeText": badge,
            "subtitle": subtitle,
            "subheadline": subtitle,
            "description": narrative,
            "story": story or narrative,
            "themeColor": primary_color
        }

        if tabs:
            sec_data["tabs"] = tabs
        if filters:
            sec_data["filters"] = filters
        if social_links:
            sec_data["socialLinks"] = social_links

        # Buttons
        cta_btns = [clean_text(b.get_text()) for b in s.find_all(["a", "button"], class_=re.compile(r"btn|cta|button", re.I)) if 0 < len(clean_text(b.get_text())) < 25]
        if cta_btns:
            sec_data["primaryCta"] = cta_btns[0]
            if len(cta_btns) > 1:
                sec_data["secondaryCta"] = cta_btns[1]

        # Meta attributes (Role, Years Active, Status, etc. - ONLY real ones)
        if meta_items:
            sec_data["metaItems"] = meta_items
            for mi in meta_items:
                clean_k = re.sub(r"[^a-zA-Z0-9]", "", mi["label"]).lower()
                if "role" in clean_k: sec_data["role"] = mi["value"]
                elif "year" in clean_k: sec_data["yearsActive"] = mi["value"]
                elif "status" in clean_k: sec_data["status"] = mi["value"]
                elif "base" in clean_k or "loc" in clean_k: sec_data["location"] = mi["value"]

        # Specialized handling for direct contact info section
        if s_id == "info" or any(w in s_id for w in ["contact_info", "reach_us"]):
            sec_data["title"] = "Contact Information"
            sec_data["headline"] = "Contact Information"
            card_items = []
            for h in s.find_all(["h4", "h3", "h5", "p", "span", "a"]):
                txt = clean_text(h.get_text())
                if "@" in txt and not sec_data.get("email"):
                    sec_data["email"] = txt
                elif any(ch.isdigit() for ch in txt) and sum(ch.isdigit() for ch in txt) >= 7 and not sec_data.get("phone"):
                    sec_data["phone"] = txt
                elif any(w in txt.lower() for w in ["brooklyn", "st", "ave", "road", "street", "ny", "suite", "floor", "box", "city", "usa", "uk"]) and not sec_data.get("address"):
                    sec_data["address"] = txt

        # Cards (Support up to 20 items without arbitrary 6-item cap)
        if card_items:
            sec_data["cards"] = card_items[:20]
            for c_i, card in enumerate(card_items[:20]):
                sec_data[f"card{c_i+1}_title"] = card["title"]
                sec_data[f"card{c_i+1}_desc"] = card["desc"]
                if card["tag"]: sec_data[f"card{c_i+1}_tag"] = card["tag"]
                if card["stack"]: sec_data[f"card{c_i+1}_stack"] = card["stack"]
                if card.get("link"):
                    sec_data[f"card{c_i+1}_link"] = card["link"]
                    sec_data[f"card{c_i+1}_href"] = card["link"]

        # Form
        if has_form:
            sec_data["hasForm"] = True
            sec_data["buttonText"] = submit_text or "Submit"
            if len(inputs) > 0 and inputs[0]: sec_data["namePlaceholder"] = inputs[0]
            if len(inputs) > 1 and inputs[1]: sec_data["emailPlaceholder"] = inputs[1]
            if textareas and textareas[0]: sec_data["messagePlaceholder"] = textareas[0]
            if has_phone and phone_val:
                sec_data["hasPhone"] = True
                sec_data["phone"] = phone_val
            if has_address and address_val:
                sec_data["hasAddress"] = True
                sec_data["address"] = address_val

        # Contact Info fields (Phone / Email / Address from info section)
        phone_in_s = s.find(class_=re.compile(r"phone", re.I))
        email_in_s = s.find(class_=re.compile(r"email", re.I))
        address_in_s = s.find(class_=re.compile(r"address", re.I))
        if phone_in_s and not sec_data.get("phone"): sec_data["phone"] = clean_text(phone_in_s.get_text())
        if email_in_s and not sec_data.get("email"): sec_data["email"] = clean_text(email_in_s.get_text())
        if address_in_s and not sec_data.get("address"): sec_data["address"] = clean_text(address_in_s.get_text())

        # Universal Leaf Text Collector: Crawl all remaining text elements so NOTHING is missed
        captured_texts = set()
        for v in [sec_data.get("title"), sec_data.get("headline"), sec_data.get("subtitle"),
                  sec_data.get("subheadline"), sec_data.get("badgeText"), sec_data.get("description"),
                  sec_data.get("story"), sec_data.get("phone"), sec_data.get("email"), sec_data.get("address"),
                  sec_data.get("buttonText"), sec_data.get("primaryCta"), sec_data.get("secondaryCta")]:
            if v and isinstance(v, str):
                captured_texts.add(v.lower().strip())
        for c in card_items:
            for cv in [c.get("title"), c.get("desc"), c.get("tag"), c.get("stack")]:
                if cv and isinstance(cv, str):
                    captured_texts.add(cv.lower().strip())
        for tb in tabs:
            captured_texts.add(tb.lower().strip())
        for flt in filters:
            captured_texts.add(flt.lower().strip())
        for sl in social_links:
            captured_texts.add(sl.get("platform", "").lower().strip())

        text_items = []
        seen_leaf = set()
        for el in s.find_all(True):
            if el.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 'li', 'button', 'label', 'strong', 'em', 'small', 'div']:
                has_child_text = any(child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 'li', 'button', 'label', 'strong'] for child in el.find_all(True))
                if not has_child_text:
                    ltxt = clean_text(el.get_text())
                    if ltxt and len(ltxt) > 1:
                        lt_lower = ltxt.lower()
                        is_cap = any(lt_lower == cap or (len(lt_lower) > 10 and lt_lower in cap) for cap in captured_texts)
                        if not is_cap and lt_lower not in seen_leaf:
                            seen_leaf.add(lt_lower)
                            text_items.append({
                                "id": f"txt_{len(text_items)+1}",
                                "tag": el.name,
                                "label": f"<{el.name}> Text",
                                "text": ltxt,
                                "originalText": ltxt
                            })
        if text_items:
            sec_data["textItems"] = text_items

        sections[s_id] = sec_data
        sections_list.append({
            "id": s_id,
            "name": disp_name,
            "category": cat_name,
            "icon": icon_name,
            "desc": f"Showcase component with {len(card_items)} items" if card_items else (f"Interactive form with {len(inputs)} fields" if has_form else "Content presentation section"),
            "targetSection": s_id
        })

    # 4. Footer Section
    footer_el = soup.find("footer")
    f_text = clean_text(footer_el.get_text()) if footer_el else ""
    c_match = re.search(r'(?:©|\(c\)|copyright)\s*\d{4}[^.\n]*', f_text, re.I)
    copyright_text = c_match.group(0) if c_match else f"© 2026 {brand_name}. All rights reserved."
    sections["footer"] = {
        "brandName": brand_name,
        "tagline": "All rights reserved.",
        "copyright": copyright_text,
        "themeColor": primary_color
    }
    sections_list.append({
        "id": "footer",
        "name": "Website Footer",
        "category": "Footer & Record",
        "icon": "Shield",
        "desc": "Site footer with brand signature, legal copyright, and navigation links",
        "targetSection": "footer"
    })

    # Master Brand
    contact_sec = next((s for s in sections.values() if s.get("hasForm")), {})
    info_sec = sections.get("info", {})
    brand = {
        "business_name": brand_name,
        "logo_text": re.sub(r"[^A-Z0-9]", "", brand_name.upper())[:7] or "BRAND",
        "tagline": page_title,
        "primary_color": primary_color
    }
    phone_val = contact_sec.get("phone") or info_sec.get("phone")
    email_val = contact_sec.get("email") or info_sec.get("email")
    if phone_val:
        brand["contact_phone"] = phone_val
    if email_val:
        brand["contact_email"] = email_val

    # Detect framework from source files or template model
    detected_framework = "HTML5"
    if any(k.endswith(".vue") for k in (all_source_files or {})):
        detected_framework = "Vue"
    elif any(k.endswith((".jsx", ".tsx")) for k in (all_source_files or {})):
        detected_framework = "React"
    elif any(k.endswith(".svelte") for k in (all_source_files or {})):
        detected_framework = "Svelte"
    elif template and template.framework:
        fw_val = template.framework.value.lower()
        if fw_val == "vue":
            detected_framework = "Vue"
        elif fw_val == "react":
            detected_framework = "React"
        elif fw_val == "nextjs":
            detected_framework = "Next.js"
        elif fw_val == "angular":
            detected_framework = "Angular"
        elif fw_val == "svelte":
            detected_framework = "Svelte"
        elif fw_val == "astro":
            detected_framework = "Astro"
        else:
            detected_framework = "HTML5"

    return {
        "status": "success",
        "template_id": template_id,
        "framework": detected_framework,
        "brand": brand,
        "sections": sections,
        "sections_list": sections_list
    }


@router.post("/live/{template_id}/fork-draft")
async def fork_live_preview_draft(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates an isolated copy of a marketplace template in the user's private drafts/projects.
    Ensures the original marketplace template remains 100% pristine and untouched.
    """
    from app.models.template import Template, TemplateStatus
    from app.repositories.template_repo import TemplateRepository
    from app.core.local_project_manager import local_project_manager
    from app.core.storage import storage
    from app.models.stored_file import StoredFile

    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        template = await template_repo.get_by_slug(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # If the user is already viewing an owned DRAFT, keep working on it
    if current_user and template.status == TemplateStatus.DRAFT and template.seller_id == current_user.id:
        return {
            "status": "success",
            "template_id": str(template.id),
            "draft_id": str(template.id),
            "draft_slug": template.slug,
            "title": template.title,
            "is_new_clone": False,
            "message": "Already working on your private draft"
        }

    slug_base = template.slug.split("-custom-")[0].split("-draft-")[0]
    existing_draft = None
    if current_user:
        ed_res = await db.execute(
            select(Template).where(
                Template.seller_id == current_user.id,
                Template.status == TemplateStatus.DRAFT,
                Template.slug.like(f"{slug_base}-draft-%")
            )
        )
        existing_draft = ed_res.scalars().first()

    if existing_draft:
        return {
            "status": "success",
            "template_id": str(existing_draft.id),
            "draft_id": str(existing_draft.id),
            "draft_slug": existing_draft.slug,
            "title": existing_draft.title,
            "is_new_clone": False,
            "message": "Continuing on your existing private draft"
        }

    # Create new draft copy
    new_slug = f"{slug_base}-draft-{uuid.uuid4().hex[:6]}"
    new_title = f"{template.title} (Draft)"
    new_template = Template(
        title=new_title,
        short_description=template.short_description,
        description=template.description,
        slug=new_slug,
        price=template.price,
        original_price=template.original_price,
        is_free=template.is_free,
        is_on_sale=template.is_on_sale,
        category_id=template.category_id,
        status=TemplateStatus.DRAFT,
        is_marketplace=False,
        template_origin="custom_draft",
        seller_id=current_user.id,
        thumbnail_url=template.thumbnail_url,
        preview_url=template.preview_url,
        tags=template.tags,
        framework=template.framework,
        pages_count=template.pages_count,
        has_dark_mode=template.has_dark_mode,
        is_responsive=template.is_responsive,
        is_rtl_supported=template.is_rtl_supported,
        is_ai_ready=True,
        compatibility=template.compatibility,
        version=template.version,
        license_type=template.license_type,
        industry=template.industry,
        color_scheme=template.color_scheme,
        seo_keywords=template.seo_keywords,
        included_pages=template.included_pages,
        download_assets=template.download_assets.copy() if template.download_assets else {}
    )
    db.add(new_template)
    await db.flush()

    # Clone local files on disk
    local_project_manager.clone_project(template.slug or template.id, new_template.id, new_template.slug, new_template.title)

    # Warm preview directory if needed
    src_preview = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template.id))
    dst_preview = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(new_template.id))
    if os.path.isdir(src_preview) and not os.path.exists(dst_preview):
        try:
            shutil.copytree(src_preview, dst_preview)
        except Exception:
            pass

    await db.commit()

    return {
        "status": "success",
        "template_id": str(new_template.id),
        "draft_id": str(new_template.id),
        "draft_slug": new_template.slug,
        "title": new_template.title,
        "is_new_clone": True,
        "message": f"Template copied to your private draft ({new_template.title}). The marketplace version is completely protected."
    }


@router.post("/live/{template_id}/edit-manual")
async def edit_live_preview_manual(
    template_id: str,
    request: ManualEditRequest,
    raw_request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    import zipfile
    import io
    import shutil
    import tempfile
    from app.models.template import Template, TemplateStatus
    from app.core.storage import storage
    
    # Try recovering current_user from raw request Authorization header if dependency didn't resolve
    if not current_user:
        auth_hdr = raw_request.headers.get("authorization") or raw_request.headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            try:
                from app.core.security import decode_token
                payload = decode_token(auth_hdr[7:].strip())
                if payload and payload.get("sub"):
                    from app.repositories.user_repo import UserRepository
                    u_repo = UserRepository(db)
                    current_user = await u_repo.get_by_id(uuid.UUID(payload["sub"]))
            except Exception:
                pass

    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    original_template_id = str(template.id)
    is_new_clone = False

    # If the template is PUBLISHED or belongs to another user, clone/fork it so the user modifies their own private DRAFT copy
    is_user_owned_draft = (
        template.status == TemplateStatus.DRAFT 
        and current_user 
        and template.seller_id == current_user.id
    )

    clean_tags = [t for t in (template.tags or []) if t != "studio-project"]
    if "customized-draft" not in clean_tags:
        clean_tags.append("customized-draft")

    if not is_user_owned_draft:
        existing_draft = None
        if current_user:
            slug_prefix = template.slug.split("-custom-")[0].split("-draft-")[0]
            from sqlalchemy import or_
            ed_res = await db.execute(
                select(Template).where(
                    Template.seller_id == current_user.id,
                    Template.status == TemplateStatus.DRAFT,
                    or_(
                        Template.slug.like(f"{slug_prefix}-custom-%"),
                        Template.slug.like(f"{slug_prefix}-draft-%")
                    )
                )
            )
            existing_draft = ed_res.scalars().first()
            
        if existing_draft:
            template = existing_draft
            template_id = str(existing_draft.id)
            template.template_origin = "custom_draft"
            template.is_marketplace = False
            template.tags = clean_tags
        else:
            is_new_clone = True
            custom_bname = request.business_name.strip() if request.business_name else ""
            custom_title = f"{custom_bname} (Customized)" if custom_bname else f"Customized {template.title}"
            new_template = Template(
                title=custom_title,
                short_description=template.short_description,
                description=template.description,
                slug=f"{template.slug.split('-custom-')[0].split('-draft-')[0]}-custom-{uuid.uuid4().hex[:6]}",
                price=template.price,
                original_price=template.original_price,
                is_free=template.is_free,
                is_on_sale=template.is_on_sale,
                category_id=template.category_id,
                status=TemplateStatus.DRAFT,
                is_marketplace=False,
                template_origin="custom_draft",
                seller_id=current_user.id if current_user else template.seller_id,
                thumbnail_url=template.thumbnail_url,
                preview_url=template.preview_url,
                tags=clean_tags,
                framework=template.framework,
                pages_count=template.pages_count,
                has_dark_mode=template.has_dark_mode,
                is_responsive=template.is_responsive,
                is_rtl_supported=template.is_rtl_supported,
                is_ai_ready=True,
                compatibility=template.compatibility,
                version=template.version,
                license_type=template.license_type,
                industry=template.industry,
                color_scheme=template.color_scheme,
                seo_keywords=template.seo_keywords,
                included_pages=template.included_pages,
                download_assets=template.download_assets.copy() if template.download_assets else {}
            )
            db.add(new_template)
            await db.flush()
            template = new_template
            template_id = str(new_template.id)

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
        
    match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
    if not match:
        raise HTTPException(status_code=400, detail="External/Invalid zip storage format")
    file_id = uuid.UUID(match.group(1))
        
    result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
    stored_file = result.scalar_one_or_none()
    if not stored_file:
        raise HTTPException(status_code=404, detail="Source template archive file not found")

    zip_data = stored_file.data if stored_file and stored_file.data else None
    if not zip_data:
        stored_file_data = await storage.get_file(db, file_id)
        if not stored_file_data:
            raise HTTPException(status_code=404, detail="Source template archive data not found")
        zip_data = stored_file_data[0]
    
    # 1. Read all editable files in the ZIP (HTML, JS, JSX, CSS)
    files_dict = {}
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        for name in z_in.namelist():
            is_build = any(d in name.replace("\\", "/").split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
            if (name.endswith(".html") or name.endswith(".jsx") or name.endswith(".js") or name.endswith(".css") or name.endswith(".tsx") or name.endswith(".ts")) and not is_build:
                try:
                    files_dict[name] = z_in.read(name).decode("utf-8", errors="ignore")
                except Exception:
                    pass

    if not files_dict:
        raise HTTPException(status_code=400, detail="Could not locate code files in template archive")

    updated_filenames = set()

    def smart_replace_in_code(code: str, old_text: str, new_text: str) -> tuple[str, bool]:
        if not old_text or not new_text or str(old_text).strip() == str(new_text).strip():
            return code, False
        ot = str(old_text).strip()
        nt = str(new_text).strip()
        # 1. Exact match
        if ot in code:
            return code.replace(ot, nt, 1), True
        # 2. Case variations
        if ot.upper() in code:
            return code.replace(ot.upper(), nt.upper(), 1), True
        if ot.lower() in code:
            return code.replace(ot.lower(), nt.lower(), 1), True
        if ot.title() in code:
            return code.replace(ot.title(), nt.title(), 1), True
        # 3. Flexible JSX/HTML matching across nested tags and multiline whitespace
        words = [re.escape(w) for w in re.split(r'\s+', ot) if w]
        if len(words) >= 2:
            pattern = r'(?:\s*<[^>]+>\s*|\s+)+'.join(words)
            m = re.search(pattern, code, re.I)
            if m:
                new_code = code[:m.start()] + nt + code[m.end():]
                return new_code, True
        return code, False

    def apply_smart_replace(old_val: str, new_val: str):
        if not old_val or not new_val or str(old_val).strip() == str(new_val).strip():
            return
        ov = str(old_val).strip()
        nv = str(new_val).strip()
        for fname in files_dict:
            updated_code, replaced = smart_replace_in_code(files_dict[fname], ov, nv)
            if replaced:
                files_dict[fname] = updated_code
                updated_filenames.add(fname)

    # 2. Fast, Guaranteed Direct Deterministic Replacements across all files
    try:
        extracted = await get_live_preview_extracted_data(original_template_id, db)
    except Exception as ex_ext:
        logger.warning(f"Could not pre-extract sections for direct replacement: {ex_ext}")
        extracted = {}

    orig_brand = extracted.get("brand", {}).get("business_name")
    orig_primary_color = extracted.get("brand", {}).get("primary_color")
    orig_sections = extracted.get("sections", {})

    # (a) Business Name Replacement across all case variations
    if request.business_name:
        new_bname = request.business_name.strip()
        names_to_replace = []
        if orig_brand and orig_brand.strip() and orig_brand.strip() != new_bname:
            ob = orig_brand.strip()
            names_to_replace.extend([
                (ob, new_bname),
                (ob.upper(), new_bname.upper()),
                (ob.lower(), new_bname.lower()),
                (ob.title(), new_bname.title()),
            ])
            # Also if original brand was multi-word like "Jerome Pascal", also match "Jerome" or "Pascal" in isolated headers
            parts = ob.split()
            if len(parts) > 1:
                names_to_replace.append((ob.replace(" ", "<br>"), new_bname))
                names_to_replace.append((ob.upper().replace(" ", "<br>"), new_bname.upper()))
        if template.title and template.title.strip() != new_bname:
            tb = template.title.strip()
            names_to_replace.extend([
                (tb, new_bname),
                (tb.upper(), new_bname.upper()),
                (tb.lower(), new_bname.lower()),
                (tb.title(), new_bname.title()),
            ])

        for old_str, new_str in names_to_replace:
            if len(old_str) > 1:
                apply_smart_replace(old_str, new_str)

    # (b) Primary Theme Color Replacement
    if request.primary_color:
        new_color = request.primary_color.strip()
        colors_to_replace = set()
        if orig_primary_color and orig_primary_color.lower() != new_color.lower():
            colors_to_replace.add(orig_primary_color)
            colors_to_replace.add(orig_primary_color.lower())
            colors_to_replace.add(orig_primary_color.upper())

        for c_old in colors_to_replace:
            for fname in files_dict:
                if fname.endswith(".css") or fname.endswith(".html") or fname.endswith(".jsx") or fname.endswith(".tsx"):
                    if c_old in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(c_old, new_color)
                        updated_filenames.add(fname)

    # (c) Global Contact Email & Phone
    if request.contact_email:
        new_email = request.contact_email.strip()
        for s_data in orig_sections.values():
            if isinstance(s_data, dict) and s_data.get("email"):
                old_email = s_data["email"].strip()
                if old_email and old_email != new_email:
                    apply_smart_replace(old_email, new_email)

    if request.contact_phone:
        new_phone = request.contact_phone.strip()
        for s_data in orig_sections.values():
            if isinstance(s_data, dict) and s_data.get("phone"):
                old_phone = s_data["phone"].strip()
                if old_phone and old_phone != new_phone:
                    apply_smart_replace(old_phone, new_phone)

    # (d) Section-by-Section Edits (Titles, Subtitles, Descriptions, CTAs, Cards, Tabs, Filters, Text Items)
    if request.page_edits and isinstance(request.page_edits, dict):
        for p_name, p_data in request.page_edits.items():
            if not isinstance(p_data, dict):
                continue
            orig_s = orig_sections.get(p_name, {})

            # Logo Monogram / Code
            new_logo = (p_data.get("logoText") or p_data.get("logo_text") or "").strip()
            old_logo = (orig_s.get("logoText") or orig_s.get("logo_text") or extracted.get("brand", {}).get("logo_text") or "").strip()
            if new_logo and old_logo and new_logo != old_logo:
                apply_smart_replace(old_logo, new_logo)

            # Title / Headline
            new_title = (p_data.get("title") or p_data.get("headline") or p_data.get("brandName") or "").strip()
            old_title = (orig_s.get("title") or orig_s.get("headline") or orig_s.get("brandName") or "").strip()
            if new_title and old_title and new_title != old_title:
                apply_smart_replace(old_title, new_title)

            # Badge Text
            new_badge = (p_data.get("badgeText") or p_data.get("badge") or "").strip()
            old_badge = (orig_s.get("badgeText") or orig_s.get("badge") or "").strip()
            if new_badge and old_badge and new_badge != old_badge:
                apply_smart_replace(old_badge, new_badge)

            # Subtitle / Subheadline
            new_sub = (p_data.get("subtitle") or p_data.get("subheadline") or "").strip()
            old_sub = (orig_s.get("subtitle") or orig_s.get("subheadline") or "").strip()
            if new_sub and old_sub and new_sub != old_sub:
                apply_smart_replace(old_sub, new_sub)

            # Description / Story
            new_desc = (p_data.get("description") or p_data.get("story") or "").strip()
            old_desc = (orig_s.get("description") or orig_s.get("story") or "").strip()
            if new_desc and old_desc and new_desc != old_desc:
                apply_smart_replace(old_desc, new_desc)

            # CTA Text / Primary CTA / Button Text
            new_cta = (p_data.get("cta_text") or p_data.get("primaryCta") or p_data.get("buttonText") or "").strip()
            old_cta = (orig_s.get("primaryCta") or orig_s.get("buttonText") or orig_s.get("ctaText") or "").strip()
            if new_cta and old_cta and new_cta != old_cta:
                apply_smart_replace(old_cta, new_cta)

            # CTA Links
            new_cta_link = (p_data.get("ctaLink") or p_data.get("primaryCtaLink") or "").strip()
            old_cta_link = (orig_s.get("ctaLink") or orig_s.get("primaryCtaLink") or "").strip()
            if new_cta_link and old_cta_link and new_cta_link != old_cta_link:
                apply_smart_replace(old_cta_link, new_cta_link)

            # Secondary CTA
            new_sec_cta = (p_data.get("secondaryCta") or "").strip()
            old_sec_cta = (orig_s.get("secondaryCta") or "").strip()
            if new_sec_cta and old_sec_cta and new_sec_cta != old_sec_cta:
                apply_smart_replace(old_sec_cta, new_sec_cta)

            new_sec_cta_link = (p_data.get("secondaryCtaLink") or "").strip()
            old_sec_cta_link = (orig_s.get("secondaryCtaLink") or "").strip()
            if new_sec_cta_link and old_sec_cta_link and new_sec_cta_link != old_sec_cta_link:
                apply_smart_replace(old_sec_cta_link, new_sec_cta_link)

            # Nav Links
            new_nav_links = p_data.get("navLinks") or p_data.get("nav_links") or []
            old_nav_links = orig_s.get("navLinks") or orig_s.get("nav_links") or []
            if isinstance(new_nav_links, list) and isinstance(old_nav_links, list):
                for o_lnk, n_lnk in zip(old_nav_links, new_nav_links):
                    apply_smart_replace(o_lnk, n_lnk)

            # Tabs
            new_tabs = p_data.get("tabs", [])
            old_tabs = orig_s.get("tabs", [])
            if isinstance(new_tabs, list) and isinstance(old_tabs, list):
                for o_tab, n_tab in zip(old_tabs, new_tabs):
                    apply_smart_replace(o_tab, n_tab)

            # Category Filters
            new_filters = p_data.get("filters", [])
            old_filters = orig_s.get("filters", [])
            if isinstance(new_filters, list) and isinstance(old_filters, list):
                for o_f, n_f in zip(old_filters, new_filters):
                    apply_smart_replace(o_f, n_f)

            # Cards
            new_cards = p_data.get("cards", [])
            old_cards = orig_s.get("cards", [])
            if isinstance(new_cards, list) and isinstance(old_cards, list):
                for o_card, n_card in zip(old_cards, new_cards):
                    if isinstance(o_card, dict) and isinstance(n_card, dict):
                        apply_smart_replace(o_card.get("title"), n_card.get("title"))
                        apply_smart_replace(o_card.get("desc"), n_card.get("desc"))
                        apply_smart_replace(o_card.get("tag"), n_card.get("tag"))
                        apply_smart_replace(o_card.get("stack"), n_card.get("stack"))
                        apply_smart_replace(o_card.get("link"), n_card.get("link"))
                        apply_smart_replace(o_card.get("href"), n_card.get("href"))
                        apply_smart_replace(o_card.get("url"), n_card.get("url"))

                # Extra cards added by user beyond original count: replicate markup of the reference card
                if len(new_cards) > len(old_cards) and len(old_cards) > 0:
                    last_ref = old_cards[-1]
                    ref_title = (last_ref.get("title") or "").strip()
                    ref_desc = (last_ref.get("desc") or "").strip()

                    for extra_card in new_cards[len(old_cards):]:
                        if not isinstance(extra_card, dict):
                            continue
                        e_title = (extra_card.get("title") or "").strip()
                        e_desc = (extra_card.get("desc") or "").strip()
                        e_tag = (extra_card.get("tag") or "").strip()
                        e_link = (extra_card.get("link") or extra_card.get("href") or "").strip()
                        if not e_title and not e_desc and not e_link:
                            continue

                        for fname, code in list(files_dict.items()):
                            anchor = ref_title if (ref_title and ref_title in code) else (ref_desc if (ref_desc and ref_desc in code) else None)
                            if not anchor:
                                continue

                            idx_anchor = code.find(anchor)
                            tag_start = code.rfind("<div", 0, idx_anchor)
                            if tag_start == -1:
                                tag_start = code.rfind("<li", 0, idx_anchor)
                            if tag_start == -1:
                                tag_start = code.rfind("<article", 0, idx_anchor)
                            if tag_start == -1:
                                tag_start = code.rfind("<a", 0, idx_anchor)

                            if tag_start != -1:
                                tag_sub = code[tag_start:tag_start+10].lower()
                                close_tag = "</div>"
                                if tag_sub.startswith("<li"):
                                    close_tag = "</li>"
                                elif tag_sub.startswith("<article"):
                                    close_tag = "</article>"
                                elif tag_sub.startswith("<a"):
                                    close_tag = "</a>"

                                tag_end = code.find(close_tag, idx_anchor)
                                if tag_end != -1:
                                    tag_end += len(close_tag)
                                    block = code[tag_start:tag_end]
                                    new_block = block
                                    if ref_title and e_title:
                                        new_block = new_block.replace(ref_title, e_title, 1)
                                    if ref_desc and e_desc:
                                        new_block = new_block.replace(ref_desc, e_desc, 1)
                                    if last_ref.get("tag") and e_tag:
                                        new_block = new_block.replace(last_ref.get("tag"), e_tag, 1)
                                    old_l = (last_ref.get("link") or last_ref.get("href") or "").strip()
                                    if old_l and e_link and old_l in new_block:
                                        new_block = new_block.replace(old_l, e_link, 1)
                                    elif e_link and 'href="' in new_block:
                                        new_block = re.sub(r'href=["\'][^"\']*["\']', f'href="{e_link}"', new_block, count=1)

                                    updated_code = code[:tag_end] + "\n\n" + new_block + code[tag_end:]
                                    files_dict[fname] = updated_code
                                    updated_filenames.add(fname)
                                    ref_title = e_title
                                    ref_desc = e_desc
                                    break

            # Text Items
            for ti in p_data.get("textItems", []):
                apply_smart_replace(ti.get("originalText"), ti.get("text"))

            # Direct top-level fields (e.g. card1_link, card1_title, ctaLink, primaryCtaLink)
            for k, val in p_data.items():
                if isinstance(val, str) and val.strip():
                    orig_val = orig_s.get(k)
                    if orig_val and isinstance(orig_val, str) and orig_val.strip() and orig_val != val:
                        apply_smart_replace(orig_val.strip(), val.strip())

        # (e) Persist Custom Element Colors into HTML/CSS files
        color_rules = []
        for p_name, p_data in request.page_edits.items():
            if not isinstance(p_data, dict):
                continue

            sec_sel = f"#{p_name}, .{p_name}, [data-section='{p_name}']"

            # Headline / Section Title color
            h_col = p_data.get("headlineColor") or p_data.get("titleColor")
            if h_col and isinstance(h_col, str) and h_col.strip():
                c = h_col.strip()
                color_rules.append(f"{sec_sel} h1, {sec_sel} h2, {sec_sel} .title, {sec_sel} .hero-title, {sec_sel} .section-title {{ color: {c} !important; }}")

            # Subtitle / Story / Bio / Description color
            sub_col = p_data.get("subtitleColor") or p_data.get("subheadlineColor") or p_data.get("storyColor") or p_data.get("descriptionColor")
            if sub_col and isinstance(sub_col, str) and sub_col.strip():
                c = sub_col.strip()
                color_rules.append(f"{sec_sel} p, {sec_sel} .hero-sub, {sec_sel} .subtitle, {sec_sel} .story-content, {sec_sel} .lead {{ color: {c} !important; }}")

            # Badge / Top Pill / Tag color
            badge_col = p_data.get("badgeColor") or p_data.get("tagColor")
            if badge_col and isinstance(badge_col, str) and badge_col.strip():
                c = badge_col.strip()
                color_rules.append(f"{sec_sel} .badge, {sec_sel} .pill, {sec_sel} .hero-badge, {sec_sel} .status-pill {{ color: {c} !important; border-color: {c}44 !important; }}")

            # Primary CTA / Button color
            cta_col = p_data.get("ctaColor") or p_data.get("primaryCtaColor") or p_data.get("buttonColor")
            if cta_col and isinstance(cta_col, str) and cta_col.strip():
                c = cta_col.strip()
                color_rules.append(f"{sec_sel} .btn-primary, {sec_sel} .hero-cta, {sec_sel} .cta-button, {sec_sel} .primary-btn {{ color: {c} !important; }}")

            # Secondary CTA color
            sec_cta_col = p_data.get("secondaryCtaColor")
            if sec_cta_col and isinstance(sec_cta_col, str) and sec_cta_col.strip():
                c = sec_cta_col.strip()
                color_rules.append(f"{sec_sel} .btn-secondary, {sec_sel} .btn-outline, {sec_sel} .secondary-cta {{ color: {c} !important; }}")

            # Brand Name color
            b_col = p_data.get("brandNameColor")
            if b_col and isinstance(b_col, str) and b_col.strip():
                c = b_col.strip()
                color_rules.append(f".brand-logo, .brand-name, .logo, .navbar-brand, .logo-text, .footer-logo {{ color: {c} !important; }}")

            # Logo Code / Monogram color
            l_col = p_data.get("logoTextColor")
            if l_col and isinstance(l_col, str) and l_col.strip():
                c = l_col.strip()
                color_rules.append(f".brand-code, .logo-monogram, .logo-mark {{ color: {c} !important; }}")

            # Tagline color
            tg_col = p_data.get("taglineColor")
            if tg_col and isinstance(tg_col, str) and tg_col.strip():
                c = tg_col.strip()
                color_rules.append(f"footer p, footer .tagline {{ color: {c} !important; }}")

            # Copyright color
            cp_col = p_data.get("copyrightColor")
            if cp_col and isinstance(cp_col, str) and cp_col.strip():
                c = cp_col.strip()
                color_rules.append(f".copyright, footer small, footer p:last-child {{ color: {c} !important; }}")

            # Contact colors
            for f_key, sel in [("phoneColor", "a[href^='tel:'], .phone, .contact-phone"), ("emailColor", "a[href^='mailto:'], .email, .contact-email"), ("addressColor", ".address, .contact-address, address")]:
                f_val = p_data.get(f_key)
                if f_val and isinstance(f_val, str) and f_val.strip():
                    color_rules.append(f"{sel} {{ color: {f_val.strip()} !important; }}")

            # Cards color rules
            cards = p_data.get("cards", [])
            if isinstance(cards, list):
                for c_idx, c_obj in enumerate(cards):
                    if not isinstance(c_obj, dict):
                        continue
                    n = c_idx + 1
                    card_sel = f"{sec_sel} .card:nth-of-type({n}), {sec_sel} [class*='card']:nth-of-type({n}), {sec_sel} .grid > div:nth-child({n})"
                    if c_obj.get("titleColor"):
                        color_rules.append(f"{card_sel} h1, {card_sel} h2, {card_sel} h3, {card_sel} h4, {card_sel} .card-title, {card_sel} strong {{ color: {c_obj['titleColor'].strip()} !important; }}")
                    if c_obj.get("descColor"):
                        color_rules.append(f"{card_sel} p, {card_sel} .card-desc, {card_sel} .desc {{ color: {c_obj['descColor'].strip()} !important; }}")
                    if c_obj.get("tagColor"):
                        color_rules.append(f"{card_sel} .tag, {card_sel} .badge, {card_sel} .pill {{ color: {c_obj['tagColor'].strip()} !important; }}")
                    if c_obj.get("stackColor"):
                        color_rules.append(f"{card_sel} .stack, {card_sel} small {{ color: {c_obj['stackColor'].strip()} !important; }}")
                    if c_obj.get("boxColor"):
                        color_rules.append(f"{card_sel} {{ background-color: {c_obj['boxColor'].strip()} !important; border-color: {c_obj['boxColor'].strip()}55 !important; }}")
                    if c_obj.get("color"):
                        color_rules.append(f"{card_sel} {{ color: {c_obj['color'].strip()} !important; }}")

        if color_rules:
            custom_css_block = "<style id=\"studio-custom-colors\">\n/* AI Site Studio Custom Text & Element Colors */\n" + "\n".join(color_rules) + "\n</style>"
            for fname, content in list(files_dict.items()):
                if fname.endswith(".html"):
                    if '<style id="studio-custom-colors">' in content:
                        pattern = r'<style id="studio-custom-colors">.*?</style>'
                        files_dict[fname] = re.sub(pattern, custom_css_block, content, flags=re.DOTALL)
                    elif "</head>" in content:
                        files_dict[fname] = content.replace("</head>", f"  {custom_css_block}\n</head>", 1)
                    elif "</body>" in content:
                        files_dict[fname] = content.replace("</body>", f"  {custom_css_block}\n</body>", 1)
                    else:
                        files_dict[fname] = content + "\n" + custom_css_block
                    updated_filenames.add(fname)

    # 3. AI Code Refactor (Step 2): Only invoked when user chooses "AI Save" (request.use_ai=True)
    if request.use_ai:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required to use AI Code Refactoring.")
        files_str = ""
        ordered_files = sorted(
            files_dict.items(),
            key=lambda item: (
                0 if os.path.basename(item[0]).lower() in ("index.html", "app.jsx", "app.tsx", "page.jsx", "main.jsx") else
                1 if item[0].lower().endswith((".html", ".jsx", ".tsx", ".js", ".ts")) else 2,
                len(item[1]),
            ),
        )
        # Keep prompt + requested JSON output beneath the common 8k-token TPM tier.
        # One character is conservatively budgeted as ~4 tokens for source code.
        context_budget = 12_000
        for name, content in ordered_files:
            if context_budget <= 0:
                break
            # Include complete files only; skipping a large generated bundle is safer than
            # handing the model a syntactically truncated component.
            block = f"\n--- FILE: {name} ---\n{content}\n"
            if len(block) > context_budget:
                continue
            files_str += block
            context_budget -= len(block)

        page_edits_str = ""
        if request.page_edits:
            page_edits_str = "\nAlso apply these page-specific content overrides:\n"
            for page_name, edits in request.page_edits.items():
                page_name_clean = page_name.replace(".html", "").replace(".jsx", "").replace(".js", "").replace(".tsx", "").replace(".ts", "")
                page_edits_str += f"- For page/file '{page_name}' (If the template is a single-page template/only has index.html, map these changes to the corresponding section like #{page_name_clean} or the '{page_name_clean}' area inside index.html):\n"
                if edits.get("title"):
                    page_edits_str += f"  * Set main title/header/headline to: \"{edits['title']}\"\n"
                if edits.get("subtitle"):
                    page_edits_str += f"  * Set subtitle / hook text to: \"{edits['subtitle']}\"\n"
                if edits.get("description"):
                    page_edits_str += f"  * Set main body content/description/story to: \"{edits['description']}\"\n"
                if edits.get("cta_text"):
                    page_edits_str += f"  * Set primary Call to Action (CTA) button text to: \"{edits['cta_text']}\"\n"
                if edits.get("cta_link"):
                    page_edits_str += f"  * Set primary Call to Action (CTA) button link/href/action to: \"{edits['cta_link']}\"\n"
                if edits.get("phone"):
                    page_edits_str += f"  * Set phone number to: \"{edits['phone']}\"\n"
                if edits.get("email"):
                    page_edits_str += f"  * Set contact email to: \"{edits['email']}\"\n"
                if edits.get("address"):
                    page_edits_str += f"  * Set address / location to: \"{edits['address']}\"\n"
                if edits.get("tabs") and isinstance(edits["tabs"], list):
                    page_edits_str += f"  * Set section tabs/pills labels to: {edits['tabs']}\n"
                if edits.get("filters") and isinstance(edits["filters"], list):
                    page_edits_str += f"  * Set category filter buttons to: {edits['filters']}\n"
                if edits.get("cards") and isinstance(edits["cards"], list):
                    for idx_c, card in enumerate(edits["cards"]):
                        page_edits_str += f"  * Item/Card #{idx_c+1}: title=\"{card.get('title','')}\", description=\"{card.get('desc','')}\", tag=\"{card.get('tag','')}\", stack=\"{card.get('stack','')}\"\n"
                if edits.get("textItems") and isinstance(edits["textItems"], list):
                    for ti in edits["textItems"]:
                        orig = ti.get("originalText") or ti.get("text")
                        new_t = ti.get("text")
                        if orig and new_t and orig != new_t:
                            page_edits_str += f"  * Replace text snippet \"{orig}\" with: \"{new_t}\"\n"
                        elif not orig and new_t:
                            page_edits_str += f"  * Add new text content element: \"{new_t}\" ({ti.get('label') or 'element'})\n"

        edit_prompt = f"""You are a specialized React/HTML code refactoring tool.
Your task is to take the provided website template files and replace specific business fields and styles with these new values:
- Business Name: {request.business_name}
- About Description: {request.about}
- Primary Theme Color Accent: {request.primary_color}
- Secondary Theme Color Accent: {request.secondary_color}
- Contact Email: {request.contact_email or ""}
- Contact Phone: {request.contact_phone or ""}
{page_edits_str}

Rules:
1. Return a JSON list of search-and-replace blocks. Do NOT return the entire file content.
2. The "find" string must match the target code exactly, including leading spaces and indentation.
3. The "replace" string must contain the updated code to replace it.
4. Replace all occurrences of old business names, descriptions, accent colors, and contact info in the code.
5. If the template is a single-page template (index.html), apply all page/section overrides to the corresponding sections inside index.html.
6. If new items or cards were added that do not yet exist in the file, duplicate the previous item's surrounding HTML/JSX element markup, populate it with the new item's details, and insert it right after the previous item.

Format the JSON response exactly like this:
[
  {{
    "filename": "src/App.tsx",
    "find": "const [title, setTitle] = useState('Old Title');",
    "replace": "const [title, setTitle] = useState('New Title');"
  }}
]

Here are the codebase files:
{files_str}
"""
        def clean_code_response(text: str, language: str) -> str:
            text = text.strip()
            if text.startswith(f"```{language}"):
                text = text.replace(f"```{language}", "", 1)
            elif text.startswith("```"):
                text = text.replace("```", "", 1)
            if text.endswith("```"):
                text = text[:-3]
            return text.strip()

        try:
            import json
            raw_code = await ai_service._generate_content(edit_prompt, response_mime_type="application/json", feature_name="code_assistant")
            chunks = json.loads(clean_code_response(raw_code, "json"))
            if isinstance(chunks, list):
                for chunk in chunks:
                    filename = chunk.get("filename")
                    find_str = chunk.get("find")
                    replace_str = chunk.get("replace")
                    if not filename or find_str is None or replace_str is None:
                        continue
                    matched_name = None
                    for name in files_dict:
                        if name == filename or name.endswith("/" + filename) or name.endswith("\\" + filename) or os.path.basename(name) == filename:
                            matched_name = name
                            break
                    if matched_name:
                        if find_str in files_dict[matched_name]:
                            files_dict[matched_name] = files_dict[matched_name].replace(find_str, replace_str)
                            updated_filenames.add(matched_name)
                        else:
                            cleaned_find = find_str.strip()
                            if cleaned_find and cleaned_find in files_dict[matched_name]:
                                files_dict[matched_name] = files_dict[matched_name].replace(cleaned_find, replace_str.strip())
                                updated_filenames.add(matched_name)
        except Exception as e_ai:
            logger.warning(f"AI edit refactor fallback notice: {e_ai}")
    else:
        logger.info("Manual edit direct save: use_ai=False - applied Step 1 fast direct replacements without invoking AI LLM.")

    # If no files updated by AI or direct text, update business name and primary color directly
    if not updated_filenames:
        for name in files_dict:
            if name.endswith(".html") or name.endswith(".jsx") or name.endswith(".tsx"):
                files_dict[name] = files_dict[name].replace(template.title or "Port", request.business_name)
                updated_filenames.add(name)

    # 4. Overwrite files in ZIP (and strip stale pre-compiled build artifacts like dist/ so updated source files are authoritative)
    new_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                norm_f = item.filename.replace("\\", "/").strip("/").lower()
                f_parts = norm_f.split("/")
                if any(p in ("dist", "build", ".output", "out") for p in f_parts[:-1]) or norm_f in ("dist", "build", ".output", "out"):
                    continue
                content = z_in.read(item.filename)
                if item.filename in updated_filenames:
                    content = files_dict[item.filename].encode("utf-8")
                z_out.writestr(item, content)
                
    new_zip_bytes = new_zip_buffer.getvalue()
    
    # 5. Save the updated ZIP back to the database as an isolated StoredFile
    new_stored_file = StoredFile(
        storage_key=f"templates/{uuid.uuid4().hex}/customized.zip",
        original_filename=f"customized_{stored_file.original_filename or 'template.zip'}",
        content_type=stored_file.content_type or "application/zip",
        size=len(new_zip_bytes),
        data=new_zip_bytes
    )
    db.add(new_stored_file)
    await db.flush()
    template.download_assets = {
        "zip": f"/api/v1/files/{new_stored_file.id}"
    }
    if request.business_name and request.business_name.strip():
        template.title = f"{request.business_name.strip()} (Customized)"
    elif not template.title.startswith("Customized ") and "(Customized)" not in template.title:
        template.title = f"Customized {template.title}"

    # Automatically generate visual snapshot thumbnail
    try:
        from app.services.screenshot_service import screenshot_service
        cat_name = "Modern Website"
        if hasattr(template, "category") and template.category:
            cat_name = template.category.name if hasattr(template.category, "name") else str(template.category)
        thumb_url = screenshot_service.save_thumbnail(
            template_id=str(template.id),
            title=template.title or "Custom Website",
            framework=template.framework or "HTML",
            category=cat_name,
        )
        template.thumbnail_url = thumb_url
    except Exception as thumb_err:
        logger.warning(f"Could not auto-generate thumbnail: {thumb_err}")

    db.add(template)
    await db.flush()
    
    # 6. Extract updated files ONLY into this user draft's isolated live preview directory
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    shutil.rmtree(preview_dir, ignore_errors=True)
    os.makedirs(preview_dir, exist_ok=True)
    from app.services.security_scanner import security_scanner
    security_scanner.sanitize_extract_zip(new_zip_bytes, Path(preview_dir))

    # Purge any stale pre-compiled build output directories from preview_dir
    for bf in ["dist", "build", ".output", "out"]:
        b_path = os.path.join(preview_dir, bf)
        if os.path.exists(b_path):
            shutil.rmtree(b_path, ignore_errors=True)
        for root, dirs, _ in list(os.walk(preview_dir)):
            if bf in dirs:
                shutil.rmtree(os.path.join(root, bf), ignore_errors=True)

    # Auto-flatten single wrapper subfolder in preview_dir if present
    subitems = [os.path.join(preview_dir, i) for i in os.listdir(preview_dir) if not i.startswith(".")]
    if len(subitems) == 1 and os.path.isdir(subitems[0]):
        inner = subitems[0]
        for s_item in os.listdir(inner):
            src_f = os.path.join(inner, s_item)
            dst_f = os.path.join(preview_dir, s_item)
            if os.path.exists(dst_f):
                if os.path.isdir(dst_f):
                    shutil.rmtree(dst_f, ignore_errors=True)
                else:
                    os.remove(dst_f)
            shutil.move(src_f, dst_f)
        try:
            os.rmdir(inner)
        except Exception:
            pass

    # Also persist updated code AND ALL media/image assets into local_project_manager under the draft's slug
    try:
        from app.core.local_project_manager import local_project_manager
        all_save_files = {}
        with zipfile.ZipFile(io.BytesIO(new_zip_bytes), "r") as z_all:
            for zinfo in z_all.infolist():
                if not zinfo.is_dir() and not any(d in zinfo.filename.replace("\\", "/").split("/") for d in ["node_modules", ".git", "__MACOSX"]):
                    try:
                        all_save_files[zinfo.filename] = z_all.read(zinfo.filename)
                    except Exception:
                        pass

        local_project_manager.save_project_revision(
            template_id=template.id,
            files=all_save_files,
            instruction="Manual edits applied in Live Preview editor",
            slug=template.slug
        )

        # Auto-flatten single wrapper subfolder in latest/ if present so assets and HTML are at root level
        latest_dir = local_project_manager.get_local_project_dir(template.slug or template.id, version="latest")
        if latest_dir and os.path.isdir(str(latest_dir)):
            for bf in ["dist", "build", ".output", "out"]:
                b_path = os.path.join(str(latest_dir), bf)
                if os.path.exists(b_path):
                    shutil.rmtree(b_path, ignore_errors=True)
            subitems = [os.path.join(str(latest_dir), i) for i in os.listdir(str(latest_dir)) if not i.startswith(".")]
            if len(subitems) == 1 and os.path.isdir(subitems[0]):
                inner = subitems[0]
                for s_item in os.listdir(inner):
                    src_f = os.path.join(inner, s_item)
                    dst_f = os.path.join(str(latest_dir), s_item)
                    if os.path.exists(dst_f):
                        if os.path.isdir(dst_f):
                            shutil.rmtree(dst_f, ignore_errors=True)
                        else:
                            os.remove(dst_f)
                    shutil.move(src_f, dst_f)
                try:
                    os.rmdir(inner)
                except Exception:
                    pass
    except Exception as save_err:
        logger.warning(f"Could not persist manual edit to local_project_manager: {save_err}")
            
    # Commit session changes
    await db.commit()

    # 7. Invalidate template caches in memory and Redis so fresh customized code is immediately served
    invalidate_preview_template_cache(str(template.id))
    invalidate_preview_template_cache(str(template_id))
    if template.slug:
        invalidate_preview_template_cache(template.slug)
    if original_template_id:
        invalidate_preview_template_cache(original_template_id)
    try:
        from app.core.redis import cache_delete
        await cache_delete(f"template:{template.id}")
        await cache_delete(f"template:{template.slug}")
        await cache_delete(f"template:{original_template_id}")
    except Exception:
        pass
    
    return {"status": "success", "template_id": str(template_id), "title": template.title, "thumbnail_url": template.thumbnail_url, "original_template_id": original_template_id}




class ApplyThemeColorRequest(BaseModel):
    primary_color: str = Field(min_length=3, max_length=30)
    secondary_color: Optional[str] = None
    section_id: Optional[str] = None


@router.post("/live/{template_id}/apply-theme-color")
async def apply_live_preview_theme_color(
    template_id: str,
    request: ApplyThemeColorRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Applies theme color changes directly into the website code (CSS variables, stylesheets, and HTML meta tags)
    both on local disk (latest/ & revisions/) and in the stored template zip file.
    """
    import os
    import re
    import io
    import json
    import zipfile
    import uuid
    import tempfile
    import shutil
    from pathlib import Path
    from app.repositories.template_repo import TemplateRepository
    from app.core.local_project_manager import local_project_manager
    from app.core.storage import storage
    from app.models.stored_file import StoredFile

    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        template = await template_repo.get_by_slug(template_id)

    local_dir = local_project_manager.get_local_project_dir(template_id, version="latest")
    if not local_dir and template and template.slug:
        local_dir = local_project_manager.get_local_project_dir(template.slug, version="latest")

    if not template and not local_dir:
        raise HTTPException(status_code=404, detail="Template not found")

    new_color = request.primary_color.strip()
    clean_hex = new_color.lstrip("#")
    if len(clean_hex) == 3:
        clean_hex = "".join([c * 2 for c in clean_hex])
    if len(clean_hex) != 6:
        clean_hex = "4f46e5"

    hex_formatted = f"#{clean_hex.upper()}"
    try:
        r = int(clean_hex[0:2], 16)
        g = int(clean_hex[2:4], 16)
        b = int(clean_hex[4:6], 16)
    except Exception:
        r, g, b = 79, 70, 229

    r_hover = max(0, int(r * 0.82))
    g_hover = max(0, int(g * 0.82))
    b_hover = max(0, int(b * 0.82))
    hover_hex = f"#{r_hover:02x}{g_hover:02x}{b_hover:02x}".upper()
    border_subtle = f"rgba({r}, {g}, {b}, 0.25)"

    is_new_clone = False
    updated_files = []

    # Universal override block for both CSS stylesheets and HTML <style> tags
    override_rule = (
        f"/* [STUDIO_APPLIED_THEME_COLOR] */\n"
        f":root, :root[data-theme='light'], :root[data-theme='dark'], html, body {{\n"
        f"  --c-primary: {hex_formatted} !important;\n"
        f"  --c-primary-hover: {hover_hex} !important;\n"
        f"  --color-primary: {hex_formatted} !important;\n"
        f"  --color-primary-dark: {hover_hex} !important;\n"
        f"  --color-primary-hover: {hover_hex} !important;\n"
        f"  --primary: {hex_formatted} !important;\n"
        f"  --primary-color: {hex_formatted} !important;\n"
        f"  --primary-hover: {hover_hex} !important;\n"
        f"  --accent: {hex_formatted} !important;\n"
        f"  --accent-color: {hex_formatted} !important;\n"
        f"  --accent-primary: {hex_formatted} !important;\n"
        f"  --accent-hover: {hover_hex} !important;\n"
        f"  --color-accent: {hex_formatted} !important;\n"
        f"  --theme-color: {hex_formatted} !important;\n"
        f"  --brand: {hex_formatted} !important;\n"
        f"  --brand-color: {hex_formatted} !important;\n"
        f"  --cta-bg: {hex_formatted} !important;\n"
        f"  --accent-gold: {hex_formatted} !important;\n"
        f"  --accent-gold-hover: {hover_hex} !important;\n"
        f"  --blue: {hex_formatted} !important;\n"
        f"  --violet: {hover_hex} !important;\n"
        f"  --cyan: {hex_formatted} !important;\n"
        f"  --green: {hex_formatted} !important;\n"
        f"  --red: {hex_formatted} !important;\n"
        f"  --red-dim: {hover_hex} !important;\n"
        f"  --grad: linear-gradient(135deg, {hex_formatted} 0%, {hover_hex} 100%) !important;\n"
        f"  --grad-r: linear-gradient(135deg, {hover_hex} 0%, {hex_formatted} 100%) !important;\n"
        f"  --glow-blue: rgba({r}, {g}, {b}, 0.25) !important;\n"
        f"  --glow-vio: rgba({r_hover}, {g_hover}, {b_hover}, 0.2) !important;\n"
        f"  --border2: rgba({r}, {g}, {b}, 0.3) !important;\n"
        f"}}\n"
        f".btn-primary, .nav-cta, .hero-cta, .btn, .button, .primary-btn, a.btn-primary, button.btn-primary, [data-theme-color='true'], [class*='btn-primary'], [class*='nav-cta'] {{\n"
        f"  background: linear-gradient(135deg, {hex_formatted} 0%, {hover_hex} 100%) !important;\n"
        f"  background-color: {hex_formatted} !important;\n"
        f"  background-image: linear-gradient(135deg, {hex_formatted} 0%, {hover_hex} 100%) !important;\n"
        f"  border-color: {hex_formatted} !important;\n"
        f"  color: #ffffff !important;\n"
        f"  box-shadow: 0 4px 18px rgba({r}, {g}, {b}, 0.35) !important;\n"
        f"}}\n"
        f".btn-primary:hover, .nav-cta:hover, .hero-cta:hover, .primary-btn:hover {{\n"
        f"  background: linear-gradient(135deg, {hover_hex} 0%, {hex_formatted} 100%) !important;\n"
        f"  background-color: {hover_hex} !important;\n"
        f"  background-image: linear-gradient(135deg, {hover_hex} 0%, {hex_formatted} 100%) !important;\n"
        f"  border-color: {hover_hex} !important;\n"
        f"  color: #ffffff !important;\n"
        f"}}\n"
        f".nav-logo, h1 .accent, .accent, .accent-text, [class*='accent-text'], .gradient-text, .text-gradient, a.brand-logo span, .hero-subtitle span {{\n"
        f"  background: linear-gradient(135deg, {hex_formatted} 0%, {hover_hex} 100%) !important;\n"
        f"  background-clip: text !important;\n"
        f"  -webkit-background-clip: text !important;\n"
        f"  -webkit-text-fill-color: transparent !important;\n"
        f"}}\n"
        f".text-primary, [class*='text-primary'], .nav-links a:hover, .brand-text, .gold-text {{\n"
        f"  color: {hex_formatted} !important;\n"
        f"}}\n"
        f".pulse, .status-dot {{\n"
        f"  background: {hex_formatted} !important;\n"
        f"  box-shadow: 0 0 0 0 rgba({r}, {g}, {b}, 0.5) !important;\n"
        f"}}\n"
        f"#crosshair, .tape-stripe {{ border-color: {hex_formatted} !important; }}\n"
        f"#crosshair::before, #crosshair::after {{ background: {hex_formatted} !important; }}\n"
        f"::selection {{ background: {hex_formatted} !important; color: #ffffff !important; }}\n"
        f"/* [/STUDIO_APPLIED_THEME_COLOR] */\n"
    )

    def update_css_text(css_text: str) -> str:
        # 1. Update standard variables across all variants
        css_text = re.sub(r'(--c-primary\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--c-primary-hover\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--c-accent\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--color-primary\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--color-primary-dark\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--color-primary-hover\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--color-accent\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--color-accent-hover\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--primary\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--primary-hover\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--primary-dark\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--primary-color\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--theme-color\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--accent\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--accent-color\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--accent-primary\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--accent-hover\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--accent-gold\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--accent-gold-hover\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--accent-amber\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--border-subtle\s*:\s*)[^;]+;', rf'\g<1>{border_subtle};', css_text)
        css_text = re.sub(r'(--cta-bg\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--brand\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--brand-color\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--blue\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--violet\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--cyan\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--green\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--red\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', css_text)
        css_text = re.sub(r'(--red-dim\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', css_text)
        css_text = re.sub(r'(--grad\s*:\s*)[^;]+;', rf'\g<1>linear-gradient(135deg, {hex_formatted} 0%, {hover_hex} 100%);', css_text)
        css_text = re.sub(r'(--grad-r\s*:\s*)[^;]+;', rf'\g<1>linear-gradient(135deg, {hover_hex} 0%, {hex_formatted} 100%);', css_text)
        css_text = re.sub(r'(--glow-blue\s*:\s*)[^;]+;', rf'\g<1>rgba({r}, {g}, {b}, 0.25);', css_text)
        css_text = re.sub(r'(--glow-vio\s*:\s*)[^;]+;', rf'\g<1>rgba({r_hover}, {g_hover}, {b_hover}, 0.2);', css_text)
        css_text = re.sub(r'(--border2\s*:\s*)[^;]+;', rf'\g<1>rgba({r}, {g}, {b}, 0.3);', css_text)

        # 2. Universal override block at top of CSS file to guarantee priority
        if "/* [STUDIO_APPLIED_THEME_COLOR] */" in css_text:
            css_text = re.sub(
                r'/\* \[STUDIO_APPLIED_THEME_COLOR\] \*/[\s\S]*?/\* \[/STUDIO_APPLIED_THEME_COLOR\] \*/\n',
                override_rule,
                css_text
            )
            if "/* [STUDIO_APPLIED_THEME_COLOR] */" not in css_text:
                # If regex didn't match end marker, fallback
                css_text = re.sub(
                    r'/\* \[STUDIO_APPLIED_THEME_COLOR\] \*/[\s\S]*?\n\}\n',
                    override_rule,
                    css_text
                )
        else:
            css_text = override_rule + css_text
        return css_text

    def update_html_text(html_text: str) -> str:
        # 1. Update <meta name="theme-color"> if present
        if '<meta name="theme-color"' in html_text or "<meta name='theme-color'" in html_text:
            html_text = re.sub(r"""(<meta\s+name=["']theme-color["']\s+content=["'])[^"']*(["'])""", rf"\g<1>{hex_formatted}\g<2>", html_text, flags=re.I)

        # 2. Strip any previously injected raw CSS comments or style blocks
        html_text = re.sub(r'<style[^>]*id=["\']studio-applied-theme-style["\'][^>]*>[\s\S]*?</style>\s*', '', html_text, flags=re.I)
        html_text = re.sub(r'/\* \[STUDIO_APPLIED_THEME_COLOR\] \*/[\s\S]*?/\* \[/STUDIO_APPLIED_THEME_COLOR\] \*/\s*', '', html_text)

        # 3. Update CSS variables inside existing <style>...</style> blocks
        def _replace_style_content(m):
            tag_open = m.group(1)
            content = m.group(2)
            tag_close = m.group(3)
            content = re.sub(r'(--c-primary\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--c-primary-hover\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', content)
            content = re.sub(r'(--color-primary\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--color-primary-dark\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', content)
            content = re.sub(r'(--color-primary-hover\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', content)
            content = re.sub(r'(--primary\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--primary-color\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--primary-hover\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', content)
            content = re.sub(r'(--accent\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--accent-color\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--blue\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--violet\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', content)
            content = re.sub(r'(--cyan\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--green\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--red\s*:\s*)[^;]+;', rf'\g<1>{hex_formatted};', content)
            content = re.sub(r'(--red-dim\s*:\s*)[^;]+;', rf'\g<1>{hover_hex};', content)
            content = re.sub(r'(--grad\s*:\s*)[^;]+;', rf'\g<1>linear-gradient(135deg, {hex_formatted} 0%, {hover_hex} 100%);', content)
            content = re.sub(r'(--grad-r\s*:\s*)[^;]+;', rf'\g<1>linear-gradient(135deg, {hover_hex} 0%, {hex_formatted} 100%);', content)
            return f"{tag_open}{content}{tag_close}"

        html_text = re.sub(r'(<style\b[^>]*>)([\s\S]*?)(</style>)', _replace_style_content, html_text, flags=re.I)

        # 4. Wrap override rule in a proper HTML <style> tag so the browser executes it as CSS instead of displaying text
        wrapped_style = f'<style id="studio-applied-theme-style">\n{override_rule}\n</style>'
        if "</head>" in html_text:
            html_text = html_text.replace("</head>", f"  {wrapped_style}\n</head>")
        elif "<body" in html_text:
            html_text = re.sub(r'(<body[^>]*>)', rf'{wrapped_style}\n\g<1>', html_text, count=1)
        else:
            html_text = f"{wrapped_style}\n{html_text}"

        return html_text


    files_for_revision = {}
    target_dirs = []
    if local_dir and os.path.isdir(str(local_dir)):
        target_dirs.append(str(local_dir))

    # Also include live_previews temporary directories so in-memory/disk preview reflects changes immediately & on refresh
    temp_preview_base = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews")
    for tid in (str(template_id), str(template.id) if template else None, template.slug if template else None):
        if tid:
            p_dir = os.path.join(temp_preview_base, tid)
            if os.path.isdir(p_dir) and p_dir not in target_dirs:
                target_dirs.append(p_dir)

    for t_dir in target_dirs:
        for root, dirs, files in os.walk(t_dir):
            dirs[:] = [d for d in dirs if d not in ["dist", "build", "node_modules", ".output", ".git", "__MACOSX", ".venv"]]
            for f_name in files:
                f_path = os.path.join(root, f_name)
                rel_path = os.path.relpath(f_path, t_dir).replace("\\", "/")
                if f_name.endswith(".css"):
                    try:
                        with open(f_path, "r", encoding="utf-8", errors="ignore") as _f:
                            original = _f.read()
                        updated = update_css_text(original)
                        if updated != original:
                            with open(f_path, "w", encoding="utf-8") as _f:
                                _f.write(updated)
                            if rel_path not in updated_files:
                                updated_files.append(rel_path)
                            files_for_revision[rel_path] = updated
                    except Exception as err:
                        logger.warning(f"Failed updating CSS file {rel_path}: {err}")
                elif f_name.endswith(".html") or f_name.endswith(".htm"):
                    try:
                        with open(f_path, "r", encoding="utf-8", errors="ignore") as _f:
                            original = _f.read()
                        updated = update_html_text(original)
                        if updated != original:
                            with open(f_path, "w", encoding="utf-8") as _f:
                                _f.write(updated)
                            if rel_path not in updated_files:
                                updated_files.append(rel_path)
                            files_for_revision[rel_path] = updated
                    except Exception as err:
                        logger.warning(f"Failed updating HTML file {rel_path}: {err}")

    if files_for_revision and local_dir:
        try:
            local_project_manager.save_project_revision(
                template_id=template_id,
                files=files_for_revision,
                instruction=f"Applied theme color {hex_formatted}",
                slug=(template.slug if template else str(template_id))
            )
        except Exception as rev_err:
            logger.warning(f"Could not save revision: {rev_err}")

    # Update metadata.json if present
    if local_dir:
        try:
            meta_file = Path(local_dir).parent / "metadata.json"
            if meta_file.exists():
                m_data = json.loads(meta_file.read_text(encoding="utf-8"))
                m_data["primary_color"] = hex_formatted
                m_data["theme_color"] = hex_formatted
                meta_file.write_text(json.dumps(m_data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # Only update stored zip archive in database if template is a private DRAFT owned by the current user
    if template and template.status == TemplateStatus.DRAFT and current_user and template.seller_id == current_user.id:
        download_assets = template.download_assets or {}
        zip_url = download_assets.get("zip")
        if zip_url:
            match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
            if match:
                file_id = uuid.UUID(match.group(1))
                res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
                sf = res.scalar_one_or_none()
                if sf and sf.data:
                    try:
                        with zipfile.ZipFile(io.BytesIO(sf.data), "r") as z_in:
                            new_zip_io = io.BytesIO()
                            with zipfile.ZipFile(new_zip_io, "w", zipfile.ZIP_DEFLATED) as z_out:
                                for item in z_in.infolist():
                                    f_bytes = z_in.read(item.filename)
                                    if item.filename.endswith(".css"):
                                        try:
                                            t_str = f_bytes.decode("utf-8", errors="ignore")
                                            t_upd = update_css_text(t_str)
                                            f_bytes = t_upd.encode("utf-8")
                                        except Exception:
                                            pass
                                    elif item.filename.endswith(".html") or item.filename.endswith(".htm"):
                                        try:
                                            t_str = f_bytes.decode("utf-8", errors="ignore")
                                            t_upd = update_html_text(t_str)
                                            f_bytes = t_upd.encode("utf-8")
                                        except Exception:
                                            pass
                                    z_out.writestr(item, f_bytes)
                        sf.data = new_zip_io.getvalue()
                        sf.file_size = len(sf.data)
                        db.add(sf)
                    except Exception as zip_err:
                        logger.warning(f"Could not update zip storage: {zip_err}")

        template.color_scheme = hex_formatted
        db.add(template)
        await db.commit()

    return {
        "status": "success",
        "primary_color": hex_formatted,
        "hover_color": hover_hex,
        "updated_files": updated_files,
        "template_id": str(template.id) if template else template_id,
        "draft_id": str(template.id) if template else template_id,
        "draft_slug": template.slug if template else None,
        "is_new_clone": is_new_clone,
        "message": f"Theme color {hex_formatted} successfully applied to website code ({len(updated_files)} files updated)."
    }


@router.post("/live/{template_id}/revoke")
async def revoke_live_preview_changes(
    template_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Revokes all unfinalized changes and resets the template back to its pristine original state (before_edit/).
    Clears temp live preview caches, rolls back code, and restores original color scheme.
    """
    import json
    import tempfile
    import shutil
    from pathlib import Path
    from app.core.local_project_manager import local_project_manager
    from app.repositories.template_repo import TemplateRepository

    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(clean_id)
    if not template:
        template = await template_repo.get_by_slug(clean_id)

    # Authorization check: only the owner or an admin can revoke a draft template
    if template and template.status == TemplateStatus.DRAFT:
        is_admin = current_user and getattr(current_user, "role", None) in ("admin", "super_admin")
        if not is_admin and (not current_user or template.seller_id != current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to revoke changes for this draft")

    # If it is a published marketplace template, never purge the canonical project or alter database color_scheme
    is_published = template and template.status == TemplateStatus.PUBLISHED

    if not is_published:
        result = local_project_manager.purge_demo_website_data(clean_id, wipe_reason="user_revoked_changes")

    original_color = "#4F46E5"
    if template:
        temp_preview_base = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews"
        for t_name in (clean_id, str(template.id), template.slug or ""):
            if t_name:
                t_dir = temp_preview_base / t_name
                if t_dir.exists():
                    try:
                        shutil.rmtree(t_dir, ignore_errors=True)
                    except Exception:
                        pass

        if not is_published:
            project_dir = local_project_manager._resolve_project_dir(template.slug or clean_id)
            meta_file = project_dir / "metadata.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8-sig"))
                    if "initial_color_scheme" in meta:
                        original_color = meta["initial_color_scheme"]
                    elif meta.get("color_scheme"):
                        original_color = meta["color_scheme"]
                except Exception:
                    pass

            if original_color and template.color_scheme != original_color:
                template.color_scheme = original_color
                db.add(template)
                await db.commit()

    return {
        "status": "success",
        "message": "All session changes have been revoked and restored to original state.",
        "details": result,
        "original_color": original_color
    }


class FindReplaceRequest(BaseModel):
    find_text: str = Field(min_length=1, max_length=2000)
    replace_text: str = Field(max_length=2000)


@router.post("/live/{template_id}/find-replace")
async def edit_live_preview_find_replace(
    template_id: str,
    request: FindReplaceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    import zipfile
    import io
    import shutil
    import tempfile
    from app.models.template import Template, TemplateStatus
    from app.core.storage import storage
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    # If the template is PUBLISHED or belongs to another user, clone it so the user modifies their own private DRAFT copy
    is_user_owned_draft = (
        template.status == TemplateStatus.DRAFT 
        and current_user 
        and template.seller_id == current_user.id
    )
    if not is_user_owned_draft:
        new_template = Template(
            title=f"Customized {template.title}",
            short_description=template.short_description,
            description=template.description,
            slug=f"{template.slug}-custom-{uuid.uuid4().hex[:6]}",
            price=template.price,
            original_price=template.original_price,
            is_free=template.is_free,
            is_on_sale=template.is_on_sale,
            category_id=template.category_id,
            status=TemplateStatus.DRAFT,
            is_marketplace=False,
            template_origin="custom_draft",
            seller_id=current_user.id if current_user else template.seller_id,
            thumbnail_url=template.thumbnail_url,
            preview_url=template.preview_url,
            tags=template.tags,
            framework=template.framework,
            pages_count=template.pages_count,
            has_dark_mode=template.has_dark_mode,
            is_responsive=template.is_responsive,
            is_rtl_supported=template.is_rtl_supported,
            is_ai_ready=template.is_ai_ready,
            compatibility=template.compatibility,
            version=template.version,
            license_type=template.license_type,
            industry=template.industry,
            color_scheme=template.color_scheme,
            seo_keywords=template.seo_keywords,
            included_pages=template.included_pages,
            download_assets=template.download_assets.copy() if template.download_assets else {}
        )
        db.add(new_template)
        await db.flush()
        template = new_template
        template_id = new_template.id

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
        
    match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
    if not match:
        raise HTTPException(status_code=400, detail="External/Invalid zip storage format")
    file_id = uuid.UUID(match.group(1))
        
    result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
    stored_file = result.scalar_one_or_none()
    if not stored_file:
        raise HTTPException(status_code=404, detail="Source template archive file not found")

    zip_data = stored_file.data if stored_file and stored_file.data else None
    if not zip_data:
        stored_file_data = await storage.get_file(db, file_id)
        if not stored_file_data:
            raise HTTPException(status_code=404, detail="Source template archive data not found")
        zip_data = stored_file_data[0]
    
    # 1. Read files and do find-and-replace
    updated_filenames = set()
    new_zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                is_build = any(d in item.filename.replace("\\", "/").split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
                is_package_or_env = any(x in item.filename.lower() for x in ["package.json", "package-lock.json", ".env", "pnpm-lock", "yarn.lock"])
                is_text = (item.filename.endswith(".html") or 
                           item.filename.endswith(".jsx") or 
                           item.filename.endswith(".js") or 
                           item.filename.endswith(".css") or 
                           item.filename.endswith(".tsx") or 
                           item.filename.endswith(".ts") or
                           item.filename.endswith(".json")) and not is_build and not is_package_or_env
                           
                if is_text:
                    try:
                        text_content = content.decode("utf-8", errors="ignore")
                        if request.find_text in text_content:
                            text_content = text_content.replace(request.find_text, request.replace_text)
                            content = text_content.encode("utf-8")
                            updated_filenames.add(item.filename)
                            print(f"Replaced text in: {item.filename}")
                    except Exception:
                        pass
                z_out.writestr(item, content)
                
    if not updated_filenames:
        return {"status": "success", "template_id": str(template_id), "matches_found": 0}
        
    new_zip_bytes = new_zip_buffer.getvalue()
    
    # 2. Save the updated ZIP back to the database
    new_zip_url = await storage.upload_file(
        db=db,
        file_content=new_zip_bytes,
        folder="templates/customized",
        original_filename=stored_file.original_filename or "template.zip",
        content_type="application/zip",
    )
    template.download_assets = {**download_assets, "zip": new_zip_url}
    db.add(template)
    await db.flush()
    
    # 3. Clear local preview directory cache
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    shutil.rmtree(preview_dir, ignore_errors=True)
    
    # Commit session changes
    await db.commit()
    
    return {"status": "success", "template_id": str(template_id), "matches_found": len(updated_filenames)}


@router.post("/live/{template_id}/edit-ai")
async def edit_live_preview_ai(
    template_id: str,
    request: AIEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import zipfile
    import io
    import shutil
    import tempfile
    from app.core.storage import storage
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    from app.core.request_limits import enforce_user_limit
    await enforce_user_limit(str(current_user.id), "template-ai-edit")
        
    # If the template is PUBLISHED or belongs to another user, clone/fork it so the user modifies their own private DRAFT copy
    is_user_owned_draft = (
        template.status == TemplateStatus.DRAFT 
        and current_user 
        and template.seller_id == current_user.id
    )

    if not is_user_owned_draft:
        existing_draft = None
        if current_user:
            slug_prefix = template.slug.split("-custom-")[0]
            ed_res = await db.execute(
                select(Template).where(
                    Template.seller_id == current_user.id,
                    Template.status == TemplateStatus.DRAFT,
                    Template.slug.like(f"{slug_prefix}-custom-%")
                )
            )
            existing_draft = ed_res.scalars().first()
            
        if existing_draft:
            template = existing_draft
            template_id = str(existing_draft.id)
        else:
            new_template = Template(
                title=f"Customized {template.title}",
                short_description=template.short_description,
                description=template.description,
                slug=f"{template.slug.split('-custom-')[0]}-custom-{uuid.uuid4().hex[:6]}",
                price=template.price,
                original_price=template.original_price,
                is_free=template.is_free,
                is_on_sale=template.is_on_sale,
                category_id=template.category_id,
                status=TemplateStatus.DRAFT,
                is_marketplace=False,
                template_origin="custom_draft",
                seller_id=current_user.id if current_user else template.seller_id,
                thumbnail_url=template.thumbnail_url,
                preview_url=template.preview_url,
                tags=template.tags,
                framework=template.framework,
                pages_count=template.pages_count,
                has_dark_mode=template.has_dark_mode,
                is_responsive=template.is_responsive,
                is_rtl_supported=template.is_rtl_supported,
                is_ai_ready=True,
                compatibility=template.compatibility,
                version=template.version,
                license_type=template.license_type,
                industry=template.industry,
                color_scheme=template.color_scheme,
                seo_keywords=template.seo_keywords,
                included_pages=template.included_pages,
                download_assets=template.download_assets.copy() if template.download_assets else {}
            )
            db.add(new_template)
            await db.flush()
            template = new_template
            template_id = str(new_template.id)

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
        
    match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
    if not match:
        raise HTTPException(status_code=400, detail="External/Invalid zip storage format")
    file_id = uuid.UUID(match.group(1))
        
    result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
    stored_file = result.scalar_one_or_none()
    if not stored_file:
        raise HTTPException(status_code=404, detail="Source template archive file not found")

    zip_data = stored_file.data if stored_file and stored_file.data else None
    if not zip_data:
        stored_file_data = await storage.get_file(db, file_id)
        if not stored_file_data:
            raise HTTPException(status_code=404, detail="Source template archive data not found")
        zip_data = stored_file_data[0]
    
    # 1. Read all editable files in the preview dir or ZIP (HTML, JS, JSX, CSS)
    files_dict = {}
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    # 1. Read all files from preview dir or ZIP
    files_dict = {}
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    if os.path.isdir(preview_dir):
        for root_d, _, f_list in os.walk(preview_dir):
            for fn in f_list:
                rel = os.path.relpath(os.path.join(root_d, fn), preview_dir).replace("\\", "/")
                is_build = any(d in rel.split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
                if (fn.endswith((".html", ".htm", ".jsx", ".js", ".css", ".tsx", ".ts"))) and not is_build:
                    try:
                        with open(os.path.join(root_d, fn), "r", encoding="utf-8", errors="ignore") as f_in:
                            files_dict[rel] = f_in.read()
                    except Exception:
                        pass
    if not files_dict:
        with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
            for name in z_in.namelist():
                is_build = any(d in name.replace("\\", "/").split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
                if (name.endswith((".html", ".htm", ".jsx", ".js", ".css", ".tsx", ".ts"))) and not is_build:
                    try:
                        files_dict[name] = z_in.read(name).decode("utf-8", errors="ignore")
                    except Exception:
                        pass

    if not files_dict:
        raise HTTPException(status_code=400, detail="Could not locate code files in template archive")

    # Filter out minified vendor libraries for AI prompt to prevent token overflow & hallucination
    VENDOR_SKIP = (
        ".min.", "bootstrap", "fontawesome", "font-awesome", "ionicons", "jquery",
        "swiper", "magnific-popup", "pushy", "normalize.css", "animate.css",
        "fonts.googleapis", "fonts.gstatic", ".map", "package-lock.json"
    )
    prompt_files = {}
    for name, content in files_dict.items():
        is_vendor = any(vk in name.lower() for vk in VENDOR_SKIP)
        if not is_vendor:
            prompt_files[name] = content

    # Fallback to all files if filtering removed everything
    if not prompt_files:
        prompt_files = files_dict

    # 2. Use Gemini to do AI editing/refinement across the priority template files
    files_str = ""
    for name, content in prompt_files.items():
        files_str += f"\n--- FILE: {name} ---\n{content}\n"

    ai_prompt = f"""You are a senior lead web developer.
Refine the provided website template files according to this user request: "{request.prompt}".

Even if the user request is simple (e.g. "change color to red", "change title to Jordan Cole", "add a button", "make background dark", "change headline", "add cards", "make text bigger"), interpret their intent intelligently and apply all necessary CSS, HTML, or JavaScript changes to fulfill it completely.

Rules:
1. Return a JSON list of search-and-replace blocks. Do NOT return the entire file content.
2. The "find" string must match the target code inside the files, including leading spaces and indentation where possible.
3. The "replace" string must contain the updated code to replace it.
4. Keep the search blocks as small and precise as possible to avoid mistakes.
5. If changing titles, names, copy or headings, locate the exact text or tags in the HTML file (e.g. index.html) and replace them cleanly.
6. If changing colors or styling, update CSS variables, root variables, or inline/utility classes as needed.

Format the JSON response exactly like this:
[
  {{
    "filename": "index.html",
    "find": "<h1>Old Name</h1>",
    "replace": "<h1>New Name</h1>"
  }}
]

Here are the codebase files:
{files_str}
"""
    def clean_code_response(text: str, language: str) -> str:
        text = text.strip()
        if text.startswith(f"```{language}"):
            text = text.replace(f"```{language}", "", 1)
        elif text.startswith("```"):
            text = text.replace("```", "", 1)
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    try:
        import json
        raw_code = await ai_service._generate_content(ai_prompt, response_mime_type="application/json", feature_name="code_assistant")
        chunks = json.loads(clean_code_response(raw_code, "json"))
        if not isinstance(chunks, list):
            if isinstance(chunks, dict):
                chunks = [{"filename": k, "find": files_dict.get(k, ""), "replace": v} for k, v in chunks.items()]
            else:
                chunks = []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refine template code via AI: {str(e)}")

    # Apply chunks to files_dict with multi-tier matching (exact -> newline-normalized -> stripped -> fuzzy regex)
    updated_filenames = set()
    for chunk in chunks:
        filename = chunk.get("filename")
        find_str = chunk.get("find")
        replace_str = chunk.get("replace")
        if not filename or find_str is None or replace_str is None or not str(find_str).strip():
            continue

        matched_name = None
        for name in files_dict:
            if name == filename or name.endswith("/" + filename) or name.endswith("\\" + filename) or os.path.basename(name) == filename:
                matched_name = name
                break

        if not matched_name and len(files_dict) == 1:
            matched_name = next(iter(files_dict.keys()))

        if matched_name:
            curr_content = files_dict[matched_name]
            # Tier 1: Exact match
            if find_str in curr_content:
                files_dict[matched_name] = curr_content.replace(find_str, replace_str, 1)
                updated_filenames.add(matched_name)
                print(f"[AI Edit] Applied exact replacement for {matched_name}")
            else:
                # Tier 2: Newline-normalized match (\r\n vs \n)
                norm_curr = curr_content.replace("\r\n", "\n")
                norm_find = find_str.replace("\r\n", "\n")
                norm_replace = replace_str.replace("\r\n", "\n")
                if norm_find in norm_curr:
                    has_crlf = "\r\n" in curr_content
                    norm_curr = norm_curr.replace(norm_find, norm_replace, 1)
                    files_dict[matched_name] = norm_curr.replace("\n", "\r\n") if has_crlf else norm_curr
                    updated_filenames.add(matched_name)
                    print(f"[AI Edit] Applied newline-normalized replacement for {matched_name}")
                else:
                    # Tier 3: Stripped whitespace match
                    cleaned_find = find_str.strip()
                    if cleaned_find and cleaned_find in curr_content:
                        files_dict[matched_name] = curr_content.replace(cleaned_find, replace_str.strip(), 1)
                        updated_filenames.add(matched_name)
                        print(f"[AI Edit] Applied stripped replacement for {matched_name}")
                    else:
                        # Tier 4: Fuzzy multi-whitespace regex match
                        try:
                            pattern = re.escape(cleaned_find)
                            pattern = re.sub(r'\\\s+', r'\\s+', pattern)
                            if re.search(pattern, curr_content):
                                files_dict[matched_name] = re.sub(pattern, replace_str.strip(), curr_content, count=1)
                                updated_filenames.add(matched_name)
                                print(f"[AI Edit] Applied regex fuzzy replacement for {matched_name}")
                        except Exception:
                            pass

    # If no files were updated, inform the user honestly
    if not updated_filenames:
        return {
            "status": "warning",
            "template_id": str(template_id),
            "message": f"Could not match target code for: \"{request.prompt[:60]}\". Please specify the exact heading or text to replace."
        }

    # 3. Overwrite files in ZIP with flexible path mapping
    new_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                matching_key = None
                for u in updated_filenames:
                    if (
                        item.filename == u
                        or item.filename.replace("\\", "/") == u
                        or item.filename.endswith("/" + u)
                        or os.path.basename(item.filename) == u
                        or u.endswith("/" + item.filename)
                    ):
                        matching_key = u
                        break

                if matching_key and matching_key in files_dict:
                    content = files_dict[matching_key].encode("utf-8")
                    print(f"[AI Edit] Saved edited file to ZIP: {item.filename}")
                z_out.writestr(item, content)

    new_zip_bytes = new_zip_buffer.getvalue()

    # 4. Save the updated ZIP back to the database as an isolated StoredFile
    new_stored_file = StoredFile(
        storage_key=f"templates/{uuid.uuid4().hex}/customized_ai.zip",
        original_filename=f"customized_{stored_file.original_filename or 'template.zip'}",
        content_type=stored_file.content_type or "application/zip",
        size=len(new_zip_bytes),
        data=new_zip_bytes
    )
    db.add(new_stored_file)
    await db.flush()
    template.download_assets = {
        "zip": f"/api/v1/files/{new_stored_file.id}"
    }
    db.add(template)
    await db.flush()

    # 5. Extract updated files into this user draft's isolated live preview directory
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    shutil.rmtree(preview_dir, ignore_errors=True)
    os.makedirs(preview_dir, exist_ok=True)
    from app.services.security_scanner import security_scanner
    security_scanner.sanitize_extract_zip(new_zip_bytes, Path(preview_dir))

    # Also directly write updated files to preview_dir as a guarantee
    for u_name in updated_filenames:
        target_disk_path = os.path.join(preview_dir, u_name)
        try:
            os.makedirs(os.path.dirname(target_disk_path), exist_ok=True)
            with open(target_disk_path, "w", encoding="utf-8") as f_out:
                f_out.write(files_dict[u_name])
            print(f"[AI Edit] Directly wrote updated file to disk: {target_disk_path}")
        except Exception as e:
            print(f"[AI Edit] Notice writing to disk: {e}")

    # Commit session changes
    await db.commit()

    return {
        "status": "success",
        "template_id": str(template_id),
        "message": f"Applied changes to {len(updated_filenames)} file(s): \"{request.prompt[:60]}\""
    }


class DemoSessionStartRequest(BaseModel):
    template_id: str


@router.post("/demo/session/start")
async def start_demo_session(
    payload: DemoSessionStartRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    session_token = uuid.uuid4().hex
    return {
        "status": "success",
        "session_token": session_token,
        "remaining_seconds": 1800,
        "template_id": payload.template_id
    }


@router.get("/demo/session/status")
async def get_demo_session_status(
    session_token: str,
    db: AsyncSession = Depends(get_db)
):
    return {
        "status": "success",
        "expired": False,
        "remaining_seconds": 1800
    }


@router.api_route("/demo/session/end", methods=["GET", "POST"])
async def end_demo_session(
    session_token: Optional[str] = None,
    template_id: Optional[str] = None,
    reason: Optional[str] = "manual"
):
    return {"status": "success", "message": "Demo session ended"}


@router.api_route("/live/{template_id}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"], response_class=Response)
@router.api_route("/live/{template_id}/{filepath:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"], response_class=Response)
async def serve_live_preview(
    template_id: str,
    request: Request,
    filepath: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    # Redirect to URL with trailing slash to ensure relative assets load correctly in browser
    if not filepath and not request.url.path.endswith("/"):
        from fastapi.responses import RedirectResponse
        forwarded_proto = request.headers.get("x-forwarded-proto") or ("https" if (settings.ENVIRONMENT == "production" or "onrender.com" in str(request.url)) else request.url.scheme)
        url_obj = request.url.replace(scheme=forwarded_proto)
        redirect_url = str(url_obj) + "/"
        return RedirectResponse(url=redirect_url)
    """
    Dynamically extract, compile (if needed), and serve the template's actual frontend code in the browser as a running live demo.
    """
    import os
    import zipfile
    import io
    import mimetypes
    import asyncio
    import tempfile
    from fastapi.responses import Response
    from sqlalchemy import select
    from app.repositories.template_repo import TemplateRepository
    from app.services.security_scanner import security_scanner
    from app.models.template import TemplateStatus
    
    # Fast in-memory template metadata lookup (avoids multi-second Neon Oregon cloud round trips)
    template = await _get_cached_preview_template(template_id, db)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Live previews serve static assets only. A template API path must never
    # dispatch uploaded Python code into the Studio API process.
    if filepath and (filepath == "api" or filepath.startswith("api/")):
        raise HTTPException(status_code=404, detail="Template previews only serve static website files")
        
    target_slug = template.slug if (template and template.slug) else str(template_id)
    purchase_url = f"{settings.FRONTEND_URL}/marketplace/{target_slug}?buy=1"

    watermark_payload = """
<!-- Injected Watermark Grid Overlay -->
<div class="preview-watermark-grid"></div>

<style>
  /* Disable text selection across all elements */
  * {
    user-select: none !important;
    -webkit-user-select: none !important;
    -moz-user-select: none !important;
    -ms-user-select: none !important;
  }

  /* Sleek modern scrollbars across all live previews (prevents ugly OS scrollbars) */
  ::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  ::-webkit-scrollbar-track {
    background: transparent;
  }
  ::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.4);
    border-radius: 9999px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: rgba(148, 163, 184, 0.7);
  }
  @media (max-width: 768px) {
    /* Hide scrollbars completely on mobile for app-like native feel */
    html, body {
      scrollbar-width: none !important;
      -ms-overflow-style: none !important;
    }
    html::-webkit-scrollbar, body::-webkit-scrollbar {
      display: none !important;
      width: 0 !important;
      height: 0 !important;
    }
  }

  /* Watermark grid covering full page with pointer-events disabled */
  .preview-watermark-grid {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    pointer-events: none !important;
    z-index: 999999 !important;
    opacity: 0.65 !important;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'><text x='20' y='150' fill='rgba(128, 128, 128, 0.16)' font-size='13' font-weight='800' font-family='sans-serif' transform='rotate(-30 20 150)'>SITE STUDIO PREVIEW</text></svg>") !important;
    background-repeat: repeat !important;
  }

  /* Bottom floating warning banner */
  .preview-purchase-footer-banner {
    position: fixed !important;
    bottom: 1.5rem !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    background: rgba(15, 23, 42, 0.96) !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    color: #ffffff !important;
    padding: 0.625rem 1.25rem !important;
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    border-radius: 9999px !important;
    display: flex !important;
    align-items: center !important;
    gap: 1rem !important;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4) !important;
    z-index: 999998 !important;
    white-space: nowrap !important;
    font-family: system-ui, -apple-system, sans-serif !important;
  }

  .preview-purchase-footer-banner a {
    color: #38bdf8 !important;
    text-decoration: none !important;
    font-weight: 800 !important;
    border-left: 1px solid rgba(255, 255, 255, 0.2) !important;
    padding-left: 1rem !important;
    transition: color 0.2s ease !important;
  }

  .preview-purchase-footer-banner a:hover {
    color: #0ea5e9 !important;
  }

  /* Robust navigation bar and button layout protection */
  .navbar, nav, header nav, .nav-container {
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 0.5rem !important;
  }

  .navbar .btn, nav a.btn, nav button, nav .nav-btn, .nav-cta, a.btn, button.btn {
    white-space: nowrap !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: max-content !important;
    line-height: 1.25 !important;
  }

  /* Block PDF printing */
  @media print {
    body {
      display: none !important;
    }
  }
</style>

<script>
  (function() {
    // 1. Disable Right-Click Context Menu
    document.addEventListener('contextmenu', function(e) {
      e.preventDefault();
    }, true);

    // 2. Intercept Inspector, View-Source, Copy and Save keys
    document.addEventListener('keydown', function(e) {
      if (
        e.key === 'F12' ||
        (e.ctrlKey && e.shiftKey && e.key === 'I') ||
        (e.ctrlKey && e.shiftKey && e.key === 'C') ||
        (e.ctrlKey && e.shiftKey && e.key === 'J') ||
        (e.ctrlKey && e.key === 'u') ||
        (e.ctrlKey && e.key === 'c') ||
        (e.ctrlKey && e.key === 's')
      ) {
        e.preventDefault();
        e.stopPropagation();
        return false;
      }
    }, true);
  })();
</script>
""".replace("__PURCHASE_URL__", purchase_url)
    async def serve_fallback(err_msg: str = "Preview compilation"):
        if filepath and not (filepath.endswith(".html") or filepath.endswith(".htm")):
            if filepath.endswith(".css"):
                return Response(content=b"", media_type="text/css")
            if filepath.endswith(".js"):
                return Response(content=b"", media_type="application/javascript")
            return Response(content=b"", media_type="application/octet-stream")

        # 1. Multi-Framework Source Detection (Vue, React, Svelte, Static HTML)
        app_vue_content = None
        app_jsx_content = None
        app_svelte_content = None
        index_html_content = None
        index_css_content = ""
        package_json_content = None
        preview_dir_loc = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))

        # Scan preview_dir (extracted filesystem) for framework entry files
        if os.path.isdir(preview_dir_loc):
            for root, _, files in os.walk(preview_dir_loc):
                if any(d in root.replace("\\", "/").split("/") for d in ["dist", "build", ".output", "node_modules"]):
                    continue
                for f in files:
                    f_lower = f.lower()
                    f_full = os.path.join(root, f)
                    if f_lower in ("app.vue", "main.vue") or (f_lower.endswith(".vue") and not app_vue_content):
                        try:
                            with open(f_full, "r", encoding="utf-8", errors="ignore") as _vf:
                                app_vue_content = _vf.read()
                        except Exception:
                            pass
                    elif f_lower in ("app.jsx", "app.tsx", "main.jsx", "main.tsx", "index.jsx") or (f_lower.endswith((".jsx", ".tsx")) and not app_jsx_content):
                        try:
                            with open(f_full, "r", encoding="utf-8", errors="ignore") as _jf:
                                raw_app = _jf.read()
                                from app.services.ai_service import clean_code_response, repair_truncated_jsx
                                app_jsx_content = repair_truncated_jsx(clean_code_response(raw_app, "jsx"))
                        except Exception:
                            pass
                    elif f_lower in ("app.svelte", "main.svelte") or (f_lower.endswith(".svelte") and not app_svelte_content):
                        try:
                            with open(f_full, "r", encoding="utf-8", errors="ignore") as _sf:
                                app_svelte_content = _sf.read()
                        except Exception:
                            pass
                    elif f_lower in ("index.html", "index.htm", "home.html", "main.html") and not index_html_content:
                        try:
                            with open(f_full, "r", encoding="utf-8", errors="ignore") as _hf:
                                index_html_content = _hf.read()
                        except Exception:
                            pass
                    elif f_lower.endswith(".css"):
                        try:
                            with open(f_full, "r", encoding="utf-8", errors="ignore") as _cf:
                                index_css_content += "\n" + _cf.read()
                        except Exception:
                            pass
                    elif f_lower == "package.json" and not package_json_content:
                        try:
                            with open(f_full, "r", encoding="utf-8", errors="ignore") as _pf:
                                package_json_content = _pf.read()
                        except Exception:
                            pass

        # If preview_dir is empty or missing sources, read directly from the DB-stored ZIP
        if not (app_vue_content or app_jsx_content or app_svelte_content or index_html_content):
            try:
                d_assets = template.download_assets or {}
                z_url = d_assets.get("zip")
                if z_url:
                    uuid_m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(z_url))
                    if uuid_m:
                        from app.models import StoredFile
                        sf_res = await db.execute(select(StoredFile).where(StoredFile.id == uuid.UUID(uuid_m.group(1))))
                        stored_f = sf_res.scalar_one_or_none()
                        if stored_f and stored_f.data and zipfile.is_zipfile(io.BytesIO(stored_f.data)):
                            with zipfile.ZipFile(io.BytesIO(stored_f.data), "r") as zf:
                                names = zf.namelist()
                                # Vue candidates
                                vue_cands = sorted(
                                    [n for n in names if n.lower().endswith(".vue") and "node_modules" not in n],
                                    key=lambda x: (not x.lower().endswith("app.vue"), len(x))
                                )
                                if vue_cands:
                                    app_vue_content = zf.read(vue_cands[0]).decode("utf-8", errors="ignore")
                                # JSX / TSX candidates
                                jsx_cands = sorted(
                                    [n for n in names if (n.lower().endswith(".jsx") or n.lower().endswith(".tsx")) and "node_modules" not in n],
                                    key=lambda x: (not x.lower().endswith("app.jsx"), len(x))
                                )
                                if jsx_cands:
                                    raw_app = zf.read(jsx_cands[0]).decode("utf-8", errors="ignore")
                                    from app.services.ai_service import clean_code_response, repair_truncated_jsx
                                    app_jsx_content = repair_truncated_jsx(clean_code_response(raw_app, "jsx"))
                                # Svelte candidates
                                svelte_cands = sorted(
                                    [n for n in names if n.lower().endswith(".svelte") and "node_modules" not in n],
                                    key=len
                                )
                                if svelte_cands:
                                    app_svelte_content = zf.read(svelte_cands[0]).decode("utf-8", errors="ignore")
                                # HTML candidates
                                html_cands = sorted(
                                    [n for n in names if (n.lower().endswith("index.html") or n.lower().endswith(".html")) and "node_modules" not in n and "__MACOSX" not in n],
                                    key=lambda x: (not x.lower().endswith("index.html"), len(x))
                                )
                                if html_cands:
                                    index_html_content = zf.read(html_cands[0]).decode("utf-8", errors="ignore")
                                # CSS candidates
                                css_cands = [n for n in names if n.lower().endswith(".css") and "node_modules" not in n]
                                for c_name in css_cands[:3]:
                                    index_css_content += "\n" + zf.read(c_name).decode("utf-8", errors="ignore")
                                # package.json
                                pkg_cands = [n for n in names if n.lower().endswith("package.json") and "node_modules" not in n]
                                if pkg_cands:
                                    package_json_content = zf.read(pkg_cands[0]).decode("utf-8", errors="ignore")
            except Exception as e_zip_read:
                logger.warning(f"serve_fallback: Could not read sources from DB ZIP: {e_zip_read}")

        # Determine target framework
        requested_fw = (request.query_params.get("framework") or "").strip().lower()
        model_fw = (template.framework.value if template.framework else "").lower()

        pkg_deps = {}
        if package_json_content:
            try:
                pkg_data = json.loads(package_json_content)
                pkg_deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
            except Exception:
                pass

        detected_fw = "react"
        if requested_fw in ("vue", "react", "nextjs", "svelte", "angular", "html", "vanilla"):
            detected_fw = requested_fw
        elif app_vue_content or "vue" in pkg_deps or "nuxt" in pkg_deps or model_fw in ("vue", "nuxt"):
            detected_fw = "vue"
        elif app_jsx_content or "react" in pkg_deps or "next" in pkg_deps or model_fw in ("react", "nextjs"):
            detected_fw = "react"
        elif app_svelte_content or "svelte" in pkg_deps or model_fw == "svelte":
            detected_fw = "svelte"
        elif "@angular/core" in pkg_deps or model_fw == "angular":
            detected_fw = "angular"
        elif index_html_content or model_fw in ("html", "vanilla", "static"):
            detected_fw = "html"

        _title = template.title or "Live Preview"
        _css = index_css_content

        # ─── RUNNER 1: Vue 3 In-Browser Standalone Runner ──────────────────────────
        if app_vue_content or (detected_fw == "vue" and app_vue_content):
            try:
                # 1. Extract <template>, <script>, and <style>
                t_match = re.search(r"<template[^>]*>([\s\S]*?)</template>", app_vue_content, re.IGNORECASE)
                vue_template_html = t_match.group(1).strip() if t_match else "<div class='p-8'><h1>{{ title || 'Vue Preview' }}</h1></div>"

                s_match = re.search(r"<script[^>]*>([\s\S]*?)</script>", app_vue_content, re.IGNORECASE)
                raw_vue_script = s_match.group(1).strip() if s_match else ""
                
                # Clean script: remove imports
                cleaned_vue_script = raw_vue_script
                cleaned_vue_script = re.sub(r"import\s+[\s\S]*?from\s+['\"].*?['\"]; *\n?", "", cleaned_vue_script)
                cleaned_vue_script = re.sub(r"import\s+['\"].*?['\"]; *\n?", "", cleaned_vue_script)

                style_matches = re.findall(r"<style[^>]*>([\s\S]*?)</style>", app_vue_content, re.IGNORECASE)
                vue_styles = "\n".join(style_matches)

                # Escape backticks and dollar signs for embedding in template string
                escaped_script = cleaned_vue_script.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

                vue_runner_html = (
                    "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
                    "  <meta charset=\"UTF-8\">\n"
                    "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
                    f"  <title>{_title} - Live Preview (Vue)</title>\n"
                    "  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">\n"
                    "  <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap\" rel=\"stylesheet\">\n"
                    "  <script src=\"https://cdn.tailwindcss.com\"></script>\n"
                    "  <script src=\"https://unpkg.com/vue@3/dist/vue.global.js\"></script>\n"
                    "  <style>\n"
                    "    *, *::before, *::after { box-sizing: border-box; }\n"
                    "    body { margin: 0; font-family: 'Inter', system-ui, sans-serif; }\n"
                    f"    {_css}\n"
                    f"    {vue_styles}\n"
                    "  </style>\n"
                    "</head>\n<body>\n"
                    "  <div id=\"app\"></div>\n"
                    "  <script id=\"vue-template-src\" type=\"text/x-template\">\n"
                    f"    {vue_template_html}\n"
                    "  </script>\n"
                    "  <script>\n"
                    "    const { createApp, ref, reactive, computed, onMounted, watch } = Vue;\n"
                    "    const commonIconNames = [\n"
                    "      'Sparkles','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','CheckCircle','CheckCircle2',\n"
                    "      'Check','XCircle','X','Cpu','Globe','Layers','FileText','File','Folder','Plus','Minus',\n"
                    "      'Trash','Trash2','Edit','Edit2','Edit3','Info','AlertCircle','AlertTriangle','Bell',\n"
                    "      'Building','Building2','Home','Map','MapPin','Palette','Paintbrush','Wand','Wand2',\n"
                    "      'Phone','Mail','MessageCircle','MessageSquare','Send','Share','Share2','Link',\n"
                    "      'ExternalLink','Copy','Download','Upload','Eye','EyeOff','Lock','Unlock','Key',\n"
                    "      'Shield','ShieldCheck','User','Users','UserPlus','Zap','Flame','Rocket','Star',\n"
                    "      'Heart','ThumbsUp','ThumbsDown','ShoppingBag','ShoppingCart','Package','Tag',\n"
                    "      'Gift','Store','Coffee','Leaf','Apple','Sun','Moon','Cloud','Menu','MoreHorizontal',\n"
                    "      'MoreVertical','ChevronUp','ChevronDown','ChevronLeft','ChevronRight','Sliders',\n"
                    "      'Settings','Settings2','Bot','Code','Code2','Terminal','Server','Database','Wifi',\n"
                    "      'Play','Pause','Circle','TrendingUp','TrendingDown','BarChart','BarChart2',\n"
                    "      'DollarSign','CreditCard','Banknote','Wallet','Award','Trophy','Crown','Flag',\n"
                    "      'Calendar','Clock','Timer','Search','Filter','RefreshCw','RotateCw','Camera',\n"
                    "      'Image','Video','Music','Mic','Volume2','Lightbulb','Brain','Network','Monitor',\n"
                    "      'Laptop','Tablet','Smartphone'\n"
                    "    ];\n"
                    "    const vueMockIcons = {};\n"
                    "    commonIconNames.forEach(function(name) {\n"
                    "      vueMockIcons[name] = {\n"
                    "        name: name,\n"
                    "        props: ['class', 'size', 'color', 'strokeWidth'],\n"
                    "        template: '<svg xmlns=\"http://www.w3.org/2000/svg\" :class=\"class || \\'w-4 h-4 inline-block\\'\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"12\" cy=\"12\" r=\"10\"/></svg>'\n"
                    "      };\n"
                    "    });\n"
                    "    let compDefinition = {};\n"
                    "    try {\n"
                    f"      const scriptBody = `{escaped_script}`;\n"
                    "      if (scriptBody.indexOf('export default') !== -1) {\n"
                    "        const expMatch = scriptBody.match(/export\\s+default\\s+([\\s\\S]+)$/);\n"
                    "        if (expMatch) {\n"
                    "          const objText = expMatch[1].trim().replace(/;$/, '');\n"
                    "          compDefinition = new Function('Vue', 'ref', 'reactive', 'computed', 'onMounted', 'watch', 'return (' + objText + ')')(Vue, ref, reactive, computed, onMounted, watch);\n"
                    "        }\n"
                    "      } else if (scriptBody.trim()) {\n"
                    "        compDefinition = {\n"
                    "          setup: function() {\n"
                    "            try {\n"
                    "              return new Function('Vue', 'ref', 'reactive', 'computed', 'onMounted', 'watch', scriptBody + '\\nreturn {};')(Vue, ref, reactive, computed, onMounted, watch);\n"
                    "            } catch(e) {\n"
                    "              console.warn('Vue setup execute:', e);\n"
                    "              return {};\n"
                    "            }\n"
                    "          }\n"
                    "        };\n"
                    "      }\n"
                    "    } catch (e) {\n"
                    "      console.warn('Vue component compile notice:', e);\n"
                    "    }\n"
                    "    compDefinition.template = document.getElementById('vue-template-src').innerHTML;\n"
                    "    try {\n"
                    "      const app = createApp(compDefinition);\n"
                    "      Object.keys(vueMockIcons).forEach(function(k) { app.component(k, vueMockIcons[k]); });\n"
                    "      app.mount('#app');\n"
                    "    } catch (e) {\n"
                    "      console.error('Vue mount error:', e);\n"
                    "      const appEl = document.getElementById('app');\n"
                    "      if (appEl) appEl.innerHTML = '<div style=\"padding:2rem;font-family:sans-serif;color:#e11d48;\"><h3>Vue Preview Ready</h3><p>' + (e && e.message || 'Rendered') + '</p></div>';\n"
                    "    }\n"
                    "  </script>\n"
                    f"  {watermark_payload}\n"
                    "</body>\n</html>"
                )
                return Response(content=vue_runner_html.encode("utf-8"), media_type="text/html", headers=security_scanner.get_secure_preview_headers())
            except Exception as e_vue:
                logger.warning(f"In-browser Vue runner fallback notice: {e_vue}")

        # ─── RUNNER 2: React 18 In-Browser Standalone Runner ───────────────────────
        if app_jsx_content:
            try:
                # Safely transform ES module image/asset imports into valid JS variables
                # e.g. import heroImg from "./assets/hero.png" -> const heroImg = "./assets/hero.png";
                def transform_asset_import(match):
                    var_name = match.group(1).strip()
                    asset_path = match.group(2).strip()
                    return f"const {var_name} = '{asset_path}';"

                cleaned_jsx = app_jsx_content
                cleaned_jsx = re.sub(
                    r"import\s+([A-Za-z0-9_]+)\s+from\s+['\"]([^'\"]+\.(?:png|jpg|jpeg|svg|webp|gif|ico|avif|bmp))['\"];?",
                    transform_asset_import,
                    cleaned_jsx
                )
                cleaned_jsx = re.sub(r"import\s+[\s\S]*?from\s+['\"].*?['\"]; *\n?", "", cleaned_jsx)
                cleaned_jsx = re.sub(r"import\s+['\"].*?['\"]; *\n?", "", cleaned_jsx)
                cleaned_jsx = re.sub(r"^\s*export\s+default\s+[A-Za-z0-9_]+\s*;\s*$", "", cleaned_jsx, flags=re.MULTILINE)
                cleaned_jsx = re.sub(r"\bexport\s+default\s+(?=function|class|const|let|var|\()", "", cleaned_jsx)
                cleaned_jsx = re.sub(r"\bexport\s+(?=function|class|const|let|var)", "", cleaned_jsx)

                comp_name = "App"
                if "function App" not in cleaned_jsx and "const App" not in cleaned_jsx:
                    func_m = re.search(r"(?:export\s+default\s+)?function\s+([A-Z][A-Za-z0-9_]+)", cleaned_jsx)
                    const_m = re.search(r"const\s+([A-Z][A-Za-z0-9_]+)\s*=\s*(?:\([^)]*\)|[A-Za-z_]+)\s*=>", cleaned_jsx)
                    if func_m:
                        comp_name = func_m.group(1)
                    elif const_m:
                        comp_name = const_m.group(1)

                react_runner_html = (
                    "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
                    "  <meta charset=\"UTF-8\">\n"
                    "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
                    f"  <title>{_title} - Live Preview</title>\n"
                    "  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">\n"
                    "  <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap\" rel=\"stylesheet\">\n"
                    "  <script src=\"https://cdn.tailwindcss.com\"></script>\n"
                    "  <script src=\"https://unpkg.com/react@18/umd/react.production.min.js\"></script>\n"
                    "  <script src=\"https://unpkg.com/react-dom@18/umd/react-dom.production.min.js\"></script>\n"
                    "  <script src=\"https://unpkg.com/@babel/standalone@7.24.0/babel.min.js\"></script>\n"
                    "  <script src=\"https://unpkg.com/lucide-react@0.451.0/dist/umd/lucide-react.js\"></script>\n"
                    "  <style>\n"
                    "    *, *::before, *::after { box-sizing: border-box; }\n"
                    "    body { margin: 0; font-family: \'Inter\', system-ui, sans-serif; }\n"
                    f"    {_css}\n"
                    "  </style>\n"
                    "</head>\n<body>\n"
                    "  <div id=\"root\"></div>\n"
                    "  <script type=\"text/babel\" data-presets=\"react\">\n"
                    "    const _lucide = window.lucide || {};\n"
                    "    const {\n"
                    "      Sparkles=()=>null,ArrowLeft=()=>null,ArrowRight=()=>null,ArrowUp=()=>null,ArrowDown=()=>null,\n"
                    "      Loader=()=>null,Loader2=()=>null,CheckCircle=()=>null,CheckCircle2=()=>null,Check=()=>null,\n"
                    "      XCircle=()=>null,X=()=>null,Cpu=()=>null,Globe=()=>null,Layers=()=>null,\n"
                    "      FileText=()=>null,File=()=>null,Folder=()=>null,Plus=()=>null,Minus=()=>null,\n"
                    "      Trash=()=>null,Trash2=()=>null,Edit=()=>null,Edit2=()=>null,Edit3=()=>null,\n"
                    "      Info=()=>null,AlertCircle=()=>null,AlertTriangle=()=>null,Bell=()=>null,\n"
                    "      Building=()=>null,Building2=()=>null,Home=()=>null,Map=()=>null,MapPin=()=>null,\n"
                    "      Palette=()=>null,Paintbrush=()=>null,Wand=()=>null,Wand2=()=>null,\n"
                    "      Phone=()=>null,Mail=()=>null,MessageCircle=()=>null,MessageSquare=()=>null,Send=()=>null,\n"
                    "      Share=()=>null,Share2=()=>null,Link=()=>null,ExternalLink=()=>null,Copy=()=>null,\n"
                    "      Download=()=>null,Upload=()=>null,Eye=()=>null,EyeOff=()=>null,\n"
                    "      Lock=()=>null,Unlock=()=>null,Key=()=>null,Shield=()=>null,ShieldCheck=()=>null,\n"
                    "      User=()=>null,Users=()=>null,UserPlus=()=>null,\n"
                    "      Zap=()=>null,Flame=()=>null,Rocket=()=>null,Star=()=>null,\n"
                    "      Heart=()=>null,ThumbsUp=()=>null,ThumbsDown=()=>null,\n"
                    "      ShoppingBag=()=>null,ShoppingCart=()=>null,Package=()=>null,Tag=()=>null,Gift=()=>null,Store=()=>null,\n"
                    "      Coffee=()=>null,Leaf=()=>null,Apple=()=>null,Sun=()=>null,Moon=()=>null,Cloud=()=>null,\n"
                    "      Menu=()=>null,MoreHorizontal=()=>null,MoreVertical=()=>null,\n"
                    "      ChevronUp=()=>null,ChevronDown=()=>null,ChevronLeft=()=>null,ChevronRight=()=>null,\n"
                    "      Sliders=()=>null,Settings=()=>null,Settings2=()=>null,\n"
                    "      Bot=()=>null,Code=()=>null,Code2=()=>null,Terminal=()=>null,\n"
                    "      Server=()=>null,Database=()=>null,Wifi=()=>null,\n"
                    "      Play=()=>null,Pause=()=>null,Circle=()=>null,\n"
                    "      TrendingUp=()=>null,TrendingDown=()=>null,BarChart=()=>null,BarChart2=()=>null,\n"
                    "      DollarSign=()=>null,CreditCard=()=>null,Banknote=()=>null,Wallet=()=>null,\n"
                    "      Award=()=>null,Trophy=()=>null,Crown=()=>null,Flag=()=>null,\n"
                    "      Calendar=()=>null,Clock=()=>null,Timer=()=>null,\n"
                    "      Search=()=>null,Filter=()=>null,\n"
                    "      RefreshCw=()=>null,RotateCw=()=>null,\n"
                    "      Camera=()=>null,Image=()=>null,Video=()=>null,Music=()=>null,Mic=()=>null,Volume2=()=>null,\n"
                    "      Lightbulb=()=>null,Brain=()=>null,Network=()=>null,\n"
                    "      Monitor=()=>null,Laptop=()=>null,Tablet=()=>null,Smartphone=()=>null,\n"
                    "    } = _lucide;\n"
                    "    const useState=React.useState;\n"
                    "    const useEffect=React.useEffect;\n"
                    "    const useRef=React.useRef;\n"
                    "    const useMemo=React.useMemo;\n"
                    "    const useCallback=React.useCallback;\n"
                    "    const useContext=React.useContext;\n"
                    "    const createContext=React.createContext;\n"
                    "    const useReducer=React.useReducer;\n"
                    f"    {cleaned_jsx}\n"
                    "    try {\n"
                    f"      const container = document.getElementById('root');\n"
                    f"      const reactRoot = ReactDOM.createRoot(container);\n"
                    f"      reactRoot.render(React.createElement({comp_name}));\n"
                    "    } catch (e) {\n"
                    "      console.error('React mount error:', e);\n"
                    "      const root = document.getElementById('root'); root.replaceChildren(); const msg = document.createElement('p'); msg.textContent = String(e && e.message || 'Unknown preview error'); root.appendChild(msg);\n"
                    "    }\n"
                    "  </script>\n"
                    f"  {watermark_payload}\n"
                    "</body>\n</html>"
                )
                return Response(content=react_runner_html.encode("utf-8"), media_type="text/html", headers=security_scanner.get_secure_preview_headers())
            except Exception as e_runner:
                logger.warning(f"In-browser React runner fallback failed: {e_runner}")

        # ─── RUNNER 3: Static HTML Runner ──────────────────────────────────────────
        if index_html_content:
            try:
                html_out = index_html_content
                if "<head>" in html_out and "cdn.tailwindcss.com" not in html_out:
                    html_out = html_out.replace("<head>", f"<head>\n  <base href=\"/api/v1/preview/live/{template_id}/\" />\n  <script src=\"https://cdn.tailwindcss.com\"></script>\n", 1)
                elif "<base" not in html_out and "<head>" in html_out:
                    html_out = html_out.replace("<head>", f"<head>\n  <base href=\"/api/v1/preview/live/{template_id}/\" />\n", 1)

                if "</body>" in html_out:
                    html_out = html_out.replace("</body>", f"{watermark_payload}\n</body>", 1)
                else:
                    html_out = html_out + "\n" + watermark_payload
                return Response(content=html_out.encode("utf-8"), media_type="text/html", headers=security_scanner.get_secure_preview_headers())
            except Exception as e_html:
                logger.warning(f"Static HTML runner fallback failed: {e_html}")

        # 2. Visual rich landing page fallback

        custom_color = request.query_params.get("primaryColor") or "#6366f1"
        try:
            hex_color = custom_color.lstrip("#")
            if len(hex_color) == 3:
                hex_color = "".join(c*2 for c in hex_color)
            primary_rgb = f"{int(hex_color[0:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:6], 16)}"
        except Exception:
            primary_rgb = "99, 102, 241"
        b_name = request.query_params.get("businessName") or template.title
        c_title = request.query_params.get("title") or template.title
        c_sub = request.query_params.get("subtitle") or template.short_description
        c_cta = request.query_params.get("ctaText") or "Get Started"
        hero_bg_url = "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&q=85"
        gallery_1 = hero_bg_url
        gallery_2 = hero_bg_url
        gallery_3 = hero_bg_url
        
        is_light_fallback = (
            request.query_params.get("theme", "").lower() == "light" 
            or request.query_params.get("theme_mode", "").lower() == "light"
            or "light" in request.query_params.get("prompt", "").lower()
        )
        bg_val = "#f8fafc" if is_light_fallback else "#0f172a"
        card_val = "rgba(255, 255, 255, 0.9)" if is_light_fallback else "rgba(30, 41, 59, 0.7)"
        border_val = "rgba(0, 0, 0, 0.1)" if is_light_fallback else "rgba(255, 255, 255, 0.1)"
        text_val = "#0f172a" if is_light_fallback else "#f8fafc"
        text_muted_val = "#475569" if is_light_fallback else "#94a3b8"

        fallback_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{b_name} - Live Preview</title>
  <style>
    :root {{
      --primary: {custom_color};
      --primary-rgb: {primary_rgb};
      --bg: {bg_val};
      --card: {card_val};
      --border: {border_val};
      --text: {text_val};
      --text-muted: {text_muted_val};
    }}
    
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, sans-serif;
    }}
    
    body {{
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }}
    
    .bg-grid {{
      position: fixed;
      inset: 0;
      z-index: -1;
      background-image: radial-gradient(circle at 50% 50%, rgba(var(--primary-rgb), 0.15) 0%, transparent 60%),
                        linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
      background-size: 100% 100%, 24px 24px, 24px 24px;
      pointer-events: none;
    }}
    
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1.5rem 2rem;
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(12px);
      background: rgba(15, 23, 42, 0.75);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    
    .logo {{
      font-size: 1.25rem;
      font-weight: 800;
      background: linear-gradient(135deg, #ffffff 0%, var(--primary) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    
    nav {{
      display: flex;
      gap: 1.5rem;
    }}
    
    nav a {{
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.875rem;
      font-weight: 600;
      transition: color 0.2s;
    }}
    
    nav a:hover, nav a.active {{
      color: var(--text);
    }}
    
    .nav-btn {{
      background: var(--primary);
      color: #fff;
      padding: 0.5rem 1rem;
      border-radius: 9999px;
      text-decoration: none;
      font-size: 0.875rem;
      font-weight: 600;
      box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.4);
    }}
    
    .nav-btn:hover {{
      opacity: 0.9;
    }}
    
    .hero-container {{
      position: relative;
      padding: 5rem 2rem;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 3rem;
      align-items: center;
      max-width: 1200px;
      margin: 0 auto;
    }}

    .hero-image-wrapper {{
      position: relative;
      border-radius: 1.5rem;
      overflow: hidden;
      border: 1px solid var(--border);
      box-shadow: 0 20px 40px -15px rgba(0,0,0,0.5);
    }}

    .hero-image-wrapper img {{
      width: 100%;
      height: 380px;
      object-fit: cover;
      display: block;
      transition: transform 0.5s ease;
    }}

    .hero-image-wrapper:hover img {{
      transform: scale(1.05);
    }}
    
    .category-badge {{
      display: inline-block;
      padding: 0.25rem 0.75rem;
      background: rgba(var(--primary-rgb), 0.15);
      color: var(--primary);
      border: 1px solid rgba(var(--primary-rgb), 0.3);
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 1.5rem;
    }}
    
    h1 {{
      font-size: 3rem;
      font-weight: 850;
      line-height: 1.15;
      margin-bottom: 1.5rem;
      letter-spacing: -0.03em;
    }}
    
    .desc {{
      color: var(--text-muted);
      font-size: 1.125rem;
      line-height: 1.6;
      margin-bottom: 2rem;
    }}
    
    .cta-group {{
      display: flex;
      gap: 1rem;
    }}
    
    .btn {{
      padding: 0.75rem 1.75rem;
      border-radius: 0.75rem;
      font-size: 0.875rem;
      font-weight: 700;
      text-decoration: none;
      transition: all 0.2s;
    }}
    
    .btn-primary {{
      background: var(--primary);
      color: #fff;
      box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.4);
    }}
    
    .btn-primary:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(var(--primary-rgb), 0.5);
    }}
    
    .btn-secondary {{
      background: transparent;
      color: var(--text);
      border: 1px solid var(--border);
    }}
    
    .btn-secondary:hover {{
      background: rgba(255,255,255,0.05);
      transform: translateY(-2px);
    }}
    
    .features {{
      padding: 4rem 2rem;
      background: rgba(30, 41, 59, 0.3);
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
      width: 100%;
    }}
    
    .section-title {{
      text-align: center;
      font-size: 1.75rem;
      font-weight: 800;
      margin-bottom: 3rem;
    }}
    
    .features-grid {{
      max-width: 1100px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 2rem;
    }}
    
    .feature-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 1.25rem;
      overflow: hidden;
      transition: transform 0.3s ease, border-color 0.3s ease;
    }}
    
    .feature-card:hover {{
      transform: translateY(-6px);
      border-color: rgba(var(--primary-rgb), 0.5);
    }}

    .feature-card img {{
      width: 100%;
      height: 180px;
      object-fit: cover;
      display: block;
    }}

    .feature-card-content {{
      padding: 1.5rem;
    }}
    
    .feature-icon {{
      width: 2.5rem;
      height: 2.5rem;
      background: rgba(var(--primary-rgb), 0.15);
      color: var(--primary);
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 0.5rem;
      font-size: 1.25rem;
      font-weight: bold;
      margin-bottom: 1rem;
    }}
    
    .feature-card h3 {{
      font-size: 1.125rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
    }}
    
    .feature-card p {{
      color: var(--text-muted);
      font-size: 0.875rem;
      line-height: 1.5;
    }}
    
    footer {{
      padding: 3rem 2rem 6rem 2rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.875rem;
      border-top: 1px solid var(--border);
      width: 100%;
    }}
  </style>
</head>
<body>
  <div class="bg-grid"></div>
  
  <header>
    <div class="logo">
      <span>✦</span>
      <span>{b_name}</span>
    </div>
    <nav>
      <a href="#" class="active">Home</a>
      <a href="#">Products & Services</a>
      <a href="#">About Us</a>
      <a href="#">Contact</a>
    </nav>
    <a href="#" class="nav-btn">Get Started</a>
  </header>
  
  <main class="hero-container">
    <div>
      <div class="category-badge">{(template.framework or 'HTML').upper()} Template</div>
      <h1>{c_title}</h1>
      <p class="desc">{c_sub}</p>
      <div class="cta-group">
        <a href="#" class="btn btn-primary">{c_cta}</a>
        <a href="#" class="btn btn-secondary">Explore Gallery</a>
      </div>
    </div>
    <div class="hero-image-wrapper">
      <img src="{hero_bg_url}" alt="Website Hero Visual" />
    </div>
  </main>
  
  <section class="features">
    <h2 class="section-title">Visual Showcase & Signature Features</h2>
    <div class="features-grid">
      <div class="feature-card">
        <img src="{gallery_1}" alt="Feature 1 Showcase" />
        <div class="feature-card-content">
          <div class="feature-icon">✨</div>
          <h3>Crafted Experience</h3>
          <p>Curated visual layouts designed to elevate your brand presence and engage customers.</p>
        </div>
      </div>
      <div class="feature-card">
        <img src="{gallery_2}" alt="Feature 2 Showcase" />
        <div class="feature-card-content">
          <div class="feature-icon">⚡</div>
          <h3>Atmospheric Design</h3>
          <p>Modern aesthetics utilizing premium colors, glowing gradients, and responsive grids.</p>
        </div>
      </div>
      <div class="feature-card">
        <img src="{gallery_3}" alt="Feature 3 Showcase" />
        <div class="feature-card-content">
          <div class="feature-icon">🛡️</div>
          <h3>Artisanal Quality</h3>
          <p>Built with attention to detail across typography, spacing systems, and interactive cards.</p>
        </div>
      </div>
    </div>
  </section>
  
  <footer>
    <p>&copy; 2026 {b_name}. Powered by Site Studio.</p>
  </footer>
  {watermark_payload}
</body>
</html>"""
        return Response(content=fallback_html.encode("utf-8"), media_type="text/html", headers=security_scanner.get_secure_preview_headers())

    try:
        download_assets = template.download_assets or {}
        zip_url = download_assets.get("zip")
        if not zip_url:
            raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
            
        from app.core.storage import storage
        from app.core.local_project_manager import local_project_manager

        # Check if project source code is already saved in the local workspace
        local_dir = local_project_manager.get_local_project_dir(template_id, version="latest")
        if not local_dir and template.slug:
            local_dir = local_project_manager.get_local_project_dir(template.slug, version="latest")

        storage_base = urlsplit(storage.public_url)
        asset_url = urlsplit(str(zip_url))
        file_id = storage._parse_file_id(str(zip_url))
        expected_asset_path = f"{storage_base.path.rstrip('/')}/{file_id}" if file_id else None

        def _is_local_host(netloc: str) -> bool:
            host = netloc.split(":")[0].lower()
            return host in ("localhost", "127.0.0.1", "0.0.0.0", "::1")

        is_local_netloc = _is_local_host(asset_url.netloc) and _is_local_host(storage_base.netloc)
        same_netloc = asset_url.netloc.lower() == storage_base.netloc.lower()

        if not file_id:
            match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
            if match:
                try:
                    file_id = uuid.UUID(match.group(1))
                except Exception:
                    file_id = None

        is_external = not (
            file_id
            and (asset_url.scheme == storage_base.scheme or is_local_netloc)
            and (same_netloc or is_local_netloc)
            and (asset_url.path == expected_asset_path or (file_id and str(file_id) in asset_url.path))
        )

        # Check local filesystem first: if already extracted, skip slow remote DB round trips
        preview_slug_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template.slug)) if template.slug else None
        preview_id_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template.id))
        
        has_local_files = bool(
            (local_dir and os.path.exists(str(local_dir)))
            or (os.path.exists(preview_id_dir) and os.listdir(preview_id_dir))
            or (preview_slug_dir and os.path.exists(preview_slug_dir) and os.listdir(preview_slug_dir))
        )

        if has_local_files:
            is_external = False
        elif file_id and is_external:
            from app.models.stored_file import StoredFile
            res = await db.execute(select(StoredFile.id).where(StoredFile.id == file_id))
            if res.scalar_one_or_none():
                is_external = False

        # Do not fetch seller-controlled URLs from the API process. Templates
        # must use an archive uploaded to Studio storage to prevent SSRF.
        if is_external and not local_dir:
            raise HTTPException(
                status_code=400,
                detail="Preview archives must be uploaded to Studio storage; external archive URLs are not supported.",
            )
            
        if local_dir and os.path.exists(str(local_dir)):
            preview_dir = str(local_dir)
        elif os.path.exists(preview_id_dir) and os.listdir(preview_id_dir):
            preview_dir = preview_id_dir
        elif preview_slug_dir and os.path.exists(preview_slug_dir) and os.listdir(preview_slug_dir):
            preview_dir = preview_slug_dir
        else:
            preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
            os.makedirs(preview_dir, exist_ok=True)
        project_root = preview_dir

        import json
        import shutil

        def detect_project_ui_package_json(base_dir: str) -> Optional[str]:
            # Priority 1: Check standard UI locations
            for cand in [
                os.path.join(base_dir, "frontend", "package.json"),
                os.path.join(base_dir, "package.json"),
                os.path.join(base_dir, "client", "package.json"),
                os.path.join(base_dir, "web", "package.json"),
                os.path.join(base_dir, "ui", "package.json"),
            ]:
                if os.path.isfile(cand):
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                            if "scripts" in p_data and ("build" in p_data["scripts"] or "dev" in p_data["scripts"]):
                                return cand
                    except Exception:
                        pass
            
            # Priority 2: Walk only safe non-vendor directories (NEVER descend into node_modules/backend/dist)
            for root, dirs, files in os.walk(base_dir):
                dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "dist", "build", ".output", "vendor", "backend", ".venv", "env"]]
                if "package.json" in files:
                    cand = os.path.join(root, "package.json")
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                            if "scripts" in p_data and ("build" in p_data["scripts"] or "dev" in p_data["scripts"]):
                                return cand
                    except Exception:
                        pass
            return None

        lock = _build_locks.setdefault(template_id, asyncio.Lock())
        async with lock:
            # 1. Detect package.json or check if source files exist
            package_json_path = detect_project_ui_package_json(preview_dir)

            # If directory is missing, empty, or index.html is missing, extract fresh from ZIP safely
            need_extract = not os.path.exists(preview_dir) or not os.listdir(preview_dir)
            if not need_extract and not package_json_path:
                if not os.path.exists(os.path.join(preview_dir, "index.html")):
                    has_html = any(f.endswith(".html") for r, d, files in os.walk(preview_dir) for f in files)
                    if not has_html:
                        need_extract = True

            if need_extract:
                if os.path.exists(preview_dir):
                    shutil.rmtree(preview_dir, ignore_errors=True)
                os.makedirs(preview_dir, exist_ok=True)

                from app.core.storage import storage
                archive_temp_dir = Path(tempfile.mkdtemp(prefix="studio_preview_archive_"))
                archive_path = archive_temp_dir / "source-upload"
                stored_file = await storage.copy_to_path(db, file_id, archive_path)
                if not stored_file:
                    shutil.rmtree(archive_temp_dir, ignore_errors=True)
                    raise HTTPException(status_code=404, detail="Source template archive data not found")

                # Extract ZIP or write raw HTML file
                from app.services.security_scanner import security_scanner
                try:
                    if not zipfile.is_zipfile(archive_path):
                        # Raw HTML file uploaded directly
                        shutil.copyfile(archive_path, os.path.join(preview_dir, "index.html"))
                    else:
                        archive_report = security_scanner.scan_zip_file(archive_path, stored_file.original_filename or "template.zip")
                        if not archive_report.get("is_safe"):
                            raise HTTPException(status_code=400, detail=archive_report.get("reason", "Archive failed security inspection"))
                        security_scanner.sanitize_extract_zip_file(archive_path, Path(preview_dir))
                finally:
                    shutil.rmtree(archive_temp_dir, ignore_errors=True)

                # Re-detect package.json after extraction
                package_json_path = detect_project_ui_package_json(preview_dir)

            # Auto-flatten single wrapper subfolder (e.g., port/index.html -> index.html)
            if not package_json_path and os.path.exists(preview_dir):
                subitems = [os.path.join(preview_dir, i) for i in os.listdir(preview_dir) if not i.startswith(".")]
                if len(subitems) == 1 and os.path.isdir(subitems[0]):
                    inner_folder = subitems[0]
                    for sub_item in os.listdir(inner_folder):
                        src_p = os.path.join(inner_folder, sub_item)
                        dst_p = os.path.join(preview_dir, sub_item)
                        shutil.move(src_p, dst_p)
                    try:
                        os.rmdir(inner_folder)
                    except Exception:
                        pass

            build_folders = ["dist", "out", "build", ".output"]
            serve_root = preview_dir
            build_dir = None

            is_custom_draft_item = (
                template.template_origin == "custom_draft"
                or template.status == TemplateStatus.DRAFT
                or "-custom-" in (template.slug or "")
                or "-draft-" in (template.slug or "")
            )

            # For customized user drafts, purge any stale pre-compiled build folders so edited source files run
            if is_custom_draft_item:
                for bf in build_folders:
                    for root, dirs, _ in list(os.walk(preview_dir)):
                        if bf in dirs:
                            shutil.rmtree(os.path.join(root, bf), ignore_errors=True)

            # Detect if this template is pure HTML / static vs modern framework
            template_fw_str = (template.framework.value if template.framework else "").lower()
            
            # Check package.json to verify if modern framework dependencies exist
            has_framework_deps = False
            if package_json_path and os.path.exists(package_json_path):
                try:
                    with open(package_json_path, "r", encoding="utf-8") as _pf:
                        _pdata = json.load(_pf)
                        _all_deps = {**_pdata.get("dependencies", {}), **_pdata.get("devDependencies", {})}
                        if any(k in _all_deps for k in ["react", "react-dom", "vue", "next", "nuxt", "svelte", "@angular/core", "astro", "vite"]):
                            has_framework_deps = True
                except Exception:
                    pass

            is_html_template = (template_fw_str in ("html", "vanilla", "static")) and not has_framework_deps

            if is_html_template:
                # Pure HTML templates run instantly in browser without Node/Vite compilation
                package_json_path = None
                if os.path.exists(os.path.join(preview_dir, "frontend", "index.html")):
                    serve_root = os.path.join(preview_dir, "frontend")
                else:
                    serve_root = preview_dir

            if package_json_path:
                project_root = os.path.dirname(package_json_path)

                # Check if project is already compiled (skip for custom drafts so updated source code runs live)
                if not is_custom_draft_item:
                    for d in build_folders:
                        candidate = os.path.join(project_root, d)
                        if os.path.isdir(candidate):
                            for b_root, b_dirs, b_files in os.walk(candidate):
                                if "index.html" in b_files:
                                    build_dir = b_root
                                    break
                            if build_dir:
                                break

                # Compile any package-based SPA (React, Vue, Angular, etc.) into a static bundle.
                if not build_dir:
                    try:
                        from app.services.deployment_providers.local_provider import local_deployment_provider
                        build_success, build_logs, candidate_path = await local_deployment_provider.build(
                            project_root,
                            deployment_id=str(template_id)
                        )
                        if build_success and candidate_path and os.path.exists(candidate_path):
                            build_dir = candidate_path
                        elif not build_success:
                            logger.error(
                                "Live preview build failed for %s (%s): %s",
                                template_id,
                                template_fw_str or "unknown framework",
                                str(build_logs or "No build output")[-4000:],
                            )
                    except Exception as e_build:
                        logger.exception("Auto-compilation failed for %s preview %s", template_fw_str or "framework", template_id)

            if build_dir:
                serve_root = build_dir
            elif template_fw_str in ("react", "nextjs", "vue", "nuxt", "svelte") or (request.query_params.get("framework") or "").lower() in ("react", "vue", "svelte"):
                # If template is declared or requested as a modern framework and not pre-compiled into dist/,
                # always run via the In-Browser Standalone Runner (React 18 + Babel or Vue 3) so the user's
                # actual App.jsx / App.vue executes live in the preview, NEVER a static HTML mirror!
                logger.info("Serving modern framework template %s (%s) directly via in-browser runner", template_id, template_fw_str)
                return await serve_fallback(f"Preview compilation: in-browser runner for {template_fw_str}")
            elif any(f in ("App.jsx", "App.tsx", "App.vue", "App.svelte") for r, d, files in os.walk(preview_dir) for f in files if "node_modules" not in r):
                logger.info("Detected App.jsx / App.vue in %s; serving directly via in-browser runner", template_id)
                return await serve_fallback("Found framework source file; serving via in-browser runner")
            elif package_json_path:
                # A framework's source index.html is only an empty mount point
                # (for example <div id="app"></div>). Never serve it as if it
                # were a finished website when compilation failed. Prefer an
                # actual static mirror packaged beside frontend/ instead.
                preview_root = Path(preview_dir).resolve()
                framework_root = Path(project_root).resolve()
                mirror_root = None
                for root, dirs, files in os.walk(preview_root):
                    dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", ".venv", "dist", "build", ".output", "backend"}]
                    current = Path(root).resolve()
                    if framework_root in current.parents:
                        dirs[:] = []
                        continue
                    if current == framework_root:
                        continue
                    if "index.html" in files:
                        mirror_root = root
                        break
                if mirror_root:
                    serve_root = mirror_root
                else:
                    logger.info("Static build unavailable for %s (%s); serving via in-browser React runner.", template_id, template_fw_str)
                    return await serve_fallback("Preview compilation fallback")
            elif os.path.exists(os.path.join(project_root, "index.html")):
                # The generator crafted a complete standalone responsive HTML with Tailwind CDN & full domain content in project_root.
                # Serve this actual generated user template instead of falling back to a generic template!
                serve_root = project_root
            else:
                serve_root = project_root
    
        # Locate entry HTML file (index.html, index.htm, or any single/fallback HTML page)
        index_file_path = os.path.join(serve_root, "index.html")
        if not os.path.exists(index_file_path):
            found_html = None
            candidate_names = ["index.htm", "home.html", "landing.html", "main.html", "default.html", "app.html"]
            # 1. Check priority candidates in serve_root
            for cand in candidate_names:
                candidate_path = os.path.join(serve_root, cand)
                if os.path.exists(candidate_path):
                    found_html = candidate_path
                    break

            # 2. Search recursively for index.html, index.htm, or candidate names
            if not found_html:
                for root, dirs, files in os.walk(serve_root):
                    for cand in ["index.html", "index.htm"] + candidate_names:
                        if cand in files:
                            found_html = os.path.join(root, cand)
                            serve_root = root
                            break
                    if found_html:
                        break

            # 3. If still not found, search for ANY .html / .htm file in the extracted template
            if not found_html:
                for root, dirs, files in os.walk(serve_root):
                    html_files = [f for f in files if f.lower().endswith((".html", ".htm"))]
                    if html_files:
                        found_html = os.path.join(root, html_files[0])
                        serve_root = root
                        break

            if found_html:
                index_file_path = found_html
            else:
                # Dynamic multi-framework fallback: compile & run Vue, React, Svelte, or static components
                return await serve_fallback("Preview compilation: finding framework entry point")
    
        # Determine file to serve
        if not filepath or filepath == "/":
            full_path = index_file_path
        else:
            preview_root = Path(serve_root).resolve()
            candidate_path = (preview_root / filepath).resolve()
            try:
                candidate_path.relative_to(preview_root)
            except ValueError:
                raise HTTPException(status_code=404, detail="Requested file not found in template")
            full_path = str(candidate_path)
            
            # Fallback for nested layouts if not found directly
            if not os.path.exists(full_path):
                subdirs = [d for d in os.listdir(serve_root) if os.path.isdir(os.path.join(serve_root, d)) and d not in ["__MACOSX"]]
                if len(subdirs) == 1:
                    nested_root = (preview_root / subdirs[0]).resolve()
                    nested_path = (nested_root / candidate_path.relative_to(preview_root)).resolve()
                    try:
                        nested_path.relative_to(preview_root)
                    except ValueError:
                        raise HTTPException(status_code=404, detail="Requested file not found in template")
                    if os.path.exists(nested_path):
                        full_path = str(nested_path)
    
        is_asset_request = bool(re.search(r'\.(?:png|jpg|jpeg|svg|webp|gif|ico|avif|bmp|tiff|css|js|mjs|woff|woff2|ttf|eot|otf|mp4|webm|mp3|wav|ogg|pdf|json|map)$', filepath or "", re.I))
        is_image_request = bool(re.search(r'\.(?:png|jpg|jpeg|svg|webp|gif|ico|avif|bmp)$', filepath or "", re.I))

        if not os.path.exists(full_path) or os.path.isdir(full_path):
            # 1. Clean URL resolution: check if appending .html or .htm matches a real page
            if not is_asset_request and os.path.exists(full_path + ".html"):
                full_path = full_path + ".html"
            elif not is_asset_request and os.path.exists(full_path + ".htm"):
                full_path = full_path + ".htm"
            # 2. Directory route: check if directory contains index.html
            elif not is_asset_request and os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, "index.html")):
                full_path = os.path.join(full_path, "index.html")
            else:
                found_match = None
                clean_target = (filepath or "").lstrip("/").replace("\\", "/")
                target_base = os.path.basename(clean_target).lower()

                # Check all alternative local extraction and project roots
                search_roots = [serve_root]
                for extra_r in [preview_dir, preview_id_dir, preview_slug_dir]:
                    if extra_r and os.path.exists(extra_r) and extra_r not in search_roots:
                        search_roots.append(extra_r)

                # 3a. Direct check for filepath in alternative roots & their direct subfolders
                for sr in search_roots:
                    direct_cand = os.path.join(sr, clean_target)
                    if os.path.isfile(direct_cand):
                        found_match = direct_cand
                        break
                    try:
                        for sub in os.listdir(sr):
                            sub_p = os.path.join(sr, sub)
                            if os.path.isdir(sub_p) and sub not in ["node_modules", ".git", "__MACOSX"]:
                                nested_cand = os.path.join(sub_p, clean_target)
                                if os.path.isfile(nested_cand):
                                    found_match = nested_cand
                                    break
                    except Exception:
                        pass
                    if found_match:
                        break

                # 3b. Recursive search by relative path suffix or filename match across all roots
                if not found_match and target_base:
                    for sr in search_roots:
                        try:
                            for root, dirs, files in os.walk(sr):
                                dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "__MACOSX"]]
                                for f in files:
                                    f_lower = f.lower()
                                    full_f = os.path.join(root, f)
                                    rel_f = os.path.relpath(full_f, sr).replace("\\", "/").lower()
                                    if rel_f.endswith(clean_target.lower()) or f_lower == target_base:
                                        found_match = full_f
                                        break
                                if found_match:
                                    break
                        except Exception:
                            pass
                        if found_match:
                            break

                # 3c. Direct ZIP Archive Fallback: If still not on disk, extract it directly from the template StoredFile zip!
                if not found_match and is_asset_request:
                    try:
                        d_assets = template.download_assets or {}
                        z_url = d_assets.get("zip")
                        if z_url:
                            uuid_m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(z_url))
                            if uuid_m:
                                from app.models import StoredFile
                                sf_res = await db.execute(select(StoredFile).where(StoredFile.id == uuid.UUID(uuid_m.group(1))))
                                sf_obj = sf_res.scalar_one_or_none()
                                if sf_obj and sf_obj.data and zipfile.is_zipfile(io.BytesIO(sf_obj.data)):
                                    with zipfile.ZipFile(io.BytesIO(sf_obj.data), "r") as zf:
                                        zf_names = zf.namelist()
                                        matched_entry = None
                                        # First try exact path suffix match
                                        for zn in zf_names:
                                            zn_clean = zn.replace("\\", "/").lower()
                                            if zn_clean.endswith(clean_target.lower()):
                                                matched_entry = zn
                                                break
                                        # Second try filename match
                                        if not matched_entry and target_base:
                                            for zn in zf_names:
                                                if os.path.basename(zn).lower() == target_base:
                                                    matched_entry = zn
                                                    break
                                        if matched_entry:
                                            asset_bytes = zf.read(matched_entry)
                                            # Cache onto disk at candidate_path so subsequent requests are fast
                                            try:
                                                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                                                with open(full_path, "wb") as _cached:
                                                    _cached.write(asset_bytes)
                                                found_match = full_path
                                            except Exception:
                                                m_type, _ = mimetypes.guess_type(matched_entry)
                                                return Response(content=asset_bytes, media_type=m_type or "application/octet-stream", headers=security_scanner.get_secure_preview_headers())
                    except Exception as z_err:
                        logger.warning(f"Live preview ZIP asset extraction fallback notice: {z_err}")

                if found_match and os.path.exists(found_match):
                    full_path = found_match
                elif is_asset_request:
                    # NEVER serve index.html for images or assets!
                    if is_image_request:
                        clean_name = os.path.basename(clean_target)
                        placeholder_svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400"><rect width="100%" height="100%" fill="#1e293b"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#64748b" font-family="sans-serif" font-size="16">{clean_name}</text></svg>'
                        return Response(content=placeholder_svg.encode("utf-8"), media_type="image/svg+xml", headers=security_scanner.get_secure_preview_headers())
                    raise HTTPException(status_code=404, detail=f"Asset '{filepath}' not found in template")
                elif os.path.exists(index_file_path):
                    # SPA client-side route fallback only for pages/documents (e.g. /about, /features, /pricing)
                    full_path = index_file_path
                else:
                    raise HTTPException(status_code=404, detail="Requested file not found in template")
                
        mime_type, _ = mimetypes.guess_type(full_path)
        if not mime_type:
            mime_type = "application/octet-stream"
            
        with open(full_path, "rb") as f:
            content = f.read()
    
        # Rewrite absolute references to relative on all HTML preview pages
        if mime_type == "text/html":
            try:
                html_content = content.decode("utf-8", errors="ignore")
                
                # 1. Rewrite absolute references to relative on all HTML preview pages
                html_content = re.sub(r'src="/(?![/])', 'src="./', html_content)
                html_content = re.sub(r'href="/(?![/])', 'href="./', html_content)
    
                # 1a. Ensure viewport meta tag exists for proper mobile/tablet responsiveness in iframe
                if "<meta name=\"viewport\"" not in html_content.lower() and "<meta name='viewport'" not in html_content.lower():
                    viewport_meta = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
                    if "<head>" in html_content:
                        html_content = html_content.replace("<head>", f"<head>\n  {viewport_meta}", 1)
                    elif "<html>" in html_content:
                        html_content = html_content.replace("<html>", f"<html>\n  <head>{viewport_meta}</head>", 1)
                    else:
                        html_content = f"<head>{viewport_meta}</head>\n" + html_content
    
                # 1b. Inject dynamic query parameter customizations into HTML for live preview customization
                customized = request.query_params.get("customized") == "true"
                if customized:
                    business_name = request.query_params.get("businessName")
                    primary_color = request.query_params.get("primaryColor")
                    custom_title = request.query_params.get("title")
                    custom_subtitle = request.query_params.get("subtitle")
                    custom_cta = request.query_params.get("ctaText")
                    logo_text = request.query_params.get("logoText")
    
                    # Override primary theme colors in CSS variables dynamically
                    if primary_color:
                        color_override_style = f"""
                        <style>
                          :root {{
                            --primary: {primary_color} !important;
                            --primary-color: {primary_color} !important;
                            --theme-color: {primary_color} !important;
                            --accent: {primary_color} !important;
                            --accent-color: {primary_color} !important;
                            --cta-bg: {primary_color} !important;
                          }}
                          a, button, .btn-primary, .bg-primary {{
                            background-color: {primary_color} !important;
                            border-color: {primary_color} !important;
                          }}
                          .text-primary, a:hover {{
                            color: {primary_color} !important;
                          }}
                        </style>
                        """
                        if "</head>" in html_content:
                            html_content = html_content.replace("</head>", f"{color_override_style}\n</head>", 1)
    
                    # Simple text/copy replacements
                    if business_name:
                        html_content = re.sub(r'<title>.*?</title>', f'<title>{business_name} - Preview</title>', html_content, flags=re.IGNORECASE)
                    if custom_title and template.title:
                        html_content = html_content.replace(template.title, custom_title)
                
                from app.models.template import TemplateFramework
                should_rewrite_history = "true" if template.framework != TemplateFramework.HTML else "false"
                
                # 2. Inject client-side routing and location sandboxing script (including absolute <base> tag)
                sandbox_script = f"""<base href="/api/v1/preview/live/{template_id}/" />
    <script>
      (function() {{
        const basePrefix = "/api/v1/preview/live/{template_id}";
        
        // Intercept fetch calls to rewrite root-relative API calls
        const originalFetch = window.fetch;
        window.fetch = function(input, init) {{
          let url = typeof input === 'string' ? input : (input instanceof Request ? input.url : '');
          if (url.startsWith('/api/')) {{
            url = basePrefix + url;
            if (input instanceof Request) {{
              input = new Request(url, input);
            }} else {{
              input = url;
            }}
          }}
          return originalFetch(input, init);
        }};

        // Intercept XMLHttpRequest
        const originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url, ...args) {{
          if (typeof url === 'string' && url.startsWith('/api/')) {{
            url = basePrefix + url;
          }}
          return originalOpen.apply(this, [method, url, ...args]);
        }};

        // 1. Client-Side Router Harmonizer: match live preview prefix dynamically
        try {{
          const liveMatch = window.location.pathname.match(/^\\/api\\/v1\\/preview\\/live\\/[^\\/]+/);
          const activePrefix = liveMatch ? liveMatch[0] : basePrefix;
          if (activePrefix && window.location.pathname.startsWith(activePrefix)) {{
            let targetPath = window.location.pathname.slice(activePrefix.length);
            if (!targetPath || !targetPath.startsWith('/')) {{
              targetPath = '/' + (targetPath || '');
            }}
            window.history.replaceState(null, '', targetPath);
          }}
        }} catch (e) {{
          console.warn("[Live Preview Sandbox] History rewrite non-critical notice:", e);
        }}

        // React Router Root Render Watchdog (guarantees Home renders if router lagged)
        window.addEventListener('DOMContentLoaded', function() {{
          setTimeout(function() {{
            const rootEl = document.getElementById('root') || document.getElementById('app');
            if (rootEl && rootEl.children.length === 0) {{
              try {{
                window.history.replaceState(null, '', '/');
                window.dispatchEvent(new PopStateEvent('popstate', {{ state: null }}));
              }} catch (_) {{}}
            }}
          }}, 350);
        }});
    
        // 4. Live Theme Color Synchronizer & Dynamic CSS Variable Override
        function applyLiveThemeColor(color) {{
          if (!color) return;
          try {{
            let styleTag = document.getElementById('studio-live-theme-override');
            if (!styleTag) {{
              styleTag = document.createElement('style');
              styleTag.id = 'studio-live-theme-override';
              document.head.appendChild(styleTag);
            }}
            let clean = color.replace('#', '');
            if (clean.length === 3) clean = clean.split('').map(function(c) {{ return c + c; }}).join('');
            let r = parseInt(clean.substring(0, 2), 16) || 79;
            let g = parseInt(clean.substring(2, 4), 16) || 70;
            let b = parseInt(clean.substring(4, 6), 16) || 229;
            let rH = Math.max(0, Math.floor(r * 0.82));
            let gH = Math.max(0, Math.floor(g * 0.82));
            let bH = Math.max(0, Math.floor(b * 0.82));
            let hoverColor = '#' + [rH, gH, bH].map(function(x) {{ return x.toString(16).padStart(2, '0'); }}).join('');
            let gradCss = 'linear-gradient(135deg, ' + color + ' 0%, ' + hoverColor + ' 100%)';
            let gradRevCss = 'linear-gradient(135deg, ' + hoverColor + ' 0%, ' + color + ' 100%)';

            styleTag.textContent = 
              ':root, :root[data-theme="light"], :root[data-theme="dark"], html, body {{' +
              '--c-primary: ' + color + ' !important;' +
              '--c-primary-hover: ' + hoverColor + ' !important;' +
              '--color-primary: ' + color + ' !important;' +
              '--color-primary-dark: ' + hoverColor + ' !important;' +
              '--color-primary-hover: ' + hoverColor + ' !important;' +
              '--primary: ' + color + ' !important;' +
              '--primary-color: ' + color + ' !important;' +
              '--primary-hover: ' + hoverColor + ' !important;' +
              '--primary-dark: ' + hoverColor + ' !important;' +
              '--accent: ' + color + ' !important;' +
              '--accent-color: ' + color + ' !important;' +
              '--accent-primary: ' + color + ' !important;' +
              '--accent-hover: ' + hoverColor + ' !important;' +
              '--color-accent: ' + color + ' !important;' +
              '--theme-color: ' + color + ' !important;' +
              '--brand: ' + color + ' !important;' +
              '--brand-color: ' + color + ' !important;' +
              '--cta-bg: ' + color + ' !important;' +
              '--accent-gold: ' + color + ' !important;' +
              '--accent-gold-hover: ' + hoverColor + ' !important;' +
              '--accent-amber: ' + color + ' !important;' +
              '--blue: ' + color + ' !important;' +
              '--violet: ' + hoverColor + ' !important;' +
              '--cyan: ' + color + ' !important;' +
              '--green: ' + color + ' !important;' +
              '--red: ' + color + ' !important;' +
              '--red-dim: ' + hoverColor + ' !important;' +
              '--grad: ' + gradCss + ' !important;' +
              '--grad-r: ' + gradRevCss + ' !important;' +
              '--glow-blue: rgba(' + r + ',' + g + ',' + b + ',0.25) !important;' +
              '--glow-vio: rgba(' + rH + ',' + gH + ',' + bH + ',0.2) !important;' +
              '--border2: rgba(' + r + ',' + g + ',' + b + ',0.3) !important;' +
              '}}' +
              '.btn-primary, .nav-cta, .hero-cta, .btn, .button, .primary-btn, a.btn-primary, button.btn-primary, [data-theme-color="true"], [class*="btn-primary"], [class*="nav-cta"] {{' +
              'background: ' + gradCss + ' !important;' +
              'background-color: ' + color + ' !important;' +
              'background-image: ' + gradCss + ' !important;' +
              'border-color: ' + color + ' !important;' +
              'color: #ffffff !important;' +
              'box-shadow: 0 4px 18px rgba(' + r + ',' + g + ',' + b + ',0.35) !important;' +
              '}}' +
              '.btn-primary:hover, .nav-cta:hover, .hero-cta:hover, .primary-btn:hover {{' +
              'background: ' + gradRevCss + ' !important;' +
              'background-color: ' + hoverColor + ' !important;' +
              'background-image: ' + gradRevCss + ' !important;' +
              'border-color: ' + hoverColor + ' !important;' +
              'color: #ffffff !important;' +
              '}}' +
              '.nav-logo, h1 .accent, .accent, .accent-text, [class*="accent-text"], .gradient-text, .text-gradient, a.brand-logo span, .hero-subtitle span {{' +
              'background: ' + gradCss + ' !important;' +
              'background-clip: text !important;' +
              '-webkit-background-clip: text !important;' +
              '-webkit-text-fill-color: transparent !important;' +
              '}}' +
              '.text-primary, [class*="text-primary"], .nav-links a:hover, .brand-text, .gold-text {{' +
              'color: ' + color + ' !important;' +
              '}}' +
              '.pulse, .status-dot {{' +
              'background: ' + color + ' !important;' +
              'box-shadow: 0 0 0 0 rgba(' + r + ',' + g + ',' + b + ',0.5) !important;' +
              '}}' +
              '#crosshair, .tape-stripe {{ border-color: ' + color + ' !important; }}' +
              '#crosshair::before, #crosshair::after {{ background: ' + color + ' !important; }}' +
              '::selection {{ background: ' + color + ' !important; color: #ffffff !important; }}';

            ['--c-primary', '--color-primary', '--primary', '--theme-color', '--accent', '--blue', '--violet', '--cyan', '--grad'].forEach(function(p) {{
              try {{ document.documentElement.style.setProperty(p, color, 'important'); }} catch(_) {{}}
            }});
          }} catch (e) {{
            console.warn('[Studio Live Preview] Theme update error:', e);
          }}
        }}

        const initColor = new URLSearchParams(window.location.search).get('primaryColor') || new URLSearchParams(window.location.search).get('themeColor');
        if (initColor) {{
          applyLiveThemeColor(initColor);
        }}

        // 5. Real-Time Visual DOM Synchronizer ("Like Copy-Paste")
        function applyLiveContent(data) {{
          if (!data) return;
          const sectionId = data.sectionId || '';
          const key = data.key || '';
          const value = data.value;
          const originalText = (data.originalText || data.prevValue || '').toString().trim();
          if (typeof value === 'undefined' || value === null) return;

          let secEl = null;
          if (sectionId) {{
            const sIdClean = (sectionId || '').toLowerCase().trim();
            secEl = document.querySelector(
              '[data-section="' + sectionId + '"], ' +
              '#' + sectionId + ', ' +
              '.' + sectionId + ', ' +
              'section#' + sectionId + ', ' +
              'section.' + sectionId + ', ' +
              '[id*="' + sectionId + '"], ' +
              '[class*="' + sectionId + '-section"], ' +
              '[class*="' + sectionId + '_section"], ' +
              '[class*="' + sectionId + 'Section"], ' +
              '[class*="' + sectionId + '"], ' +
              '[data-section*="' + sectionId + '"]'
            );
            if (!secEl) {{
              if (sIdClean.includes('hero') || sIdClean.includes('banner')) {{
                secEl = document.querySelector('section.hero-section, .hero-section, header.hero, .hero, #hero, [class*="hero"], main > section:first-of-type');
              }} else if (sIdClean.includes('nav') || sIdClean.includes('header')) {{
                secEl = document.querySelector('nav, header, .navbar, .nav-container, [class*="navbar"]');
              }} else if (sIdClean.includes('foot')) {{
                secEl = document.querySelector('footer, .footer, [class*="footer"]');
              }} else if (sIdClean.includes('feature')) {{
                secEl = document.querySelector('#features, .features-section, [class*="feature"]');
              }} else if (sIdClean.includes('about') || sIdClean.includes('story')) {{
                secEl = document.querySelector('#about, .about-section, [class*="about"]');
              }} else if (sIdClean.includes('pricing') || sIdClean.includes('plan')) {{
                secEl = document.querySelector('#pricing, .pricing-section, [class*="pricing"]');
              }} else if (sIdClean.includes('contact') || sIdClean.includes('reach')) {{
                secEl = document.querySelector('#contact, .contact-section, [class*="contact"]');
              }}
            }}
          }}
          const root = secEl || document;

          // (C1) Main Headline / Section Title Color
          if (key === 'headlineColor' || key === 'titleColor' || key === 'sectionTitleColor') {{
            let h1 = root.querySelector('h1, .hero-title, [data-bind="headline"], [data-bind="title"], header h1, main h1, .section-title');
            if (!h1 && secEl) h1 = secEl.querySelector('h1, h2, .title');
            if (!h1) h1 = document.querySelector('h1, .hero-title');
            if (h1) {{
              h1.style.color = value || '';
              const spans = h1.querySelectorAll('span:not(.pulse)');
              spans.forEach(function(s) {{ s.style.color = value || ''; }});
            }}
            return;
          }}

          // (C2) Subtitle / Story / Bio / Narrative Description Color
          if (key === 'subtitleColor' || key === 'subheadlineColor' || key === 'storyColor' || key === 'descriptionColor' || key === 'taglineColor') {{
            let p = root.querySelector('.hero-sub, .hero-subtitle, .subtitle, [data-bind="subheadline"], [data-bind="subtitle"], [data-bind="story"], [data-bind="description"], .hero-description, .about-text, .lead, p.lead, header p, .story-content, .tagline');
            if (!p && secEl) p = secEl.querySelector('p');
            if (!p) p = document.querySelector('.hero-sub, .hero-subtitle, p.lead, header p');
            if (p) {{
              p.style.color = value || '';
            }}
            return;
          }}

          // (C3) Badge / Top Pill / Tag Color
          if (key === 'badgeColor' || key === 'tagColor') {{
            let badge = root.querySelector('.hero-badge, .badge, .pill, .status-pill, .case-badge, [data-bind="badgeText"]');
            if (!badge) badge = document.querySelector('.hero-badge, .badge, .pill, .status-pill');
            if (badge) {{
              badge.style.color = value || '';
              if (value) {{
                badge.style.borderColor = value + '44';
              }} else {{
                badge.style.borderColor = '';
              }}
            }}
            return;
          }}

          // (C4) Primary Button / CTA Text Color
          if (key === 'ctaColor' || key === 'primaryCtaColor' || key === 'buttonColor' || key === 'buttonTextColor') {{
            let btn = root.querySelector('.hero-cta, .btn-primary, .cta-button, .primary-btn, [data-bind="primaryCta"], [data-bind="ctaText"], [data-bind="buttonText"], button[type="submit"]');
            if (!btn && secEl) btn = secEl.querySelector('.btn, button, a.btn');
            if (!btn) btn = document.querySelector('.hero-cta, .btn-primary, .cta-button, .primary-btn');
            if (btn) {{
              btn.style.color = value || '';
            }}
            return;
          }}

          // (C5) Secondary Button Color
          if (key === 'secondaryCtaColor') {{
            let btn = root.querySelector('.btn-secondary, .btn-outline, .secondary-cta, .btn-ghost, [data-bind="secondaryCta"]');
            if (btn) {{
              btn.style.color = value || '';
            }}
            return;
          }}

          // (C6) Brand / Header Name Color
          if (key === 'brandNameColor' || key === 'businessNameColor') {{
            const brandEls = document.querySelectorAll('.brand-logo, .brand-name, .logo, .nav-logo, .navbar-brand, a.brand-logo, [data-bind="brandName"], [data-bind="businessName"], .logo-text, header .brand, .footer-logo');
            brandEls.forEach(function(el) {{
              el.style.color = value || '';
              const span = el.querySelector('span:not(.pulse), strong');
              if (span) span.style.color = value || '';
            }});
            return;
          }}

          // (C7) Logo Monogram / Code Color
          if (key === 'logoTextColor') {{
            const logoEls = document.querySelectorAll('.brand-code, .logo-monogram, [data-bind="logoText"], .logo-code, .monogram, .logo-mark, .brand-mark, .navbar-logo');
            logoEls.forEach(function(el) {{ el.style.color = value || ''; }});
            return;
          }}

          // (C8) Nav Links Color
          if (key === 'navLinksColor') {{
            const navAnchors = document.querySelectorAll('nav a:not(.brand-logo):not(.logo):not(.nav-logo), .nav-links a, .nav-item a, header nav a, header ul li a');
            navAnchors.forEach(function(a) {{ a.style.color = value || ''; }});
            return;
          }}

          // (C9) Footer Copyright Color
          if (key === 'copyrightColor') {{
            const cpEls = document.querySelectorAll('.copyright, footer small, footer p:last-child, [data-bind="copyright"]');
            cpEls.forEach(function(el) {{ el.style.color = value || ''; }});
            return;
          }}

          // (C10) Contact Info Colors
          if (key === 'phoneColor') {{
            document.querySelectorAll('a[href^="tel:"], .phone, .contact-phone, [data-bind="phone"]').forEach(function(el) {{ el.style.color = value || ''; }});
            return;
          }}
          if (key === 'emailColor') {{
            document.querySelectorAll('a[href^="mailto:"], .email, .contact-email, [data-bind="email"]').forEach(function(el) {{ el.style.color = value || ''; }});
            return;
          }}
          if (key === 'addressColor') {{
            document.querySelectorAll('.address, .contact-address, address, [data-bind="address"]').forEach(function(el) {{ el.style.color = value || ''; }});
            return;
          }}

          // (1) Brand / Business Name across headers, navbars, and signatures
          if (key === 'brandName' || key === 'businessName') {{
            const brandEls = document.querySelectorAll('.brand-logo, .brand-name, .logo, .nav-logo, .navbar-brand, a.brand-logo, [data-bind="brandName"], [data-bind="businessName"], .logo-text, header .brand, .footer-logo');
            brandEls.forEach(function(el) {{
              const span = el.querySelector('span:not(.pulse), strong');
              if (span) {{ span.textContent = value; }} else {{ el.textContent = value; }}
            }});
            document.title = value + ' – Live Preview';
            return;
          }}

          // (2) Logo Monogram / Code
          if (key === 'logoText') {{
            const logoEls = document.querySelectorAll('.brand-code, .logo-monogram, [data-bind="logoText"], .logo-code, .monogram, .logo-mark, .brand-mark, .navbar-logo, .logo');
            logoEls.forEach(function(el) {{
              // Preserve a neighboring brand name or decorative icon within combined logo links.
              const textNode = Array.from(el.childNodes).find(function(n) {{ return n.nodeType === Node.TEXT_NODE && n.nodeValue.trim(); }});
              if (textNode) textNode.nodeValue = textNode.nodeValue.replace(textNode.nodeValue.trim(), value);
              else if (!el.querySelector('span, strong, svg, img, i')) el.textContent = value;
              else {{
                const mark = el.querySelector('.brand-code, .logo-monogram, .logo-mark, .brand-mark, [data-bind="logoText"]');
                if (mark) mark.textContent = value;
              }}
            }});
            return;
          }}

          // (3) Main Headline / Section Title
          if (key === 'headline' || key === 'title') {{
            let h1 = root.querySelector('h1, .hero-title, [data-bind="headline"], [data-bind="title"], header h1, main h1, .section-title');
            if (!h1 && secEl) h1 = secEl.querySelector('h1, h2, .title');
            if (!h1) h1 = document.querySelector('h1, .hero-title');
            if (h1) {{
              const highlightSpan = h1.querySelector('.highlight, .text-primary, .accent, .accent-text, span');
              if (highlightSpan && typeof value === 'string' && value.includes(' ')) {{
                const words = value.split(' ');
                const lastWord = words.pop();
                h1.textContent = words.join(' ') + ' ';
                highlightSpan.textContent = lastWord;
                h1.appendChild(highlightSpan);
              }} else {{
                h1.textContent = value;
              }}
            }}
            return;
          }}

          // (4) Subtitle / Story / Bio / Narrative Description
          if (key === 'subheadline' || key === 'subtitle' || key === 'story' || key === 'description') {{
            let p = root.querySelector('.hero-sub, .hero-subtitle, .subtitle, [data-bind="subheadline"], [data-bind="subtitle"], [data-bind="story"], [data-bind="description"], .hero-description, .about-text, .lead, p.lead, header p, .story-content');
            if (!p && secEl) p = secEl.querySelector('p');
            if (!p) p = document.querySelector('.hero-sub, .hero-subtitle, p.lead, header p');
            if (p) {{
              p.textContent = value;
            }}
            return;
          }}

          // (5) Badge Text / Top Pill
          if (key === 'badgeText') {{
            let badge = root.querySelector('.hero-badge, .badge, .pill, .status-pill, .case-badge, [data-bind="badgeText"]');
            if (!badge) badge = document.querySelector('.hero-badge, .badge, .pill, .status-pill');
            if (badge) {{
              const pulse = badge.querySelector('.pulse');
              if (pulse) {{
                badge.innerHTML = '';
                badge.appendChild(pulse);
                badge.appendChild(document.createTextNode(' ' + value));
              }} else {{
                badge.textContent = value;
              }}
            }}
            return;
          }}

          // (6) Primary Button / CTA Text & Link
          if (key === 'primaryCta' || key === 'ctaText' || key === 'buttonText') {{
            let btn = root.querySelector('.hero-cta, .btn-primary, .cta-button, .primary-btn, [data-bind="primaryCta"], [data-bind="ctaText"], [data-bind="buttonText"], button[type="submit"]');
            if (!btn && secEl) btn = secEl.querySelector('.btn, button, a.btn');
            if (!btn) btn = document.querySelector('.hero-cta, .btn-primary, .cta-button, .primary-btn');
            if (btn) {{
              const icon = btn.querySelector('i');
              if (icon) {{
                btn.innerHTML = '';
                btn.appendChild(icon);
                btn.appendChild(document.createTextNode(' ' + value));
              }} else {{
                btn.textContent = value;
              }}
            }}
            return;
          }}
          if (key === 'primaryCtaLink' || key === 'ctaLink') {{
            let btn = root.querySelector('.hero-cta, .btn-primary, .cta-button, .primary-btn, [data-bind="primaryCta"], a[href]');
            if (btn && btn.tagName === 'A') btn.setAttribute('href', value);
            return;
          }}

          // (7) Secondary Button & Link
          if (key === 'secondaryCta') {{
            let btn = root.querySelector('.btn-secondary, .btn-outline, .secondary-cta, .btn-ghost, [data-bind="secondaryCta"]');
            if (btn) {{
              const icon = btn.querySelector('i');
              if (icon) {{
                btn.innerHTML = '';
                btn.appendChild(icon);
                btn.appendChild(document.createTextNode(' ' + value));
              }} else {{
                btn.textContent = value;
              }}
            }}
            return;
          }}
          if (key === 'secondaryCtaLink') {{
            let btn = root.querySelector('.btn-secondary, .btn-outline, .secondary-cta, a[href]');
            if (btn && btn.tagName === 'A') btn.setAttribute('href', value);
            return;
          }}

          // (8) Contact Info (Phone, Email, Address)
          if (key === 'phone') {{
            const phoneEls = document.querySelectorAll('a[href^="tel:"], .phone, .contact-phone, [data-bind="phone"]');
            phoneEls.forEach(function(el) {{
              el.textContent = value;
              if (el.tagName === 'A') el.setAttribute('href', 'tel:' + value);
            }});
            return;
          }}
          if (key === 'email') {{
            const emailEls = document.querySelectorAll('a[href^="mailto:"], .email, .contact-email, [data-bind="email"]');
            emailEls.forEach(function(el) {{
              el.textContent = value;
              if (el.tagName === 'A') el.setAttribute('href', 'mailto:' + value);
            }});
            return;
          }}
          if (key === 'address') {{
            const addrEls = document.querySelectorAll('.address, .contact-address, address, [data-bind="address"]');
            addrEls.forEach(function(el) {{ el.textContent = value; }});
            return;
          }}

          // (9) Navigation Links Array
          if (key === 'navLinks' && Array.isArray(value)) {{
            const navAnchors = document.querySelectorAll('nav a:not(.brand-logo):not(.logo):not(.nav-logo), .nav-links a, .nav-item a, header nav a, header ul li a');
            value.forEach(function(linkText, idx) {{
              if (navAnchors[idx]) navAnchors[idx].textContent = linkText;
            }});
            return;
          }}

          // (10) Cards Array - Full Live Dynamic Creation & Updating
          if (key === 'cards' && Array.isArray(value)) {{
            let cards = [];
            let parentGrid = null;

            if (secEl) {{
              parentGrid = secEl.querySelector(
                '.stats-grid, .features-grid, .cards-grid, .grid, [class*="grid"], [class*="cards"], [class*="list"], [class*="items"], [class*="row"]'
              );
              cards = Array.from(secEl.querySelectorAll(
                '.stat-card, .feature-card, .service-card, .portfolio-card, .card, [class*="card"], [class*="stat"], [class*="feature"], [class*="service"], [class*="portfolio"], [data-card]'
              ));
              if (cards.length === 0 && parentGrid) {{
                cards = Array.from(parentGrid.children);
              }}
            }}
            if (cards.length === 0) {{
              cards = Array.from(root.querySelectorAll(
                '.stat-card, .feature-card, .service-card, .portfolio-card, .card, [class*="card"], [class*="stat"], [class*="feature"], .grid > div, [class*="grid"] > div, [data-card]'
              ));
            }}
            if (!parentGrid && cards.length > 0) {{
              parentGrid = cards[0].parentElement;
            }}

            value.forEach(function(cardItem, idx) {{
              // If user added more cards, clone the last card in the grid so it appears in the website!
              if (!cards[idx] && cards.length > 0 && parentGrid) {{
                const lastCard = cards[cards.length - 1];
                const newCard = lastCard.cloneNode(true);
                newCard.setAttribute('data-studio-dynamic', 'true');
                parentGrid.appendChild(newCard);
                cards.push(newCard);
              }}
              if (cards[idx]) {{
                const cTitle = cards[idx].querySelector('h1, h2, h3, h4, h5, .card-title, .title, strong, b');
                if (cTitle && (typeof cardItem.title !== 'undefined')) cTitle.textContent = cardItem.title;
                if (cTitle && cardItem.titleColor) cTitle.style.color = cardItem.titleColor;
                const cDesc = cards[idx].querySelector('p, .card-desc, .desc, span.desc');
                if (cDesc && (typeof (cardItem.desc || cardItem.description) !== 'undefined')) cDesc.textContent = cardItem.desc || cardItem.description;
                if (cDesc && cardItem.descColor) cDesc.style.color = cardItem.descColor;
                const cTag = cards[idx].querySelector('.card-tag, .tag, .badge, .pill, span.tag');
                if (cTag && (typeof cardItem.tag !== 'undefined')) cTag.textContent = cardItem.tag;
                if (cTag && cardItem.tagColor) cTag.style.color = cardItem.tagColor;
                const cStack = cards[idx].querySelector('.card-stack, .stack, .tech, small');
                if (cStack && (typeof cardItem.stack !== 'undefined')) cStack.textContent = cardItem.stack;
                if (cStack && cardItem.stackColor) cStack.style.color = cardItem.stackColor;
                if (cardItem.boxColor) {{
                  cards[idx].style.backgroundColor = cardItem.boxColor;
                  cards[idx].style.borderColor = cardItem.boxColor + '55';
                }}
                if (cardItem.color) {{
                  cards[idx].style.color = cardItem.color;
                }}
                const targetLink = cardItem.link || cardItem.href || cardItem.url;
                if (typeof targetLink !== 'undefined') {{
                  let cLink = cards[idx].tagName === 'A' ? cards[idx] : cards[idx].querySelector('a');
                  if (cLink) {{
                    cLink.setAttribute('href', targetLink);
                  }} else if (targetLink) {{
                    if (cTitle && cTitle.parentNode && cTitle.parentNode.tagName !== 'A') {{
                      const aWrap = document.createElement('a');
                      aWrap.setAttribute('href', targetLink);
                      aWrap.style.color = 'inherit';
                      aWrap.style.textDecoration = 'none';
                      cTitle.parentNode.insertBefore(aWrap, cTitle);
                      aWrap.appendChild(cTitle);
                    }}
                  }}
                }}
              }}
            }});
            // If cards were deleted in editor, clean up removed elements from DOM
            while (cards.length > value.length && cards.length > 1) {{
              const extraCard = cards.pop();
              if (extraCard && extraCard.parentNode) {{
                extraCard.parentNode.removeChild(extraCard);
              }}
            }}
            return;
          }}

          // (10a) Individual Card Field Updates (e.g. card4_title, card1_desc, card2_link, card1_boxColor)
          const cardKeyMatch = key.match(/^(?:card|exhibit|s|entry)(\\d+)_(title|desc|tag|stack|link|href|url|titlecolor|desccolor|tagcolor|stackcolor|boxcolor|color)$/i);
          if (cardKeyMatch) {{
            const cardIdx = parseInt(cardKeyMatch[1], 10) - 1;
            const field = cardKeyMatch[2].toLowerCase();
            let cards = [];
            let parentGrid = null;
            if (secEl) {{
              parentGrid = secEl.querySelector('.stats-grid, .features-grid, .cards-grid, .grid, [class*="grid"], [class*="cards"], [class*="list"], [class*="items"], [class*="row"]');
              cards = Array.from(secEl.querySelectorAll('.stat-card, .feature-card, .service-card, .portfolio-card, .card, [class*="card"], [class*="stat"], [class*="feature"], [class*="service"], [class*="portfolio"], [data-card]'));
              if (cards.length === 0 && parentGrid) cards = Array.from(parentGrid.children);
            }}
            if (cards.length === 0) {{
              cards = Array.from(root.querySelectorAll('.stat-card, .feature-card, .service-card, .portfolio-card, .card, [class*="card"], [class*="stat"], [class*="feature"], .grid > div, [class*="grid"] > div, [data-card]'));
            }}
            if (!parentGrid && cards.length > 0) parentGrid = cards[0].parentElement;
            if (!cards[cardIdx] && cards.length > 0 && parentGrid) {{
              const lastCard = cards[cards.length - 1];
              const newCard = lastCard.cloneNode(true);
              newCard.setAttribute('data-studio-dynamic', 'true');
              parentGrid.appendChild(newCard);
              cards.push(newCard);
            }}
            if (cards[cardIdx]) {{
              if (field === 'title') {{
                const cTitle = cards[cardIdx].querySelector('h1, h2, h3, h4, h5, .card-title, .title, strong, b');
                if (cTitle) cTitle.textContent = value;
              }} else if (field === 'titlecolor') {{
                const cTitle = cards[cardIdx].querySelector('h1, h2, h3, h4, h5, .card-title, .title, strong, b');
                if (cTitle) cTitle.style.color = value || '';
              }} else if (field === 'desc') {{
                const cDesc = cards[cardIdx].querySelector('p, .card-desc, .desc, span.desc');
                if (cDesc) cDesc.textContent = value;
              }} else if (field === 'desccolor') {{
                const cDesc = cards[cardIdx].querySelector('p, .card-desc, .desc, span.desc');
                if (cDesc) cDesc.style.color = value || '';
              }} else if (field === 'tag') {{
                const cTag = cards[cardIdx].querySelector('.card-tag, .tag, .badge, .pill, span.tag');
                if (cTag) cTag.textContent = value;
              }} else if (field === 'tagcolor') {{
                const cTag = cards[cardIdx].querySelector('.card-tag, .tag, .badge, .pill, span.tag');
                if (cTag) cTag.style.color = value || '';
              }} else if (field === 'stack') {{
                const cStack = cards[cardIdx].querySelector('.card-stack, .stack, .tech, small');
                if (cStack) cStack.textContent = value;
              }} else if (field === 'stackcolor') {{
                const cStack = cards[cardIdx].querySelector('.card-stack, .stack, .tech, small');
                if (cStack) cStack.style.color = value || '';
              }} else if (field === 'boxcolor') {{
                cards[cardIdx].style.backgroundColor = value || '';
                if (value) cards[cardIdx].style.borderColor = value + '55';
              }} else if (field === 'color') {{
                cards[cardIdx].style.color = value || '';
              }} else if (field === 'link' || field === 'href' || field === 'url') {{
                let cLink = cards[cardIdx].tagName === 'A' ? cards[cardIdx] : cards[cardIdx].querySelector('a');
                if (cLink) {{
                  cLink.setAttribute('href', value);
                }} else if (value) {{
                  const cTitle = cards[cardIdx].querySelector('h1, h2, h3, h4, h5, .card-title, .title, strong, b');
                  if (cTitle && cTitle.parentNode && cTitle.parentNode.tagName !== 'A') {{
                    const aWrap = document.createElement('a');
                    aWrap.setAttribute('href', value);
                    aWrap.style.color = 'inherit';
                    aWrap.style.textDecoration = 'none';
                    cTitle.parentNode.insertBefore(aWrap, cTitle);
                    aWrap.appendChild(cTitle);
                  }}
                }}
              }}
            }}
            return;
          }}

          // (10b) TextItems Array - Full Live Dynamic Creation & Updating
          if (key === 'textItems' && Array.isArray(value)) {{
            value.forEach(function(ti, idx) {{
              const newText = (ti.text || '').toString();
              const origText = (ti.originalText || '').toString().trim();
              if (!newText && !ti.color) return;

              // 1. Try finding and replacing existing text in DOM
              if (origText && origText.length >= 2) {{
                const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
                let node;
                let found = false;
                while ((node = walker.nextNode())) {{
                  if (node.nodeValue && node.nodeValue.includes(origText)) {{
                    if (newText) node.nodeValue = node.nodeValue.replace(origText, newText);
                    if (ti.color && node.parentElement) node.parentElement.style.color = ti.color;
                    ti.originalText = newText || origText;
                    found = true;
                    break;
                  }}
                }}
                if (found) return;
              }}

              // 2. Dynamic DOM Element insertion for newly added content items!
              const dynId = 'studio-dyn-text-' + (ti.id || idx);
              let existingEl = root.querySelector('#' + dynId);
              if (existingEl) {{
                if (newText) existingEl.textContent = newText;
                if (ti.color) existingEl.style.color = ti.color;
              }} else if (ti.isNew || !origText) {{
                const candidateSiblings = Array.from(root.querySelectorAll('p, div.grid > div, [class*="card"], li, h4, span'));
                const lastSibling = candidateSiblings.length > 0 ? candidateSiblings[candidateSiblings.length - 1] : null;
                if (lastSibling && lastSibling.parentElement) {{
                  const newEl = lastSibling.cloneNode(true);
                  newEl.id = dynId;
                  newEl.setAttribute('data-studio-dynamic', 'true');
                  const targetChild = newEl.querySelector('p, h4, span') || newEl;
                  if (newText) targetChild.textContent = newText;
                  if (ti.color) targetChild.style.color = ti.color;
                  lastSibling.parentElement.appendChild(newEl);
                }} else {{
                  const newEl = document.createElement('p');
                  newEl.id = dynId;
                  newEl.className = 'studio-added-content leading-relaxed text-foreground mt-2';
                  if (newText) newEl.textContent = newText;
                  if (ti.color) newEl.style.color = ti.color;
                  (secEl || document.body).appendChild(newEl);
                }}
              }}
            }});
            return;
          }}

          // (11) Smart Universal Text Match & Replace (works for textItems, bio, stats, anything typed or pasted)
          if (typeof value === 'string' && value.trim()) {{
            const targetToFind = originalText;
            if (targetToFind && targetToFind.length >= 2) {{
              const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
              let node;
              while ((node = walker.nextNode())) {{
                if (node.nodeValue && node.nodeValue.includes(targetToFind)) {{
                  node.nodeValue = node.nodeValue.replace(targetToFind, value);
                  return;
                }}
              }}
            }}
          }}
        }}

        window.addEventListener('message', function(evt) {{
          if (evt.data && evt.data.type === 'UPDATE_THEME_COLOR' && evt.data.color) {{
            applyLiveThemeColor(evt.data.color);
          }}
          if (evt.data && evt.data.type === 'UPDATE_CONTENT') {{
            applyLiveContent(evt.data);
          }}
          if (evt.data && evt.data.type === 'SCROLL_TO_SECTION' && evt.data.sectionId) {{
            const sId = evt.data.sectionId;
            const targetEl = document.getElementById(sId) || document.querySelector('.' + sId) || document.querySelector('[data-section="' + sId + '"]') || (sId === 'navbar' ? document.querySelector('nav, header') : null);
            if (targetEl) {{
              targetEl.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
          }}
        }});
        // 3. AI Site Studio Demo Guardian — auto-wipe data on tab close or navigation away
        (function() {{
          const params = new URLSearchParams(window.location.search);
          const sToken = params.get('session_token') || '';
          const tId = '{template_id}';
          const exitEndpoint = '/api/v1/preview/demo/session/end?session_token=' + encodeURIComponent(sToken) + '&template_id=' + encodeURIComponent(tId);

          function sendExitBeacon(why) {{
            try {{
              const fullUrl = exitEndpoint + '&reason=' + encodeURIComponent(why || 'tab_closed');
              if (navigator.sendBeacon) {{
                navigator.sendBeacon(fullUrl, '');
              }} else {{
                fetch(fullUrl, {{ method: 'POST', keepalive: true }});
              }}
            }} catch(e) {{}}
          }}

          window.addEventListener('beforeunload', function() {{ sendExitBeacon('tab_closed'); }});
          window.addEventListener('pagehide', function() {{ sendExitBeacon('back_nav'); }});
          window.addEventListener('message', function(evt) {{
            if (evt.data && evt.data.type === 'PURGE_AND_EXIT') {{
              sendExitBeacon(evt.data.reason || 'manual');
            }}
          }});
        }})();

        // 2. Intercept click events on links to keep them inside the live preview sandbox
        document.addEventListener('click', function(e) {{
          const link = e.target.closest('a');
          if (link) {{
            const rawHref = link.getAttribute('href');
            if (!rawHref) return;
            if (rawHref.includes('/marketplace') || link.closest('.preview-purchase-footer-banner')) {{
              e.preventDefault();
              window.top.location.href = "{settings.FRONTEND_URL}/marketplace/{template.slug if template and template.slug else template_id}";
              return;
            }}
            if (rawHref.startsWith('#')) {{
              e.preventDefault();
              window.location.hash = rawHref;
              return;
            }}
            if (rawHref.startsWith('javascript:')) {{
              return;
            }}
            // Ensure relative page links (e.g. "about.html", "contact.html", "./menu.html") remain inside the sandbox route
            if (link.href) {{
              try {{
                const url = new URL(link.href, window.location.href);
                if (url.origin === window.location.origin) {{
                  let path = url.pathname;
                  if (!path.startsWith(basePrefix)) {{
                    if (path.startsWith('/')) {{
                      path = path.slice(1);
                    }}
                    link.href = window.location.origin + basePrefix + '/' + path + url.search + url.hash;
                  }}
                }}
              }} catch (err) {{}}
            }}
          }}
        }}, true);
      }})();
    </script>"""
                
                if "<head>" in html_content:
                    html_content = html_content.replace("<head>", f"<head>\n  {sandbox_script}", 1)
                elif "<html>" in html_content:
                    html_content = html_content.replace("<html>", f"<html>\n  {sandbox_script}", 1)
                else:
                    html_content = sandbox_script + "\n" + html_content

                # Make generated hamburger controls usable in demos even when a
                # model emitted visual markup without attaching a click handler.
                mobile_nav_fallback = r'''<style id="studio-mobile-nav-fallback-style">
@media (max-width: 768px) {
  .studio-preview-forced-open { position: fixed !important; z-index: 99998 !important; top: 64px !important; right: 12px !important; left: 12px !important; width: auto !important; max-height: calc(100dvh - 80px) !important; overflow-y: auto !important; display: flex !important; flex-direction: column !important; gap: 8px !important; padding: 16px !important; border: 1px solid rgba(148,163,184,.32) !important; border-radius: 16px !important; background: #0c1020 !important; color: #f8fafc !important; box-shadow: 0 18px 60px rgba(0,0,0,.55) !important; visibility: visible !important; opacity: 1 !important; transform: none !important; }
  .studio-preview-forced-open a { display: flex !important; align-items: center !important; min-height: 44px !important; color: inherit !important; }
}
</style><script id="studio-mobile-nav-fallback">
(() => {
  if (window.__studioMobileNavFallback) return;
  window.__studioMobileNavFallback = true;
  const isMobile = () => window.matchMedia('(max-width: 768px)').matches;
  const findMenu = (button) => {
    const id = button.getAttribute('aria-controls');
    if (id) { const controlled = document.getElementById(id); if (controlled) return controlled; }
    const selector = button.getAttribute('data-target') || button.getAttribute('data-mobile-menu');
    if (selector) { try { const target = document.querySelector(selector); if (target) return target; } catch (_) {} }
    const scope = button.closest('header, [role="banner"], .navbar, .site-header') || document;
    const namedMenu = scope.querySelector('.mobile-drawer, .mobile-nav, .mobile-menu, [data-drawer], [id*="mobile-menu"], nav');
    if (namedMenu) return namedMenu;
    return Array.from(scope.children).find((node) => node !== button && node.querySelector?.('a[href]')) || null;
  };
  const setOpen = (button, menu, open) => {
    if (!menu) return;
    menu.classList.toggle('studio-preview-forced-open', open);
    if (open) { menu.removeAttribute('hidden'); menu.setAttribute('aria-hidden', 'false'); }
    else if (menu.classList.contains('studio-preview-forced-open')) menu.setAttribute('aria-hidden', 'true');
    if (button) button.setAttribute('aria-expanded', String(open));
  };
  document.addEventListener('click', (event) => {
    if (!isMobile()) return;
    const button = event.target.closest('button, [role="button"], [data-mobile-toggle]');
    const header = button?.closest('header, [role="banner"], .navbar, .site-header');
    const box = button?.getBoundingClientRect();
    const compactHeaderButton = Boolean(header && box && box.width <= 64 && box.height <= 64 && (button.querySelector('svg') || button.textContent.trim().length <= 3));
    if (button && (button.matches('[data-mobile-toggle], .mobile-toggle, .hamburger, .menu-btn, .menu-toggle, .mobile-menu-button, button[aria-label*="menu" i]') || button.hasAttribute('aria-controls') || compactHeaderButton)) {
      const menu = findMenu(button);
      if (!menu) return;
      const expandedBeforeClick = button.getAttribute('aria-expanded');
      window.setTimeout(() => {
        if (button.getAttribute('aria-expanded') !== expandedBeforeClick) return;
        const forcedOpen = menu.classList.contains('studio-preview-forced-open');
        const wasOpen = expandedBeforeClick === 'true' || forcedOpen;
        setOpen(button, menu, !wasOpen);
      }, 0);
      return;
    }
    const openMenu = event.target.closest('.studio-preview-forced-open');
    if (openMenu && event.target.closest('a')) {
      openMenu.classList.remove('studio-preview-forced-open');
      openMenu.setAttribute('aria-hidden', 'true');
      document.querySelectorAll('[aria-expanded="true"]').forEach((item) => item.setAttribute('aria-expanded', 'false'));
    }
  }, true);
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('.studio-preview-forced-open').forEach((menu) => {
      menu.classList.remove('studio-preview-forced-open'); menu.setAttribute('aria-hidden', 'true');
    });
    document.querySelectorAll('[aria-expanded="true"]').forEach((button) => button.setAttribute('aria-expanded', 'false'));
  });
})();
</script>'''
                if "</body>" in html_content.lower():
                    body_end = html_content.lower().rfind("</body>")
                    html_content = html_content[:body_end] + mobile_nav_fallback + "\n" + html_content[body_end:]
                else:
                    html_content += mobile_nav_fallback
    
                # Inject Watermarks & Copy/Inspect/Print Restrictions before </body>
                target_slug = template.slug if (template and template.slug) else str(template_id)
                purchase_url = f"{settings.FRONTEND_URL}/marketplace/{target_slug}?buy=1"

                watermark_payload = """
    <!-- Injected Watermark Grid Overlay -->
    <div class="preview-watermark-grid"></div>
    
    <style>
      /* Disable text selection across all elements */
      * {
        user-select: none !important;
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
      }
    
      /* Watermark grid covering full page with pointer-events disabled */
      .preview-watermark-grid {
        position: fixed !important;
        inset: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        pointer-events: none !important;
        z-index: 999999 !important;
        opacity: 0.65 !important;
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'><text x='20' y='150' fill='rgba(128, 128, 128, 0.16)' font-size='13' font-weight='800' font-family='sans-serif' transform='rotate(-30 20 150)'>SITE STUDIO PREVIEW</text></svg>") !important;
        background-repeat: repeat !important;
      }
    
      /* Bottom floating warning banner */
      .preview-purchase-footer-banner {
        position: fixed !important;
        bottom: 1.5rem !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        background: rgba(15, 23, 42, 0.96) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        color: #ffffff !important;
        padding: 0.625rem 1.25rem !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        border-radius: 9999px !important;
        display: flex !important;
        align-items: center !important;
        gap: 1rem !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4) !important;
        z-index: 999998 !important;
        white-space: nowrap !important;
        font-family: system-ui, -apple-system, sans-serif !important;
      }
    
      .preview-purchase-footer-banner a {
        color: #38bdf8 !important;
        text-decoration: none !important;
        font-weight: 800 !important;
        border-left: 1px solid rgba(255, 255, 255, 0.2) !important;
        padding-left: 1rem !important;
        transition: color 0.2s ease !important;
      }
    
      .preview-purchase-footer-banner a:hover {
        color: #0ea5e9 !important;
      }
    
      /* Block PDF printing */
      @media print {
        body {
          display: none !important;
        }
      }
    </style>
    
    <script>
      (function() {
        // 1. Disable Right-Click Context Menu
        document.addEventListener('contextmenu', function(e) {
          e.preventDefault();
        }, true);
    
        // 2. Intercept Inspector, View-Source, Copy and Save keys
        document.addEventListener('keydown', function(e) {
          if (
            e.key === 'F12' ||
            (e.ctrlKey && e.shiftKey && e.key === 'I') ||
            (e.ctrlKey && e.shiftKey && e.key === 'C') ||
            (e.ctrlKey && e.shiftKey && e.key === 'J') ||
            (e.ctrlKey && e.key === 'u') ||
            (e.ctrlKey && e.key === 'c') ||
            (e.ctrlKey && e.key === 's')
          ) {
            e.preventDefault();
            e.stopPropagation();
            return false;
          }
        }, true);
      })();
    </script>
    """.replace("__PURCHASE_URL__", purchase_url)

                # Inject watermark overlay on all template previews unless explicitly marked clean
                is_clean = request.query_params.get("clean") == "1"

                if not is_clean:
                    if "</body>" in html_content:
                        html_content = html_content.replace("</body>", f"{watermark_payload}\n</body>", 1)
                    else:
                        html_content = html_content + "\n" + watermark_payload

                # Ensure all /marketplace links point to the React frontend application
                html_content = html_content.replace('href="/marketplace"', f'href="{purchase_url}"')
                html_content = html_content.replace("href='/marketplace'", f"href='{purchase_url}'")
    
                content = html_content.encode("utf-8")
            except Exception:
                pass
        from app.services.security_scanner import security_scanner
        return Response(content=content, media_type=mime_type, headers=security_scanner.get_secure_preview_headers())
    except Exception as e:
        logger.exception(f"🚨 Preview generation error for template {template_id}: {e}")
        return await serve_fallback(str(e))


class ManualEditRequest(BaseModel):
    business_name: str
    about: str
    primary_color: str
    secondary_color: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    page_edits: Optional[dict] = None
    use_ai: bool = False


class AIEditRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


@router.post("/live/{template_id}/ai-debug")
async def ai_debug_template_code(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    On-demand AI Debugger endpoint:
    Scans the template codebase, detects any broken JSX/TSX/HTML or syntax defects,
    invokes Gemini AI Debugger to fix them, rebuilds the project, and persists the fixes.
    """
    import shutil
    import tempfile
    import zipfile
    import io
    from sqlalchemy import select
    from app.services.debugger_service import ai_debugger
    from app.models.template import Template
    from app.models.stored_file import StoredFile

    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    
    # 1. Fetch template from DB
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.status != TemplateStatus.DRAFT or template.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner of a draft can edit its source files.")
    from app.core.request_limits import enforce_user_limit
    await enforce_user_limit(str(current_user.id), "template-ai-debug")

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP archive")

    match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
    stored_file = None
    if match:
        try:
            file_id = uuid.UUID(match.group(1))
            sf_res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
            stored_file = sf_res.scalar_one_or_none()
        except Exception:
            pass

    if not stored_file:
        raise HTTPException(status_code=404, detail="Source archive data not found")

    from app.core.storage import storage
    stored_file_data = await storage.get_file(db, file_id)
    if not stored_file_data:
        raise HTTPException(status_code=404, detail="Source archive data not found")
    zip_bytes = stored_file_data[0]

    # 2. Extract to preview_dir
    os.makedirs(preview_dir, exist_ok=True)
    from app.services.security_scanner import security_scanner
    security_scanner.sanitize_extract_zip(zip_bytes, Path(preview_dir))

    # 3. Locate package.json and scan all source files
    fixed_files_count = 0
    repaired_map = {}

    for root, _, files in os.walk(preview_dir):
        if any(d in root.replace("\\", "/").split("/") for d in ["dist", "node_modules", "build", ".output"]):
            continue
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in [".jsx", ".tsx", ".js", ".ts", ".html"]:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        code = f.read()

                    # Sanitize heuristics first
                    healed = ai_debugger.sanitize_code_heuristics(code, ext)
                    
                    # If suspect syntax or defects detected, invoke Gemini AI Debugger
                    if ");</" in code or ";</" in code or "export default" not in code or code.count("{") != code.count("}") or code.count("<div") != code.count("</div"):
                        rel_path = os.path.relpath(fpath, preview_dir)
                        healed = await ai_debugger.debug_code_with_ai(
                            code=code,
                            filename=rel_path,
                            error_message="Fix unbalanced tags, stray semicolons, missing brackets, and broken exports."
                        )

                    if healed and healed != code:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(healed)
                        rel_p = os.path.relpath(fpath, preview_dir)
                        repaired_map[rel_p] = healed
                        fixed_files_count += 1
                except Exception as e_file:
                    logger.warning(f"AI Debugger skipped {fname}: {e_file}")

    # 4. If files were fixed, re-package the ZIP and save to DB
    if repaired_map and stored_file:
        in_mem = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zin:
            with zipfile.ZipFile(in_mem, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    item_data = zin.read(item.filename)
                    norm_name = os.path.normpath(item.filename).replace("\\", "/")
                    for rep_rel, rep_content in repaired_map.items():
                        norm_rep = os.path.normpath(rep_rel).replace("\\", "/")
                        if norm_name.endswith(norm_rep) or norm_rep.endswith(norm_name):
                            item_data = rep_content.encode("utf-8")
                            break
                    zout.writestr(item, item_data)
        from app.core.storage import storage
        replacement_url = await storage.upload_file(
            db=db,
            file_content=in_mem.getvalue(),
            folder="templates/debugged",
            original_filename=stored_file.original_filename or "template.zip",
            content_type="application/zip",
        )
        template.download_assets = {**download_assets, "zip": replacement_url}
        db.add(template)
        await db.commit()

    # 5. Clear compiled dist/build directories in preview_dir to trigger fresh build
    for b_dir in ["dist", "out", "build", ".output"]:
        for root, dirs, _ in os.walk(preview_dir):
            if b_dir in dirs:
                shutil.rmtree(os.path.join(root, b_dir), ignore_errors=True)

    return {
        "status": "success",
        "message": f"AI Debugger analyzed project and successfully fixed {fixed_files_count} file(s).",
        "fixed_files": list(repaired_map.keys()),
        "fixed_count": fixed_files_count
    }


@router.get("/thumbnail/{template_id}.svg", include_in_schema=False)
async def get_dynamic_thumbnail(template_id: str, db: AsyncSession = Depends(get_db)):
    """Dynamically serves or generates on-demand SVG thumbnail snapshot for any template or draft."""
    from fastapi.responses import FileResponse, Response
    from app.services.screenshot_service import screenshot_service, _THUMBNAILS_DIR
    from app.core.local_project_manager import local_project_manager

    # 1. If local project exists, generate snapshot using real photo, real skills & real content
    clean_id = str(template_id).strip()
    if local_project_manager.get_local_project_dir(clean_id, version="latest"):
        svg = screenshot_service.generate_for_project(clean_id)
        return Response(content=svg, media_type="image/svg+xml")

    # 2. Check cached thumbnail file on disk
    thumb_path = Path(_THUMBNAILS_DIR) / f"{clean_id}.svg"
    if thumb_path.exists():
        return FileResponse(str(thumb_path), media_type="image/svg+xml")

    # If not on disk, lookup template and dynamically generate
    try:
        t_res = await db.execute(select(Template).where((Template.id == template_id) | (Template.slug == template_id)))
        tmpl = t_res.scalar_one_or_none()
    except Exception:
        tmpl = None

    title = tmpl.title if tmpl else "Modern Website Template"
    fw = str(tmpl.framework) if tmpl and tmpl.framework else "HTML"
    cat = "Modern Business"
    if tmpl and hasattr(tmpl, "category") and tmpl.category:
        cat = tmpl.category.name if hasattr(tmpl.category, "name") else str(tmpl.category)
    
    svg = screenshot_service.generate_svg_snapshot(title=title, framework=fw, category=cat)
    try:
        with open(thumb_path, "w", encoding="utf-8") as f:
            f.write(svg)
    except Exception:
        pass
    return Response(content=svg, media_type="image/svg+xml")




