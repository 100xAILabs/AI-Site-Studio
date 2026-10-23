"""
Template service — business logic layer.
"""

import uuid
import os
from typing import List, Optional, Tuple
from math import ceil

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

        # Get user interaction flags in bulk via parallel gathering
        favorited_ids: set = set()
        wishlisted_ids: set = set()
        if current_user:
            import asyncio
            fav_task = self.favorites.get_favorited_ids(current_user.id)
            wish_task = self.wishlist.get_wishlisted_ids(current_user.id)
            fav_res, wish_res = await asyncio.gather(fav_task, wish_task)
            favorited_ids = set(fav_res)
            wishlisted_ids = set(wish_res)

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
                    "pages_count": t.pages_count,
                    "has_dark_mode": t.has_dark_mode,
                    "is_featured": t.is_featured,
                    "is_bestseller": t.is_bestseller,
                    "is_new": t.is_new,
                    "downloads_count": t.downloads_count,
                    "rating_avg": t.rating_avg,
                    "rating_count": t.rating_count,
                    "developer_name": t.developer_name,
                    "is_favorited": t.id in favorited_ids if current_user else None,
                    "is_wishlisted": t.id in wishlisted_ids if current_user else None,
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
        import asyncio
        fav_task = self.favorites.get_favorited_ids(current_user.id)
        wish_task = self.wishlist.get_wishlisted_ids(current_user.id)
        fav_res, wish_res = await asyncio.gather(fav_task, wish_task)
        favorited_ids = set(fav_res)
        wishlisted_ids = set(wish_res)

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
        user_role = getattr(getattr(current_user, "role", None), "value", str(getattr(current_user, "role", ""))).lower()
        is_owner = current_user is not None and str(template.seller_id) == str(current_user.id)
        is_admin = user_role in {"admin", "super_admin"}
        if template_status != TemplateStatus.PUBLISHED.value and not (is_owner or is_admin):
            # AI Studio drafts are private projects and must never be publicly browsable.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

        # Record unique account view — if 1 account opens 5 times, it only counts as 1.
        if current_user:
            await self.record_unique_account_view(template.id, current_user.id)


        is_favorited = None
        is_wishlisted = None
        if current_user:
            is_favorited = await self.favorites.is_favorited(current_user.id, template.id)
            is_wishlisted = await self.wishlist.is_wishlisted(current_user.id, template.id)

        response = TemplateResponse.model_validate(template)
        
        # Dynamically inspect ZIP files ONLY if included_pages has never been determined
        download_assets = template.download_assets or {}
        if (not template.included_pages or len(template.included_pages) == 0) and "zip" in download_assets:
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
                if stored_file:
                    import zipfile
                    import io
                    with zipfile.ZipFile(io.BytesIO(stored_file.data), "r") as z_in:
                        namelist = z_in.namelist()
                        
                        # Find base directory of index.html
                        base_dir = ""
                        for name in namelist:
                            if name.endswith("index.html"):
                                if "/" in name:
                                    base_dir = name.rsplit("index.html", 1)[0]
                                break
                        
                        pages = []
                        for name in namelist:
                            if name.startswith(base_dir) and (name.endswith(".html") or name.endswith(".jsx") or name.endswith(".js") or name.endswith(".tsx") or name.endswith(".ts")):
                                rel_name = name[len(base_dir):]
                                if "/" not in rel_name and rel_name != "" and not rel_name.startswith("__MACOSX"):
                                    pages.append(rel_name)
                        
                        # Dynamic section detection for single-page templates
                        if len(pages) <= 1:
                            try:
                                index_content = z_in.read(base_dir + "index.html").decode("utf-8", errors="ignore")
                                anchors = re.findall(r'href="#([a-zA-Z0-9_-]+)"', index_content)
                                seen = set()
                                for anchor in anchors:
                                    if anchor.lower() not in ["home", "top", "carousel", "header", "footer", "wrapper", "main"] and anchor not in seen:
                                        seen.add(anchor)
                                        pages.append(f"{anchor}.html")
                            except Exception:
                                pass
                                
                        if not pages:
                            pages = ["index.html"]
                        response.included_pages = sorted(list(set(pages)))
                        # Persist permanently in database so it is never re-scanned
                        template.included_pages = response.included_pages
                        await self.db.commit()
            except Exception:
                pass
                
        # Get developer stats
        templates_count = 0
        total_sales = 0
        if template.seller_id or template.developer_name:
            from sqlalchemy import select, func
            from app.models.template import TemplateStatus

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
        return response

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
        return TemplateResponse.model_validate(template)

    async def delete_template(
        self, template_id: uuid.UUID, current_user: Optional[User] = None
    ) -> None:
        template = await self.repo.get_by_id(template_id)
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

        # 1. Clean preview cache if exists
        try:
            import tempfile, shutil
            preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
            if os.path.exists(preview_dir):
                shutil.rmtree(preview_dir, ignore_errors=True)
        except Exception:
            pass

        # 2. Clean up associated stored ZIP / file assets in PostgreSQL
        try:
            from app.core.storage import storage
            if template.download_assets and isinstance(template.download_assets, dict):
                for asset_url in template.download_assets.values():
                    if isinstance(asset_url, str):
                        await storage.delete_file(self.db, asset_url)
        except Exception:
            pass

        # 3. Clean up Qdrant vector index if available
        try:
            from app.services.search_service import SearchService
            ss = SearchService(self.db)
            await ss.delete_template_vector(str(template.id))
        except Exception:
            pass

        await self.repo.delete(template)

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
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            return False

