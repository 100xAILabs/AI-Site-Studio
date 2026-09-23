"""
Categories routes — with Redis caching and automatic invalidation on admin edits.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.redis import CacheKeys, cache_get, cache_set, cache_delete
from app.models.user import User
from app.repositories.category_repo import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse

router = APIRouter()


@router.get("", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Return all active top-level categories with their children (cached in Redis)."""
    cache_key = CacheKeys.categories()
    cached = await cache_get(cache_key)
    if cached is not None:
        return [CategoryResponse.model_validate(c) for c in cached]

    repo = CategoryRepository(db)
    categories = await repo.get_all_active()
    result = []
    for cat in categories:
        cat_resp = CategoryResponse.model_validate(cat)
        cat_resp.template_count = await repo.count_templates(cat.id)
        result.append(cat_resp)

    await cache_set(
        cache_key,
        [c.model_dump(mode="json") for c in result],
        ttl=CacheKeys.CACHE_TTL_LONG,
    )
    return result


@router.get("/{slug}", response_model=CategoryResponse)
async def get_category(slug: str, db: AsyncSession = Depends(get_db)):
    """Get a single category by slug."""
    repo = CategoryRepository(db)
    cat = await repo.get_by_slug(slug)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return CategoryResponse.model_validate(cat)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Create a category."""
    repo = CategoryRepository(db)
    existing = await repo.get_by_slug(data.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category with slug '{data.slug}' already exists."
        )
    cat = await repo.create(data)
    await db.commit()
    await db.refresh(cat)
    # Invalidate categories cache
    await cache_delete(CacheKeys.categories())
    return CategoryResponse.model_validate(cat)


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Update a category."""
    repo = CategoryRepository(db)
    cat = await repo.get_by_id(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat = await repo.update(cat, data)
    await db.commit()
    await db.refresh(cat)
    # Invalidate categories cache
    await cache_delete(CacheKeys.categories())
    return CategoryResponse.model_validate(cat)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """[Admin] Delete a category."""
    repo = CategoryRepository(db)
    cat = await repo.get_by_id(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    await repo.delete(cat)
    await db.commit()
    # Invalidate categories cache
    await cache_delete(CacheKeys.categories())
