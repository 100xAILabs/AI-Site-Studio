"""
Templates routes — public browsing and admin CRUD.
"""

import uuid
import os
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Query, HTTPException, status, File, UploadFile, Response, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel
from app.core.database import get_db
from app.core.dependencies import get_current_user_optional, require_admin, require_seller_or_admin, get_current_user
from app.models.user import User, UserRole
from app.services.template_service import TemplateService
from app.repositories.template_repo import TemplateRepository
from app.services.project_analyzer import project_analyzer
from app.core.storage import storage
from app.schemas.template import (
    TemplateCreate, TemplateUpdate, TemplateResponse,
    TemplateListResponse, TemplateFilterParams, TemplateCardResponse,
)
from app.models.template import TemplateFramework, TemplateLicense, TemplateStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.core.config import settings
from app.core.security import generate_file_signature
from app.core.redis import CacheKeys, cache_get, cache_set, cache_delete, cache_delete_pattern
from app.services.security_scanner import security_scanner
from decimal import Decimal
from urllib.parse import urlparse
from datetime import datetime, timezone

router = APIRouter()


import httpx


async def _read_upload_limited(file: UploadFile) -> bytes:
    """Read an upload with a strict size cap instead of buffering unbounded input."""
    max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )

    content = bytearray()
    try:
        while chunk := await file.read(1024 * 1024):
            content.extend(chunk)
            if len(content) > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB}MB.",
                )
    finally:
        await file.close()
    return bytes(content)

