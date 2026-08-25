"""
Category repository.
"""

import uuid
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, category_id: uuid.UUID) -> Optional[Category]:
        result = await self.db.execute(
            select(Category)
            .options(selectinload(Category.children))
            .where(Category.id == category_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Category]:
        result = await self.db.execute(select(Category).where(Category.slug == slug))
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[Category]:
        """Return all active top-level categories with children eagerly loaded."""
        result = await self.db.execute(
            select(Category)
            .options(selectinload(Category.children))
            .where(Category.is_active == True, Category.parent_id == None)
            .order_by(Category.sort_order.asc(), Category.name.asc())
        )
        return list(result.scalars().all())

    async def create(self, data: CategoryCreate) -> Category:
        category = Category(**data.model_dump())
        self.db.add(category)
        await self.db.flush()
        await self.db.refresh(category)
        return category

    async def update(self, category: Category, data: CategoryUpdate | dict) -> Category:
        update_data = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(category, field, value)
        await self.db.flush()
        await self.db.refresh(category)
        return category

    async def delete(self, category: Category) -> None:
        await self.db.delete(category)
        await self.db.flush()

    async def count_templates(self, category_id: uuid.UUID) -> int:
        from app.models.template import Template, TemplateStatus
        result = await self.db.execute(
            select(func.count())
            .select_from(Template)
            .where(Template.category_id == category_id, Template.status == TemplateStatus.PUBLISHED)
        )
        return result.scalar_one()
