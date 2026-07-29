"""
Template service — business logic layer.
"""

import uuid
from typing import List, Optional, Tuple
from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template
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

        # Get user interaction flags in bulk
        favorited_ids: set = set()
        wishlisted_ids: set = set()
        if current_user:
            favorited_ids = set(await self.favorites.get_favorited_ids(current_user.id))
            wishlisted_ids = set(await self.wishlist.get_wishlisted_ids(current_user.id))

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

        # Increment view count (fire-and-forget style in real app)
        await self.repo.increment_views(template.id)

        is_favorited = None
        is_wishlisted = None
        if current_user:
            is_favorited = await self.favorites.is_favorited(current_user.id, template.id)
            is_wishlisted = await self.wishlist.is_wishlisted(current_user.id, template.id)

        response = TemplateResponse.model_validate(template)
        
        # Dynamically inspect ZIP files if included_pages is empty or only shows index.html (self-healing for auto-seeded templates).
        # Keep the archive URL on the server: TemplateResponse is a public API response.
        download_assets = template.download_assets or {}
        if (not response.included_pages or response.included_pages == ["index.html"]) and "zip" in download_assets:
            try:
                zip_url = download_assets["zip"]
                file_id_str = zip_url.split("/")[-1]
                file_id = uuid.UUID(file_id_str)
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
                        if pages:
                            response.included_pages = sorted(pages)
                            # Cache in database
                            template.included_pages = response.included_pages
                            await self.db.flush()
            except Exception as e:
                print("Failed to dynamically extract included_pages:", e)
                
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
                Template.status == TemplateStatus.PUBLISHED
            )
            count_result = await self.db.execute(count_query)
            templates_count = count_result.scalar() or 0

            sales_query = select(func.sum(Template.downloads_count)).where(
                count_cond,
                Template.status == TemplateStatus.PUBLISHED
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
        if current_user.role.value not in ("admin", "super_admin") and template.seller_id != current_user.id:
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
        # Sellers can only delete templates they own.
        if current_user and current_user.role.value not in ("admin", "super_admin"):
            if template.seller_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only delete your own templates.",
                )

        await self.repo.delete(template)

    async def get_featured_templates(self, limit: int = 8) -> List[TemplateCardResponse]:
        templates = await self.repo.get_featured(limit)
        return [TemplateCardResponse.model_validate(t) for t in templates]