class GitAnalyzeRequest(BaseModel):
    git_url: str
    token: Optional[str] = None


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    # Search
    q: Optional[str] = Query(None, description="Text search query"),
    # Category & Sub-category
    category: Optional[str] = Query(None, description="Category slug or name"),
    sub_category: Optional[str] = Query(None, description="Subcategory slug or name"),
    # Price
    min_price: Optional[Decimal] = Query(None, ge=0),
    max_price: Optional[Decimal] = Query(None, ge=0),
    # Rating
    rating: Optional[float] = Query(None, ge=1, le=5),
    # Boolean flags
    is_free: Optional[bool] = Query(None),
    is_on_sale: Optional[bool] = Query(None),
    has_dark_mode: Optional[bool] = Query(None),
    is_ai_ready: Optional[bool] = Query(None),
    is_featured: Optional[bool] = Query(None),
    # Taxonomy
    framework: Optional[TemplateFramework] = Query(None),
    industry: Optional[str] = Query(None),
    color_scheme: Optional[str] = Query(None),
    license_type: Optional[TemplateLicense] = Query(None),
    # Theme Forest specific filters
    sales: Optional[str] = Query(None, description="Sales count tier filter"),
    compatibility: Optional[str] = Query(None, description="Compatibility filter"),
    language: Optional[str] = Query(None, description="Programming language filter"),
    technology: Optional[str] = Query(None, description="Technology/Framework/Library filter"),
    date_added: Optional[str] = Query(None, description="Date added range filter"),
    # Sorting & Pagination
    sort: str = Query("newest", description="Sort field"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    semantic: bool = Query(False, description="Use AI semantic search"),
    developer: Optional[str] = Query(None, description="Developer/seller name"),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Browse marketplace templates with filtering, sorting, and pagination.
    All filter params are optional and combinable.
    """
    import json
    import hashlib

    filters = TemplateFilterParams(
        q=q, category=category, sub_category=sub_category, min_price=min_price, max_price=max_price,
        rating=rating, is_free=is_free, is_on_sale=is_on_sale,
        has_dark_mode=has_dark_mode, is_ai_ready=is_ai_ready, is_featured=is_featured,
        framework=framework, industry=industry, color_scheme=color_scheme,
        license_type=license_type, sales=sales, compatibility=compatibility, language=language,
        technology=technology, date_added=date_added,
        sort=sort, page=page, page_size=page_size, semantic=semantic,
        developer=developer,
    )

    # Compute deterministic cache key for catalog query
    filter_dict = {k: v for k, v in filters.model_dump(exclude_none=True).items() if k != "semantic"}
    filter_str = json.dumps(filter_dict, sort_keys=True, default=str)
    cache_key = f"templates:catalog:{hashlib.md5(filter_str.encode('utf-8')).hexdigest()}"

    service = TemplateService(db)

    # 1. Check Redis cache for public catalog (when not semantic search)
    if not filters.semantic:
        cached_catalog = await cache_get(cache_key)
        if cached_catalog is not None:
            if settings.TEMPLATE_DOWNLOADS_FREE:
                cached_catalog = {
                    **cached_catalog,
                    "items": [
                        {**item, "price": 0, "original_price": None, "is_free": True, "is_on_sale": False}
                        for item in cached_catalog.get("items", [])
                    ],
                }
            if response:
                response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
            if not current_user:
                return TemplateListResponse.model_validate(cached_catalog)
            # Authenticated user: enrich cached catalog with favorites & wishlist in parallel
            return await service.enrich_with_user_interactions(cached_catalog, current_user)

    result = await service.list_templates(filters, current_user)

    # 2. Store in Redis cache for 3 minutes (180s)
    if result and not filters.semantic:
        raw_cards = []
        for c in result.items:
            dump = c.model_dump(mode="json")
            dump["is_favorited"] = None
            dump["is_wishlisted"] = None
            raw_cards.append(dump)
        to_cache = {
            "items": raw_cards,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "total_pages": result.total_pages,
        }
        await cache_set(cache_key, to_cache, ttl=180)

    if response:
        response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return result


@router.get("/featured", response_model=list[TemplateCardResponse])
async def get_featured_templates(
    limit: int = Query(8, ge=1, le=20),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
):
    """Return featured templates for the landing page (cached in Redis)."""
    cache_key = CacheKeys.featured(limit)
    cached = await cache_get(cache_key)
    if cached is not None:
        if settings.TEMPLATE_DOWNLOADS_FREE:
            cached = [
                {**item, "price": 0, "original_price": None, "is_free": True, "is_on_sale": False}
                for item in cached
            ]
        if response:
            response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
        return [TemplateCardResponse.model_validate(c) for c in cached]

    service = TemplateService(db)
    result = await service.get_featured_templates(limit)
    if result:
        await cache_set(
            cache_key,
            [c.model_dump(mode="json") for c in result],
            ttl=CacheKeys.CACHE_TTL_MEDIUM,
        )
    if response:
        response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
    return result


@router.get("/my-templates", response_model=list[TemplateResponse])
async def list_my_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get account-owned template records, including private AI Studio Project drafts.
    The dashboard separates published marketplace listings from draft projects by status.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.template import Template
    from app.models.category import Category

    query = (
        select(Template)
        .options(selectinload(Template.category).selectinload(Category.children))
        .where(Template.seller_id == current_user.id)
        .order_by(Template.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/git-repos")
async def list_git_repos(
    username: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Fetch repository list for a GitHub user (using username or token, or stored user token).
    """
    auth_token = token
    if not auth_token and current_user.github_access_token:
        auth_token = current_user.github_access_token

    if not username and not auth_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either GitHub username, Personal Access Token, or connected GitHub account is required"
        )
    
    headers = {"Accept": "application/vnd.github+json"}
    if auth_token:
        headers["Authorization"] = f"token {auth_token}"
        url = "https://api.github.com/user/repos?per_page=100&sort=updated"
    else:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code != 200:
                detail = "Failed to fetch repositories from GitHub"
                try:
                    detail = response.json().get("message", detail)
                except Exception:
                    pass
                raise HTTPException(status_code=response.status_code, detail=detail)
            
            repos = response.json()
            return [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "clone_url": r.get("clone_url"),
                    "description": r.get("description"),
                    "private": r.get("private"),
                    "language": r.get("language"),
                    "stargazers_count": r.get("stargazers_count", 0),
                    "updated_at": r.get("updated_at"),
                }
                for r in repos if isinstance(r, dict)
            ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting to GitHub: {str(e)}"
        )


