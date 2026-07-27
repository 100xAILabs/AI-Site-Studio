"""
Template repository — database access layer for Template entities.
"""

import uuid
from decimal import Decimal
from typing import Optional, List, Tuple

from sqlalchemy import select, func, and_, or_, desc, asc, cast, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.template import Template, TemplateStatus, TemplateFramework, TemplateLicense
from app.models.category import Category
from app.models.user import User
from app.schemas.template import TemplateCreate, TemplateUpdate, TemplateFilterParams


class TemplateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, template_id: uuid.UUID) -> Optional[Template]:
        result = await self.db.execute(
            select(Template)
            .options(selectinload(Template.category).selectinload(Category.children))
            .where(Template.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Template]:
        result = await self.db.execute(
            select(Template)
            .options(selectinload(Template.category).selectinload(Category.children))
            .where(Template.slug == slug, Template.status == TemplateStatus.PUBLISHED)
        )
        return result.scalar_one_or_none()

    async def create(self, data: TemplateCreate) -> Template:
        # Prevent unique constraint violations by resolving slug conflicts
        import re
        base_slug = data.slug
        if not base_slug:
            base_slug = re.sub(r"[^\w\s-]", "", data.title.lower()).strip()
            base_slug = re.sub(r"[-\s]+", "-", base_slug)
        else:
            base_slug = re.sub(r"[-\s]+", "-", base_slug)
            
        slug = base_slug
        counter = 1
        while True:
            result = await self.db.execute(select(Template).where(Template.slug == slug))
            existing = result.scalar_one_or_none()
            if not existing:
                break
            slug = f"{base_slug}-{counter}"
            counter += 1
            
        data.slug = slug
        template = Template(**data.model_dump())
        self.db.add(template)
        await self.db.flush()
        return await self.get_by_id(template.id)

    async def update(self, template: Template, data: TemplateUpdate | dict) -> Template:
        update_data = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)
        await self.db.flush()
        return await self.get_by_id(template.id)

    async def delete(self, template: Template) -> None:
        await self.db.delete(template)
        await self.db.flush()

    async def list_with_filters(
        self,
        filters: TemplateFilterParams,
        current_user: Optional[User] = None,
    ) -> Tuple[List[Template], int]:
        """Return paginated, filtered, sorted templates + total count."""
        query = (
            select(Template)
            .options(selectinload(Template.category))
            .where(Template.status == TemplateStatus.PUBLISHED)
        )

        # ── Filters ──────────────────────────────────────────────────────────
        # Join Category if filtering by category or performing a keyword search
        need_category_join = bool(filters.category or (filters.q and not filters.semantic))
        if need_category_join:
            query = query.join(Category, Template.category_id == Category.id)

        # ── Filters ──────────────────────────────────────────────────────────
        if filters.category:
            category_normalized = filters.category.lower().replace("-", " ")
            parts = filters.category.split("-")
            slug_conditions = [Category.slug == filters.category]
            for p in parts:
                if len(p) > 3:
                    slug_conditions.append(Category.slug == p)
                    slug_conditions.append(Category.slug.ilike(f"%{p}%"))
            query = query.where(
                or_(
                    *slug_conditions,
                    Category.name.ilike(f"%{filters.category}%"),
                    Category.name.ilike(f"%{category_normalized}%"),
                    *[Category.name.ilike(f"%{p}%") for p in parts if len(p) > 3],
                    Template.industry.ilike(f"%{filters.category}%"),
                    Template.industry.ilike(f"%{category_normalized}%"),
                    cast(Template.tags, ARRAY(String)).overlap([filters.category]),
                    cast(Template.tags, ARRAY(String)).overlap([category_normalized]),
                    *[cast(Template.tags, ARRAY(String)).overlap([p]) for p in parts if len(p) > 3]
                )
            )

        if filters.min_price is not None:
            query = query.where(Template.price >= filters.min_price)
        if filters.max_price is not None:
            query = query.where(Template.price <= filters.max_price)

        if filters.rating is not None:
            query = query.where(Template.rating_avg >= filters.rating)

        if filters.is_free is not None:
            query = query.where(Template.is_free == filters.is_free)
        if filters.is_on_sale is not None:
            query = query.where(Template.is_on_sale == filters.is_on_sale)

        if filters.framework is not None:
            query = query.where(Template.framework == filters.framework)
        if filters.has_dark_mode is not None:
            query = query.where(Template.has_dark_mode == filters.has_dark_mode)
        if filters.is_ai_ready is not None:
            query = query.where(Template.is_ai_ready == filters.is_ai_ready)
        if filters.industry:
            query = query.where(Template.industry.ilike(f"%{filters.industry}%"))
        if filters.license_type:
            query = query.where(Template.license_type == filters.license_type)
        if filters.is_featured is not None:
            query = query.where(Template.is_featured == filters.is_featured)

        if filters.sales:
            if filters.sales == "no-sales":
                query = query.where(Template.downloads_count == 0)
            elif filters.sales == "low":
                query = query.where(and_(Template.downloads_count > 0, Template.downloads_count <= 10))
            elif filters.sales == "medium":
                query = query.where(and_(Template.downloads_count > 10, Template.downloads_count <= 50))
            elif filters.sales == "high":
                query = query.where(and_(Template.downloads_count > 50, Template.downloads_count <= 200))
            elif filters.sales == "top-seller":
                query = query.where(or_(Template.downloads_count > 200, Template.is_bestseller == True))

        if filters.compatibility:
            query = query.where(cast(Template.compatibility, ARRAY(String)).overlap([filters.compatibility]))

        if filters.language:
            # Check overlap in tags/keywords or if framework matches
            query = query.where(or_(
                Template.framework == filters.language,
                cast(Template.tags, ARRAY(String)).overlap([filters.language]),
                cast(Template.seo_keywords, ARRAY(String)).overlap([filters.language])
            ))

        if filters.date_added:
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            if filters.date_added == "last-24h":
                query = query.where(Template.created_at >= now - timedelta(days=1))
            elif filters.date_added == "last-week":
                query = query.where(Template.created_at >= now - timedelta(weeks=1))
            elif filters.date_added == "last-month":
                query = query.where(Template.created_at >= now - timedelta(days=30))
            elif filters.date_added == "last-year":
                query = query.where(Template.created_at >= now - timedelta(days=365))

        if filters.tags:
            query = query.where(cast(Template.tags, ARRAY(String)).overlap(filters.tags))

        if filters.q:
            q_clean = filters.q.strip().lower()
            
            # Synonym expansion for common search concepts to match relevant templates
            synonyms_list = [q_clean]
            synonym_dict = {
                "food": ["restaurant", "bistro", "culinary", "menu", "dining", "cafe", "bakery", "food"],
                "restaurant": ["food", "culinary", "dining", "bistro", "cafe", "bakery", "restaurant"],
                "restaurent": ["food", "culinary", "dining", "bistro", "cafe", "bakery", "restaurant"],
                "healthcare": ["medical", "hospital", "clinic", "dentist", "pharmacy", "doctor", "healthcare"],
                "medical": ["healthcare", "hospital", "clinic", "dentist", "pharmacy", "doctor", "medical"],
                "doctor": ["healthcare", "medical", "hospital", "clinic", "dentist", "doctor"],
                "ecommerce": ["store", "shop", "fashion", "clothing", "apparel", "retail", "ecommerce"],
                "shop": ["store", "ecommerce", "fashion", "clothing", "apparel", "retail", "shop"],
                "store": ["shop", "ecommerce", "fashion", "clothing", "apparel", "retail", "store"],
            }
            if q_clean in synonym_dict:
                synonyms_list.extend(synonym_dict[q_clean])
            
            # Trigram similarity score matrix (probability score)
            title_sim = func.similarity(Template.title, q_clean)
            desc_sim = func.similarity(Template.short_description, q_clean)
            industry_sim = func.similarity(Template.industry, q_clean)
            cat_sim = func.similarity(Category.name, q_clean)
            tags_sim = func.similarity(cast(Template.tags, String), q_clean)
            
            similarity_score = func.greatest(title_sim, desc_sim, industry_sim, cat_sim, tags_sim)

            # Build list of OR conditions for all synonyms and fields
            or_conditions = [similarity_score > 0.12]
            for term in synonyms_list:
                search_term = f"%{term}%"
                or_conditions.extend([
                    Template.title.ilike(search_term),
                    Template.short_description.ilike(search_term),
                    Template.description.ilike(search_term),
                    Template.industry.ilike(search_term),
                    Template.developer_name.ilike(search_term),
                    Template.color_scheme.ilike(search_term),
                    Category.name.ilike(search_term),
                    cast(Template.tags, String).ilike(search_term),
                ])

            if filters.semantic:
                # Resolve circular import by importing locally
                from app.services.search_service import SearchService
                search_service = SearchService(self.db)
                
                # Fetch semantic matches (limit to a pool of 50 candidates for filtering)
                try:
                    # Run semantic search synchronously inside the async context
                    matched_cards = await search_service.semantic_search(
                        query=filters.q, 
                        limit=50, 
                        category_filter=filters.category,
                        user=current_user
                    )
                    matched_ids = [c.id for c in matched_cards]
                except Exception:
                    matched_ids = []
                    
                if not matched_ids:
                    # Fallback to fuzzy similarity search when semantic search finds nothing
                    query = query.where(or_(*or_conditions))
                    score_expr = func.coalesce(similarity_score, 0.0)
                    query = query.order_by(score_expr.desc())
                else:
                    query = query.where(Template.id.in_(matched_ids))
                    # Order by the semantic relevance score ranking returned by Qdrant + Reranker
                    from sqlalchemy import case
                    ordering = case(
                        {id_: index for index, id_ in enumerate(matched_ids)},
                        value=Template.id
                    )
                    # We will bypass the default sorting list below and order by semantic relevance directly
                    query = query.order_by(ordering)
            else:
                # Fuzzy keyword search using Trigram Similarity (matrix matching)
                query = query.where(or_(*or_conditions))
                score_expr = func.coalesce(similarity_score, 0.0)
                query = query.order_by(score_expr.desc())


        # ── Count ─────────────────────────────────────────────────────────────
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # ── Sort ──────────────────────────────────────────────────────────────
        if not (filters.q and filters.semantic):
            sort_map = {
                "newest": Template.created_at.desc(),
                "best_sellers": Template.downloads_count.desc(),
                "best_rated": Template.rating_avg.desc(),
                "trending": Template.views_count.desc(),
                "lowest_price": Template.price.asc(),
                "highest_price": Template.price.desc(),
                "most_downloaded": Template.downloads_count.desc(),
            }
            order_by = sort_map.get(filters.sort, Template.created_at.desc())
            query = query.order_by(order_by)


        # ── Pagination ────────────────────────────────────────────────────────
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def increment_views(self, template_id: uuid.UUID) -> None:
        await self.db.execute(
            Template.__table__.update()
            .where(Template.id == template_id)
            .values(views_count=Template.views_count + 1)
        )

    async def increment_downloads(self, template_id: uuid.UUID) -> None:
        await self.db.execute(
            Template.__table__.update()
            .where(Template.id == template_id)
            .values(downloads_count=Template.downloads_count + 1)
        )

    async def update_rating(self, template_id: uuid.UUID, avg: float, count: int) -> None:
        await self.db.execute(
            Template.__table__.update()
            .where(Template.id == template_id)
            .values(rating_avg=avg, rating_count=count)
        )

    async def get_featured(self, limit: int = 8) -> List[Template]:
        result = await self.db.execute(
            select(Template)
            .options(selectinload(Template.category))
            .where(Template.is_featured == True, Template.status == TemplateStatus.PUBLISHED)
            .order_by(Template.downloads_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_ids(self, ids: List[uuid.UUID]) -> List[Template]:
        result = await self.db.execute(
            select(Template)
            .options(selectinload(Template.category))
            .where(Template.id.in_(ids))
        )
        return list(result.scalars().all())

    async def count_all(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Template))
        return result.scalar_one()
