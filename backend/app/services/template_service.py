"""
Template service — business logic layer.
"""

import uuid
import os
from typing import List, Optional, Tuple
from math import ceil
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template, TemplateStatus
from app.models.user import User
from app.repositories.template_repo import TemplateRepository
from app.repositories.favorite_repo import FavoriteRepository, WishlistRepository
from app.schemas.template import (
    TemplateCreate, TemplateUpdate, TemplateResponse,
    TemplateCardResponse, TemplateListResponse, TemplateFilterParams,
)
from app.core.config import settings
from fastapi import HTTPException, status


class TemplateService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TemplateRepository(db)
        self.favorites = FavoriteRepository(db)
        self.wishlist = WishlistRepository(db)

    async def list_templates(
        self,
        filters: TemplateFilterParams,
        current_user: Optional[User] = None,
    ) -> TemplateListResponse:
        templates, total = await self.repo.list_with_filters(filters, current_user)

        # Get user interaction flags sequentially (AsyncSession is single-concurrency)
        favorited_ids: set = set()
        wishlisted_ids: set = set()
        purchased_ids: set = set()
        if current_user:
            try:
                fav_res = await self.favorites.get_favorited_ids(current_user.id)
                wish_res = await self.wishlist.get_wishlisted_ids(current_user.id)
                favorited_ids = set(fav_res)
                wishlisted_ids = set(wish_res)

                from app.models.order import Order, OrderItem, OrderStatus
                from sqlalchemy import select
                purch_stmt = (
                    select(OrderItem.template_id)
                    .join(Order, Order.id == OrderItem.order_id)
                    .where(
                        Order.user_id == current_user.id,
                        Order.status == OrderStatus.COMPLETED,
                    )
                )
                purch_res = await self.db.execute(purch_stmt)
                purchased_ids = set(purch_res.scalars().all())
            except Exception as e_fav:
                pass

        cards = [
            TemplateCardResponse(
                **{
                    "id": t.id,
                    "title": t.title,
                    "slug": t.slug,
                    "short_description": t.short_description,
                    "price": t.price,
                    "original_price": t.original_price,
                    "is_free": t.is_free,
                    "is_on_sale": t.is_on_sale,
                    "thumbnail_url": t.thumbnail_url,
                    "video_url": t.video_url,
                    "category_id": t.category_id,
                    "tags": t.tags,
                    "framework": t.framework,
                    "pages_count": max(len(t.included_pages or []), t.pages_count or 1),
                    "included_pages": t.included_pages,
                    "has_dark_mode": t.has_dark_mode,
                    "is_featured": t.is_featured,
                    "is_bestseller": t.is_bestseller,
                    "is_new": t.is_new,
                    "downloads_count": t.downloads_count,
                    "rating_avg": t.rating_avg,
                    "rating_count": t.rating_count,
                    "developer_name": t.developer_name,
                    "seller_id": t.seller_id,
                    "is_favorited": t.id in favorited_ids if current_user else None,
                    "is_wishlisted": t.id in wishlisted_ids if current_user else None,
                    "is_purchased": t.id in purchased_ids if current_user else None,
                }
            )
            for t in templates
        ]

        total_pages = ceil(total / filters.page_size) if total > 0 else 1

        return TemplateListResponse(
            items=cards,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
        )

    async def enrich_with_user_interactions(
        self,
        cached_catalog: dict,
        current_user: User,
    ) -> TemplateListResponse:
        favorited_ids: set = set()
        wishlisted_ids: set = set()
        try:
            fav_res = await self.favorites.get_favorited_ids(current_user.id)
            wish_res = await self.wishlist.get_wishlisted_ids(current_user.id)
            favorited_ids = set(fav_res)
            wishlisted_ids = set(wish_res)
        except Exception as e_fav:
            pass

        items = []
        for raw in cached_catalog.get("items", []):
            item_data = dict(raw)
            try:
                t_id = uuid.UUID(str(item_data["id"])) if isinstance(item_data["id"], str) else item_data["id"]
            except Exception:
                t_id = item_data["id"]
            item_data["is_favorited"] = t_id in favorited_ids
            item_data["is_wishlisted"] = t_id in wishlisted_ids
            items.append(TemplateCardResponse.model_validate(item_data))

        return TemplateListResponse(
            items=items,
            total=cached_catalog.get("total", 0),
            page=cached_catalog.get("page", 1),
            page_size=cached_catalog.get("page_size", 20),
            total_pages=cached_catalog.get("total_pages", 1),
        )

    async def get_template_by_id(
        self,
        template_id: uuid.UUID | str,
        current_user: Optional[User] = None,
    ) -> TemplateResponse:
        return await self.get_template(slug=str(template_id), current_user=current_user)

    async def get_template(
        self,
        slug: str,
        current_user: Optional[User] = None,
    ) -> TemplateResponse:
        template = await self.repo.get_by_slug(slug)
        if not template:
            try:
                template_id = uuid.UUID(slug)
                template = await self.repo.get_by_id(template_id)
            except ValueError:
                pass
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

        template_status = getattr(template.status, "value", str(template.status)).lower()
        user_id = getattr(current_user, "id", None) if current_user else None
        user_role = getattr(getattr(current_user, "role", None), "value", str(getattr(current_user, "role", ""))).lower() if current_user else ""
        template_id = template.id
        seller_id = getattr(template, "seller_id", None)
        is_owner = user_id is not None and str(seller_id) == str(user_id)
        is_admin = user_role in {"admin", "super_admin"}
        if template_status != TemplateStatus.PUBLISHED.value and not (is_owner or is_admin):
            # AI Studio drafts are private projects and must never be publicly browsable.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

        # Record unique account view — if 1 account opens 5 times, it only counts as 1.
        if user_id:
            try:
                await self.record_unique_account_view(template_id, user_id)
            except Exception:
                pass

        is_favorited = None
        is_wishlisted = None
        is_purchased = False
        if user_id:
            is_favorited = await self.favorites.is_favorited(user_id, template_id)
            is_wishlisted = await self.wishlist.is_wishlisted(user_id, template_id)
            is_purchased = await self.is_purchased_by_user(user_id, template_id)

        response = TemplateResponse.model_validate(template)
        
        # Dynamically inspect ZIP files if included_pages has never been determined or defaulted to ['Home']
        download_assets = template.download_assets or {}
        if (not template.included_pages or len(template.included_pages) <= 1 or template.included_pages == ["Home"]) and "zip" in download_assets:
            try:
                import re
                zip_url = download_assets["zip"]
                file_id = None
                match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
                if match:
                    file_id = uuid.UUID(match.group(1))
                from app.models.stored_file import StoredFile
                from sqlalchemy import select
                result = await self.db.execute(select(StoredFile).where(StoredFile.id == file_id))
                stored_file = result.scalar_one_or_none()
                if stored_file and stored_file.data:
                    import zipfile
                    import io
                    with zipfile.ZipFile(io.BytesIO(stored_file.data), "r") as z_in:
                        namelist = z_in.namelist()
                        pages = []

                        # Look for HTML pages
                        for name in namelist:
                            if name.startswith("__MACOSX") or "/." in name:
                                continue
                            fn = os.path.basename(name)
                            fn_lower = fn.lower()
                            if fn_lower.endswith(".html") and fn_lower not in ["404.html", "500.html"]:
                                if fn not in pages:
                                    pages.append(fn)

                        # Look for React / Vue pages in pages/, views/, routes/, or app/
                        for name in namelist:
                            if name.startswith("__MACOSX") or "/." in name:
                                continue
                            fn = os.path.basename(name)
                            fn_lower = fn.lower()
                            name_norm = name.replace("\\", "/").lower()
                            if any(p_dir in name_norm for p_dir in ["/pages/", "/views/", "/routes/", "/app/"]):
                                if fn_lower.endswith((".jsx", ".tsx", ".vue")):
                                    base_no_ext = os.path.splitext(fn)[0].lower()
                                    if base_no_ext not in ["layout", "loading", "error", "not-found", "404", "app"]:
                                        if fn not in pages:
                                            pages.append(fn)

                        # If React/Vue and we have App.jsx/App.vue, ensure Home is included
                        has_app = any(os.path.basename(n).lower() in ["app.jsx", "app.tsx", "app.vue", "home.jsx", "home.vue"] for n in namelist)
                        if has_app and not any(p.lower().startswith("home") or p.lower().startswith("app") for p in pages):
                            pages.insert(0, "Home.jsx" if any(n.endswith(".jsx") for n in namelist) else "Home")
                        elif not pages:
                            pages = ["index.html"]

                        response.included_pages = pages
                        template.included_pages = pages
                        template.pages_count = max(len(pages), 1)
                        response.pages_count = template.pages_count
                        await self.db.commit()
            except Exception:
                pass
                
        # Get developer stats
        templates_count = 0
        total_sales = 0
        if template.seller_id or template.developer_name:
            from sqlalchemy import select, func

            count_cond = (
                Template.seller_id == template.seller_id 
                if template.seller_id 
                else Template.developer_name == template.developer_name
            )
            count_query = select(func.count(Template.id)).where(
                count_cond,
                Template.status == TemplateStatus.PUBLISHED,
                Template.slug.notlike("%-custom-%"),
                Template.title.notlike("%(Customized)%"),
                Template.title.notlike("Customized %"),
            )
            count_result = await self.db.execute(count_query)
            templates_count = count_result.scalar() or 0

            sales_query = select(func.sum(Template.downloads_count)).where(
                count_cond,
                Template.status == TemplateStatus.PUBLISHED,
                Template.slug.notlike("%-custom-%"),
                Template.title.notlike("%(Customized)%"),
                Template.title.notlike("Customized %"),
            )
            sales_result = await self.db.execute(sales_query)
            total_sales = sales_result.scalar() or 0

        response.seller_templates_count = templates_count
        response.seller_total_sales = total_sales
        response.is_favorited = is_favorited
        response.is_wishlisted = is_wishlisted
        response.is_purchased = is_purchased
        return response

    async def is_purchased_by_user(self, user_id: uuid.UUID | str, template_id: uuid.UUID | str) -> bool:
        """Check if user has an active completed order for this template."""
        from app.models.order import Order, OrderItem, OrderStatus
        from sqlalchemy import select
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except (ValueError, TypeError):
                return False
        if isinstance(template_id, str):
            try:
                template_id = uuid.UUID(template_id)
            except (ValueError, TypeError):
                return False
        stmt = (
            select(Order.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                Order.status == OrderStatus.COMPLETED,
                OrderItem.template_id == template_id,
            )
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def create_template(
        self, data: TemplateCreate, seller_id: Optional[uuid.UUID] = None
    ) -> TemplateResponse:
        template = await self.repo.create(data)
        # Permanently bind this template to the uploading seller's account
        if seller_id is not None:
            template.seller_id = seller_id
            await self.db.flush()
            await self.db.commit()
            # Re-fetch with eagerly loaded relationships (selectinload) instead
            # of refresh(), which strips loaded relationships and causes
            # MissingGreenlet when Pydantic serializes in async context.
            template = await self.repo.get_by_id(template.id)
        return TemplateResponse.model_validate(template)

    async def update_template(
        self, template_id: uuid.UUID, data: TemplateUpdate, current_user: User
    ) -> TemplateResponse:
        template = await self.repo.get_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        if str(role_val).lower() not in ("admin", "super_admin") and str(template.seller_id or "") != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own templates.",
            )
        template = await self.repo.update(template, data)
        await self.db.commit()
        return TemplateResponse.model_validate(template)

    async def delete_template(
        self, template_id: uuid.UUID, current_user: Optional[User] = None
    ) -> None:
        template = await self.repo.get_by_id(template_id, include_deleted=True)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Admins and super-admins can delete any template.
        # Users/Sellers/Buyers can delete templates they own or created.
        if current_user:
            role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
            if str(role_val).lower() not in ("admin", "super_admin"):
                creator_id = getattr(template, "creator_id", None)
                seller_id = getattr(template, "seller_id", None)
                user_id_str = str(current_user.id)
                if str(seller_id or "") != user_id_str and str(creator_id or "") != user_id_str:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only delete your own templates or studio projects.",
                    )

        # Soft delete: move to trash for retention (1 week user, 30 days admin)
        template.is_deleted = True
        template.deleted_at = datetime.now(timezone.utc)
        template.deleted_by_id = current_user.id if current_user else None
        await self.db.commit()

        # Invalidate caches
        try:
            from app.core.redis import cache_delete, cache_delete_pattern, CacheKeys
            from app.services.fast_catalog import fast_catalog
            if hasattr(template, "slug") and template.slug:
                await cache_delete(CacheKeys.template(template.slug))
            await cache_delete(CacheKeys.template(str(template_id)))
            await cache_delete_pattern("templates:featured:*")
            fast_catalog.invalidate()
        except Exception:
            pass

    async def restore_template(
        self, template_id: uuid.UUID, current_user: Optional[User] = None
    ) -> Template:
        template = await self.repo.get_by_id(template_id, include_deleted=True)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if not template.is_deleted:
            return template

        is_admin = False
        if current_user:
            role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
            is_admin = str(role_val).lower() in ("admin", "super_admin")

        now = datetime.now(timezone.utc)
        del_date = template.deleted_at or now
        if del_date.tzinfo is None:
            del_date = del_date.replace(tzinfo=timezone.utc)

        if not is_admin:
            # Regular user must be the owner
            creator_id = getattr(template, "creator_id", None)
            seller_id = getattr(template, "seller_id", None)
            user_id_str = str(current_user.id) if current_user else ""
            if str(seller_id or "") != user_id_str and str(creator_id or "") != user_id_str:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only recover your own templates or drafts.",
                )

            # 7-day user recovery window
            if (now - del_date).total_seconds() > 7 * 86400:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Draft recovery window has expired (7 days limit). Please contact an administrator to recover within 30 days.",
                )
        else:
            # 30-day admin recovery window
            if (now - del_date).total_seconds() > 30 * 86400:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Template retention window has expired (30 days limit).",
                )

        template.is_deleted = False
        template.deleted_at = None
        template.deleted_by_id = None
        await self.db.commit()

        # Invalidate caches
        try:
            from app.core.redis import cache_delete, cache_delete_pattern, CacheKeys
            from app.services.fast_catalog import fast_catalog
            if hasattr(template, "slug") and template.slug:
                await cache_delete(CacheKeys.template(template.slug))
            await cache_delete(CacheKeys.template(str(template_id)))
            await cache_delete_pattern("templates:featured:*")
            fast_catalog.invalidate()
        except Exception:
            pass

        return template

    async def permanent_delete_template(
        self, template_id: uuid.UUID, current_user: Optional[User] = None
    ) -> None:
        template = await self.repo.get_by_id(template_id, include_deleted=True)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if current_user:
            role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
            if str(role_val).lower() not in ("admin", "super_admin"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only administrators can permanently delete templates.",
                )

        # 1. Clean preview cache if exists
        try:
            import tempfile, shutil
            preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
            if os.path.exists(preview_dir):
                shutil.rmtree(preview_dir, ignore_errors=True)
            preview_dir_2 = os.path.join(tempfile.gettempdir(), "ai_site_studio_previews", str(template_id))
            if os.path.exists(preview_dir_2):
                shutil.rmtree(preview_dir_2, ignore_errors=True)
        except Exception:
            pass

        # 2. Clean up associated stored ZIP / file assets
        try:
            from app.core.storage import storage
            if template.download_assets and isinstance(template.download_assets, dict):
                for asset_url in template.download_assets.values():
                    if isinstance(asset_url, str):
                        await storage.delete_file(self.db, asset_url)
        except Exception:
            pass

        # 3. Clean up generated_projects directory if exists (exact matching)
        try:
            import shutil
            from pathlib import Path
            possible_roots = [
                Path(__file__).resolve().parents[3],
                Path.cwd(),
            ]
            for r in possible_roots:
                gen_proj_dir = r / "generated_projects"
                if gen_proj_dir.is_dir():
                    alias_file = gen_proj_dir / f".id_{template.id}.txt"
                    if alias_file.is_file():
                        try:
                            alias_file.unlink(missing_ok=True)
                        except Exception:
                            pass
                    for entry in os.listdir(gen_proj_dir):
                        if entry == str(template.id) or (template.slug and entry == template.slug):
                            full_p = gen_proj_dir / entry
                            if full_p.is_dir():
                                shutil.rmtree(full_p, ignore_errors=True)
        except Exception:
            pass

        # 4. Clean up Qdrant vector index if available
        try:
            from app.services.search_service import SearchService
            ss = SearchService(self.db)
            await ss.delete_template_vector(str(template.id))
        except Exception:
            pass

        await self.repo.delete(template)
        await self.db.commit()

        # Invalidate caches
        try:
            from app.core.redis import cache_delete, cache_delete_pattern, CacheKeys
            from app.services.fast_catalog import fast_catalog
            if hasattr(template, "slug") and template.slug:
                await cache_delete(CacheKeys.template(template.slug))
            await cache_delete(CacheKeys.template(str(template_id)))
            await cache_delete_pattern("templates:featured:*")
            fast_catalog.invalidate()
        except Exception:
            pass

    async def get_featured_templates(self, limit: int = 8) -> List[TemplateCardResponse]:
        templates = await self.repo.get_featured(limit)
        return [TemplateCardResponse.model_validate(t) for t in templates]

    async def record_unique_account_view(
        self,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """
        Record a unique view for this account.
        If the account has already viewed this template, does nothing.
        If this is a new unique account opening the template, records it
        and increments views_count by 1.
        """
        try:
            # 1. Quick Redis set check for instant deduplication
            from app.core.redis import get_redis_client
            redis_client = await get_redis_client()
            if redis_client:
                viewer_set_key = f"template:{template_id}:account_viewers"
                is_new = await redis_client.sadd(viewer_set_key, str(user_id))
                if not is_new:
                    return False  # Already viewed by this account

            # 2. Database check & record in template_account_views
            from app.models.template_view import TemplateAccountView
            from sqlalchemy import select

            existing = await self.db.execute(
                select(TemplateAccountView).where(
                    TemplateAccountView.template_id == template_id,
                    TemplateAccountView.user_id == user_id,
                )
            )
            if existing.scalar_one_or_none():
                return False

            new_view = TemplateAccountView(
                template_id=template_id,
                user_id=user_id,
            )
            self.db.add(new_view)
            await self.repo.increment_views(template_id)
            await self.db.flush()
            return True
        except Exception as e:
            await self.db.rollback()
            return False


async def create_or_get_buyer_draft_copy(
    db: AsyncSession,
    buyer_id: uuid.UUID,
    marketplace_template: Template
) -> Template:
    """
    Creates or returns a private draft copy of a purchased marketplace template
    stored under the buyer's account details (seller_id = buyer_id).
    Ensures that when a user buys a template:
    1. It is stored under the buyer's own database records and file storage.
    2. The original marketplace template remains completely untouched and pristine.
    3. When the buyer opens the editor, it directly accesses their own database copy.
    """
    from sqlalchemy import select, or_
    from app.core.local_project_manager import local_project_manager

    slug_base = (marketplace_template.slug or "template").split("-custom-")[0].split("-draft-")[0].split("-user-")[0]
    ed_res = await db.execute(
        select(Template).where(
            Template.seller_id == buyer_id,
            Template.status == TemplateStatus.DRAFT,
            or_(
                Template.forked_from_template_id == marketplace_template.id,
                Template.slug.like(f"{slug_base}-draft-%"),
                Template.slug.like(f"{slug_base}-user-%")
            )
        )
    )
    existing_draft = ed_res.scalars().first()
    if existing_draft:
        return existing_draft

    new_slug = f"{slug_base}-user-{buyer_id.hex[:6]}-{uuid.uuid4().hex[:6]}"
    new_title = f"{marketplace_template.title} (My Project)"
    clean_tags = [t for t in (marketplace_template.tags or []) if t != "studio-project"]
    if "customized-draft" not in clean_tags:
        clean_tags.append("customized-draft")

    new_template = Template(
        title=new_title,
        short_description=marketplace_template.short_description,
        description=marketplace_template.description,
        slug=new_slug,
        price=marketplace_template.price,
        original_price=marketplace_template.original_price,
        is_free=marketplace_template.is_free,
        is_on_sale=marketplace_template.is_on_sale,
        category_id=marketplace_template.category_id,
        status=TemplateStatus.DRAFT,
        is_marketplace=False,
        template_origin="custom_draft",
        forked_from_template_id=marketplace_template.id,
        seller_id=buyer_id,
        thumbnail_url=marketplace_template.thumbnail_url,
        preview_url=marketplace_template.preview_url,
        tags=clean_tags,
        framework=marketplace_template.framework,
        pages_count=marketplace_template.pages_count,
        has_dark_mode=marketplace_template.has_dark_mode,
        is_responsive=marketplace_template.is_responsive,
        is_rtl_supported=marketplace_template.is_rtl_supported,
        is_ai_ready=True,
        compatibility=marketplace_template.compatibility,
        version=marketplace_template.version,
        license_type=marketplace_template.license_type,
        industry=marketplace_template.industry,
        color_scheme=marketplace_template.color_scheme,
        seo_keywords=marketplace_template.seo_keywords,
        included_pages=marketplace_template.included_pages,
        download_assets=(marketplace_template.download_assets or {}).copy() if marketplace_template.download_assets else {}
    )
    db.add(new_template)
    await db.flush()

    try:
        local_project_manager.clone_project(
            marketplace_template.slug or marketplace_template.id,
            new_template.id,
            new_template.slug,
            new_template.title
        )
    except Exception as e_clone:
        import logging
        logging.getLogger("template_service").warning("Could not clone local project for buyer %s: %s", buyer_id, e_clone)

    return new_template