@router.get("/{slug}", response_model=TemplateResponse)
async def get_template(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get full template details by slug or ID with Redis multi-tier caching."""
    cache_key = CacheKeys.template(slug)
    cached = await cache_get(cache_key)
    if cached is not None and str(cached.get("status", "")).lower() != TemplateStatus.PUBLISHED.value:
        # Never let a prior cache entry bypass owner checks for a private AI Studio draft.
        cached = None
    if cached is not None:
        try:
            if settings.TEMPLATE_DOWNLOADS_FREE:
                cached = {**cached, "price": 0, "original_price": None, "is_free": True, "is_on_sale": False}
            if current_user:
                template_id = uuid.UUID(str(cached["id"]))
                service = TemplateService(db)
                # Count unique account view if new
                await service.record_unique_account_view(template_id, current_user.id)
                # Fetch user-specific favorite and wishlist flags
                is_fav = await service.favorites.is_favorited(current_user.id, template_id)
                is_wish = await service.wishlist.is_wishlisted(current_user.id, template_id)
                resp_dict = dict(cached)
                resp_dict["is_favorited"] = is_fav
                resp_dict["is_wishlisted"] = is_wish
                return TemplateResponse.model_validate(resp_dict)
            return TemplateResponse.model_validate(cached)
        except Exception as e_cache:
            logger.warning(f"Error serving cached template for '{slug}': {e_cache}")

    service = TemplateService(db)
    result = await service.get_template(slug, current_user)
    if result:
        result_status = getattr(result.status, "value", str(result.status)).lower()
        if result_status == TemplateStatus.PUBLISHED.value:
            # Shared cache is reserved for marketplace listings, never private projects.
            base_dump = result.model_dump(mode="json")
            base_dump["is_favorited"] = None
            base_dump["is_wishlisted"] = None

            await cache_set(cache_key, base_dump, ttl=CacheKeys.CACHE_TTL_MEDIUM)
            if result.slug and result.slug != slug:
                await cache_set(CacheKeys.template(result.slug), base_dump, ttl=CacheKeys.CACHE_TTL_MEDIUM)
            if str(result.id) != slug:
                await cache_set(CacheKeys.template(str(result.id)), base_dump, ttl=CacheKeys.CACHE_TTL_MEDIUM)
            
    return result


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update template details by ID (price, description, title, framework, etc.)."""
    repo = TemplateRepository(db)
    template = await repo.get_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if template.seller_id != current_user.id and user_role.lower() not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this template"
        )

    update_dict = data.model_dump(exclude_unset=True)
    if "price" in update_dict and update_dict["price"] is not None:
        update_dict["price"] = Decimal(str(update_dict["price"]))
        update_dict["is_free"] = update_dict["price"] == 0

    updated = await repo.update(template, update_dict)
    await db.commit()

    # Invalidate template details and featured caches
    if hasattr(template, "slug") and template.slug:
        await cache_delete(CacheKeys.template(template.slug))
    await cache_delete(CacheKeys.template(str(template.id)))
    await cache_delete_pattern("templates:featured:*")

    return updated


@router.post("/analyze-zip")
async def analyze_project_zip(
    file: UploadFile = File(...),
    _user: User = Depends(require_seller_or_admin),
):
    """
    Upload a project ZIP file or single HTML file, extract/analyze the code and assets,
    and generate visual/SEO/code suggestions and meta parameters via Gemini.
    """
    allowed_exts = (".zip", ".html", ".htm", ".tar", ".gz")
    if not file.filename.lower().endswith(allowed_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported upload formats: ZIP archives (.zip) or HTML documents (.html, .htm)"
        )
    content = await _read_upload_limited(file)
    return await project_analyzer.analyze_zip(content, file.filename)


