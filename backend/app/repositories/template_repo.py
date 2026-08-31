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

    async def get_by_id(self, template_id: uuid.UUID | str) -> Optional[Template]:
        if isinstance(template_id, str):
            try:
                template_id = uuid.UUID(template_id)
            except ValueError:
                return await self.get_by_slug(template_id)
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
            .where(Template.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_id_or_slug(self, id_or_slug: str | uuid.UUID) -> Optional[Template]:
        if isinstance(id_or_slug, uuid.UUID):
            return await self.get_by_id(id_or_slug)
        try:
            parsed_uuid = uuid.UUID(str(id_or_slug))
            tmpl = await self.get_by_id(parsed_uuid)
            if tmpl:
                return tmpl
        except (ValueError, AttributeError):
            pass
        return await self.get_by_slug(str(id_or_slug))

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
        # Join Category if filtering by category, sub-category, or performing a keyword search
        need_category_join = bool(filters.category or (filters.q and not filters.semantic))
        if need_category_join:
            query = query.join(Category, Template.category_id == Category.id)

        # ── Category Filter — slug/name match via Category JOIN + tag / industry fallback ─────────
        if filters.category:
            cat_val = filters.category.strip().lower()
            cat_val_spaced = cat_val.replace("-", " ")
            cat_val_slug = cat_val.replace(" ", "-")
            query = query.where(
                or_(
                    Category.slug == cat_val,
                    Category.slug == cat_val_slug,
                    func.lower(Category.name) == cat_val,
                    func.lower(Category.name) == cat_val_spaced,
                    func.lower(Category.name).ilike(f"%{cat_val}%"),
                    cast(Template.tags, String).ilike(f"%{cat_val}%"),
                    cast(Template.tags, String).ilike(f"%{cat_val_spaced}%"),
                    cast(Template.tags, String).ilike(f"%{cat_val_slug}%"),
                    Template.industry.ilike(f"%{cat_val}%"),
                    Template.industry.ilike(f"%{cat_val_spaced}%"),
                )
            )

        # ── Sub-Category Filter — strict: industry field + tags only ──────────
        if filters.sub_category:
            sub_raw = filters.sub_category.strip()
            sub_lower = sub_raw.lower()
            sub_spaced = sub_lower.replace("-", " ")      # "small-business" → "small business"
            sub_slug = sub_lower.replace(" ", "-")         # "Small Business" → "small-business"

            # Match industry field (free-text, case insensitive)
            industry_conds = [
                Template.industry.ilike(f"%{sub_spaced}%"),
                Template.industry.ilike(f"%{sub_slug}%"),
                Template.industry.ilike(f"%{sub_raw}%"),
            ]

            # Match tags: ARRAY overlap + cast-to-text fallback (works with both PG ARRAY and JSON)
            tag_conds = [
                cast(Template.tags, ARRAY(String)).overlap(
                    [sub_lower, sub_spaced, sub_slug, sub_raw]
                ),
                cast(Template.tags, String).ilike(f"%{sub_spaced}%"),
                cast(Template.tags, String).ilike(f"%{sub_slug}%"),
            ]

            query = query.where(or_(*industry_conds, *tag_conds))

        # ── Price ─────────────────────────────────────────────────────────────
        if filters.min_price is not None:
            query = query.where(Template.price >= filters.min_price)
        if filters.max_price is not None:
            query = query.where(Template.price <= filters.max_price)

        # ── Rating ────────────────────────────────────────────────────────────
        if filters.rating is not None:
            query = query.where(Template.rating_avg >= filters.rating)

        # ── Boolean flags ─────────────────────────────────────────────────────
        # ── Boolean flags ─────────────────────────────────────────────────────
        if filters.is_free is not None:
            query = query.where(Template.is_free == filters.is_free)
        if filters.is_on_sale is not None:
            if filters.is_on_sale:
                query = query.where(
                    or_(
                        Template.is_on_sale.is_(True),
                        and_(Template.original_price.isnot(None), Template.original_price > Template.price)
                    )
                )
            else:
                query = query.where(
                    and_(
                        or_(Template.is_on_sale.is_(False), Template.is_on_sale.is_(None)),
                        or_(Template.original_price.is_(None), Template.original_price <= Template.price)
                    )
                )

        # ── Framework / Dark mode / AI-ready ──────────────────────────────────
        if filters.framework is not None:
            query = query.where(Template.framework == filters.framework)
        if filters.has_dark_mode is not None:
            query = query.where(Template.has_dark_mode == filters.has_dark_mode)
        if filters.is_ai_ready is not None:
            query = query.where(Template.is_ai_ready == filters.is_ai_ready)

        # ── Technology / Framework / UI Library ──────────────────────────────
        if filters.technology:
            tech_raw = filters.technology.strip().lower()
            tech_spaced = tech_raw.replace("-", " ")
            tech_slug = tech_raw.replace(" ", "-")

            query = query.where(
                or_(
                    func.lower(cast(Template.framework, String)) == tech_raw,
                    func.lower(cast(Template.framework, String)) == tech_slug,
                    func.lower(cast(Template.framework, String)).ilike(f"%{tech_raw}%"),
                    cast(Template.tags, String).ilike(f"%{tech_raw}%"),
                    cast(Template.tags, String).ilike(f"%{tech_spaced}%"),
                    cast(Template.tags, String).ilike(f"%{tech_slug}%"),
                    Template.title.ilike(f"%{tech_raw}%"),
                    Template.short_description.ilike(f"%{tech_raw}%"),
                    Template.description.ilike(f"%{tech_raw}%"),
                )
            )

        # ── Industry ──────────────────────────────────────────────────────────
        if filters.industry:
            query = query.where(Template.industry.ilike(f"%{filters.industry}%"))

        # ── License type ──────────────────────────────────────────────────────
        if filters.license_type:
            query = query.where(Template.license_type == filters.license_type)

        # ── Featured ──────────────────────────────────────────────────────────
        if filters.is_featured is not None:
            query = query.where(Template.is_featured == filters.is_featured)

        # ── Sales tier ────────────────────────────────────────────────────────
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
                query = query.where(or_(Template.downloads_count > 20, Template.is_bestseller.is_(True)))

        # ── Compatibility ─────────────────────────────────────────────────────
        if filters.compatibility:
            query = query.where(
                cast(Template.compatibility, ARRAY(String)).overlap([filters.compatibility])
            )

        # ── Language (tags/framework overlap) ─────────────────────────────────
        if filters.language:
            query = query.where(or_(
                Template.framework == filters.language,
                cast(Template.tags, ARRAY(String)).overlap([filters.language]),
                cast(Template.seo_keywords, ARRAY(String)).overlap([filters.language])
            ))

        # ── Date added ────────────────────────────────────────────────────────
        if filters.date_added:
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            if filters.date_added == "last-24h":
                query = query.where(Template.created_at >= now - timedelta(days=1))
            elif filters.date_added == "last-week":
                query = query.where(Template.created_at >= now - timedelta(days=7))
            elif filters.date_added == "last-month":
                query = query.where(Template.created_at >= now - timedelta(days=30))
            elif filters.date_added == "last-year":
                query = query.where(Template.created_at >= now - timedelta(days=365))

        # ── Developer ─────────────────────────────────────────────────────────
        if filters.developer:
            query = query.where(Template.developer_name == filters.developer)

        # ── Tag list ──────────────────────────────────────────────────────────
        if filters.tags:
            query = query.where(cast(Template.tags, ARRAY(String)).overlap(filters.tags))

        # ── Keyword / Semantic Search ──────────────────────────────────────────
        if filters.q:
            q_clean = filters.q.strip().lstrip("#").strip().lower()

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
            synonyms_list = [q_clean] + synonym_dict.get(q_clean, [])

            # Trigram similarity (requires pg_trgm extension)
            title_sim = func.similarity(Template.title, q_clean)
            desc_sim = func.similarity(Template.short_description, q_clean)
            industry_sim = func.similarity(Template.industry, q_clean)
            tags_sim = func.similarity(cast(Template.tags, String), q_clean)

            if need_category_join:
                cat_sim = func.similarity(Category.name, q_clean)
                similarity_score = func.greatest(title_sim, desc_sim, industry_sim, cat_sim, tags_sim)
            else:
                similarity_score = func.greatest(title_sim, desc_sim, industry_sim, tags_sim)

            or_conditions = [similarity_score > 0.12]
            for term in synonyms_list:
                search_term = f"%{term}%"
                or_conditions.extend([
                    Template.title.ilike(search_term),
                    Template.short_description.ilike(search_term),
                    Template.description.ilike(search_term),
                    Template.industry.ilike(search_term),
                    Template.developer_name.ilike(search_term),
                    cast(Template.tags, String).ilike(search_term),
                ])
                if need_category_join:
                    or_conditions.append(Category.name.ilike(search_term))

            if filters.semantic:
                from app.services.search_service import SearchService
                search_service = SearchService(self.db)
                try:
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
                    query = query.where(or_(*or_conditions))
                    score_expr = func.coalesce(similarity_score, 0.0)
                    query = query.order_by(score_expr.desc())
                else:
                    query = query.where(Template.id.in_(matched_ids))
                    from sqlalchemy import case
                    ordering = case(
                        {id_: index for index, id_ in enumerate(matched_ids)},
                        value=Template.id
                    )
                    query = query.order_by(ordering)
            else:
                query = query.where(or_(*or_conditions))
                score_expr = func.coalesce(similarity_score, 0.0)
                query = query.order_by(score_expr.desc())

        # ── Count (snapshot before pagination) ───────────────────────────────
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # ── Sort (skip if semantic already ordered) ───────────────────────────
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