@router.post("/analyze-git")
async def analyze_git_repo(
    request_data: GitAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Provide a Git repository URL, clone it, package it into a clean ZIP,
    analyze the code and assets, save the clean ZIP to database storage,
    and return the analysis results along with the public file URL.
    """
    git_url = request_data.git_url.strip()
    from app.core.request_limits import enforce_user_limit
    await enforce_user_limit(str(current_user.id), "git-import", limit=5, window_seconds=3600)
    token = request_data.token.strip() if request_data.token else None
    if not token and current_user.github_access_token:
        token = current_user.github_access_token

    parsed_git_url = urlparse(git_url)
    allowed_git_hosts = {"github.com", "gitlab.com", "bitbucket.org"}
    if (parsed_git_url.scheme != "https" or parsed_git_url.hostname not in allowed_git_hosts
            or parsed_git_url.username or parsed_git_url.password or parsed_git_url.port not in (None, 443)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only HTTPS repositories hosted on GitHub, GitLab, or Bitbucket are supported."
        )

    # Inject personal access token into HTTPS URL for private repositories
    if token and git_url.startswith("https://github.com/"):
        git_url = git_url.replace("https://github.com/", f"https://{token}@github.com/")

    try:
        result = await project_analyzer.analyze_git_repo(git_url)
        zip_bytes = result.pop("_zip_bytes")
        filename = result.pop("_filename")

        from app.core.storage import storage
        stored_zip_url = await storage.upload_file(
            db=db,
            file_content=zip_bytes,
            folder="uploads",
            original_filename=filename,
            content_type="application/zip",
        )

        result["stored_zip_url"] = stored_zip_url
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to import and analyze the repository. Check that it is accessible and try again."
        )


@router.post("/audit")
async def audit_template_zip(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Run pre-upload Security & Quality Audit on a template ZIP archive.
    Returns 0-100 Overall Score, malware check, page completeness, and relative link health.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a ZIP archive (.zip)",
        )

    content = await _read_upload_limited(file)
    from app.services.security_scanner import security_scanner
    report = security_scanner.audit_zip_template(content, file.filename)
    return report


# ── Admin Endpoints ───────────────────────────────────────────────────────────

@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """Create a new template and permanently link it to the uploading seller's account."""
    data.status = TemplateStatus.PUBLISHED
    service = TemplateService(db)
    return await service.create_template(data, seller_id=current_user.id)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str | uuid.UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """Update an existing template."""
    service = TemplateService(db)
    return await service.update_template(template_id, data, current_user)


@router.post("/{template_id}/reupload", response_model=TemplateResponse)
async def reupload_template_zip(
    template_id: str | uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Re-upload and replace a template's source ZIP file.
    Automatically purges dangerous executables, updates download_assets,
    clears live preview disk cache, and updates updated_at timestamp.
    """
    valid_exts = (".zip", ".html", ".htm", ".tar", ".gz")
    if not any(file.filename.lower().endswith(ext) for ext in valid_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a ZIP archive (.zip) or HTML file (.html, .htm)",
        )

    t_uuid = uuid.UUID(str(template_id))
    from app.repositories.template_repo import TemplateRepository
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(t_uuid)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if str(role_val).lower() not in ("admin", "super_admin") and str(template.seller_id or "") != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only re-upload template files for your own templates.",
        )

    zip_bytes = await _read_upload_limited(file)
    from app.models.stored_file import StoredFile
    from app.api.v1.routes.files import create_signed_url
    from app.services.project_analyzer import project_analyzer

    # 1. Run automatic project analysis & security scan on the re-uploaded file
    analysis = await project_analyzer.analyze_zip(zip_bytes, file.filename)
    if analysis.get("success"):
        detected_fw = analysis.get("framework_detected")
        if detected_fw:
            fw_lower = str(detected_fw).lower()
            if "next" in fw_lower:
                template.framework = TemplateFramework.NEXTJS
            elif "react" in fw_lower:
                template.framework = TemplateFramework.REACT
            elif "nuxt" in fw_lower:
                template.framework = TemplateFramework.NUXT
            elif "vue" in fw_lower:
                template.framework = TemplateFramework.VUE
            elif "astro" in fw_lower:
                template.framework = TemplateFramework.ASTRO
            elif "svelte" in fw_lower:
                template.framework = TemplateFramework.SVELTE
            elif "angular" in fw_lower:
                template.framework = TemplateFramework.ANGULAR
            elif "tailwind" in fw_lower:
                template.framework = TemplateFramework.TAILWIND
            else:
                template.framework = TemplateFramework.HTML

        detected_ver = analysis.get("code_version") or analysis.get("version") or analysis.get("framework_version")
        if detected_ver:
            template.version = str(detected_ver)

        if analysis.get("pages"):
            template.pages_count = len(analysis["pages"])
            template.included_pages = analysis["pages"]

        if analysis.get("dark_mode") is not None:
            template.has_dark_mode = bool(analysis["dark_mode"])

        if analysis.get("responsive_analysis"):
            template.is_responsive = bool(analysis["responsive_analysis"].get("mobile", True))

        if analysis.get("changelog"):
            template.changelog = {
                **(template.changelog or {}),
                "last_reupload_analysis": analysis,
                "reuploaded_at": datetime.now(timezone.utc).isoformat()
            }

    # 2. Save to StoredFile table in PostgreSQL
    sf = StoredFile(
        filename=f"templates/{t_uuid}_{file.filename}",
        original_filename=file.filename,
        content_type="application/zip" if file.filename.lower().endswith(".zip") else "text/html",
        size=len(zip_bytes),
        data=zip_bytes,
        created_by_id=current_user.id,
    )
    db.add(sf)
    await db.flush()

    signed_url = create_signed_url(sf.id, expires_in_seconds=86400 * 365)
    download_assets = dict(template.download_assets or {})
    download_assets["zip"] = signed_url
    template.download_assets = download_assets
    template.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # 3. Purge all preview disk caches so the next preview extracts the new files
    import shutil
    cache_dirs = [
        os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(t_uuid)),
        os.path.join(tempfile.gettempdir(), "ai_site_studio_previews", str(t_uuid)),
    ]
    for p_dir in cache_dirs:
        if os.path.exists(p_dir):
            shutil.rmtree(p_dir, ignore_errors=True)

    # 4. Invalidate template detail caches
    if hasattr(template, "slug") and template.slug:
        await cache_delete(CacheKeys.template(template.slug))
    await cache_delete(CacheKeys.template(str(t_uuid)))
    await cache_delete_pattern("templates:featured:*")

    service = TemplateService(db)
    return await service.get_template_by_id(t_uuid)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str | uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a template or studio project. Admins can delete any template; users can delete their own."""
    service = TemplateService(db)
    await service.delete_template(template_id, current_user)


@router.post("/{template_id}/download")
async def download_template(
    template_id: str | uuid.UUID,
    format: Optional[str] = "zip",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate secure download URL for a purchased template.
    """
    from app.repositories.template_repo import TemplateRepository
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    is_authorized_creator = str(template.seller_id) == str(current_user.id)
    template_status = getattr(template.status, "value", str(template.status)).lower()
    is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
    if template_status != TemplateStatus.PUBLISHED.value and not (is_authorized_creator or is_admin):
        raise HTTPException(status_code=404, detail="Template not found")
    if (template_status == TemplateStatus.PUBLISHED.value and not template.is_free
            and not settings.TEMPLATE_DOWNLOADS_FREE and not is_authorized_creator):
        purchase = await db.execute(
            select(OrderItem.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == current_user.id,
                Order.status == OrderStatus.COMPLETED,
                OrderItem.template_id == template_id,
            )
            .limit(1)
        )
        if purchase.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Purchase required to download this template")

    await template_repo.increment_downloads(template_id)
    
    from app.models.download import Download
    download_log = Download(
        user_id=current_user.id,
        template_id=template_id,
    )
    db.add(download_log)
    await db.flush()
    await db.commit()
    
    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Source zip file not configured for this template")
        
    # Stored files require a short-lived signature. External URLs retain their
    # provider-managed access controls.
    if zip_url.startswith(settings.STORAGE_BASE_URL.rstrip("/") + "/"):
        file_id = zip_url.rsplit("/", 1)[-1]
        expires = int(datetime.now(timezone.utc).timestamp()) + 3600
        signature = generate_file_signature(file_id, expires)
        zip_url = f"{zip_url}?expires={expires}&signature={signature}"

    return {"download_url": zip_url}


@router.get("/{template_id}/preview/render/{filename:path}")
async def render_live_template_preview(
    template_id: str,
    filename: str = "index.html",
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Live Interactive Web Preview Sandbox Endpoint.
    Extracts the generated HTML/assets from ZIP storage and serves them directly as text/html for iframe embedding.
    """
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id_or_slug(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template_status = template.status.value if hasattr(template.status, "value") else str(template.status)
    if template_status != TemplateStatus.PUBLISHED.value:
        role = current_user.role.value if current_user and hasattr(current_user.role, "value") else (str(current_user.role) if current_user else "")
        is_admin = role.lower() in {"admin", "super_admin"}
        if not current_user or (str(template.seller_id or "") != str(current_user.id) and not is_admin):
            raise HTTPException(status_code=404, detail="Template not found")

    zip_asset_url = template.download_assets.get("zip") if template.download_assets else None
    if not zip_asset_url:
        raise HTTPException(status_code=404, detail="Template asset package not available")

    file_id = storage._parse_file_id(zip_asset_url)
    if not file_id:
        raise HTTPException(status_code=404, detail="Invalid zip asset url")

    # Read zip bytes from storage
    try:
        file_info = await storage.get_file(db, file_id)
        if not file_info or not file_info[0]:
            raise HTTPException(status_code=404, detail="Could not read template zip file")
        zip_bytes = file_info[0]

        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            target_path = filename if filename in zf.namelist() else f"frontend/{filename}"
            if target_path not in zf.namelist():
                # Fallback to index.html or frontend/index.html
                target_path = "index.html" if "index.html" in zf.namelist() else "frontend/index.html"

            if target_path in zf.namelist():
                content = zf.read(target_path).decode("utf-8", errors="replace")
                content_type = "text/html" if target_path.endswith(".html") else "text/css" if target_path.endswith(".css") else "application/javascript"
                return Response(
                    content=content,
                    media_type=content_type,
                    headers=security_scanner.get_secure_preview_headers(),
                )
            else:
                raise HTTPException(status_code=404, detail=f"File '{filename}' not found in template package")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to render live preview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to render live preview: {str(e)}")
