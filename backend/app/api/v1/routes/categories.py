"""
Categories routes — with Redis caching and automatic invalidation on admin edits.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.redis import CacheKeys, cache_get, cache_set, cache_delete
from app.models.category import Category
from app.models.user import User
from app.repositories.category_repo import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse

router = APIRouter()

ALL_STANDARD_CATEGORIES = [
    {"name": "Business", "slug": "business", "icon": "Briefcase", "color": "#6366f1", "description": "Professional business and corporate templates", "sort_order": 1},
    {"name": "SaaS & Technology", "slug": "saas-technology", "icon": "Cpu", "color": "#f43f5e", "description": "SaaS, tech startup, cloud and software templates", "sort_order": 2},
    {"name": "E-Commerce", "slug": "ecommerce", "icon": "ShoppingCart", "color": "#8b5cf6", "description": "Online store, shop and shopping templates", "sort_order": 3},
    {"name": "Restaurant & Food", "slug": "restaurant-food", "icon": "UtensilsCrossed", "color": "#f59e0b", "description": "Food, cafe, dining, bakery and restaurant templates", "sort_order": 4},
    {"name": "Healthcare", "slug": "healthcare", "icon": "Heart", "color": "#10b981", "description": "Medical, clinic, dental and wellness templates", "sort_order": 5},
    {"name": "Real Estate", "slug": "real-estate", "icon": "Home", "color": "#3b82f6", "description": "Property listing, rental, builder and real estate templates", "sort_order": 6},
    {"name": "Education", "slug": "education", "icon": "GraduationCap", "color": "#14b8a6", "description": "School, college, university, LMS and online course templates", "sort_order": 7},
    {"name": "Portfolio", "slug": "portfolio", "icon": "Palette", "color": "#ec4899", "description": "Creative portfolio, CV, resume and personal brand templates", "sort_order": 8},
    {"name": "Creative Agency", "slug": "creative-agency", "icon": "Building2", "color": "#a855f7", "description": "Design studio, branding and digital agency templates", "sort_order": 9},
    {"name": "Events", "slug": "events", "icon": "Calendar", "color": "#e11d48", "description": "Conference, wedding, meetup, festival and event templates", "sort_order": 10},
    {"name": "Travel", "slug": "travel", "icon": "Plane", "color": "#06b6d4", "description": "Travel agency, resort, hotel booking and tourism templates", "sort_order": 11},
    {"name": "Fitness", "slug": "fitness", "icon": "Dumbbell", "color": "#84cc16", "description": "Gym, yoga, personal trainer, sports club and fitness templates", "sort_order": 12},
    {"name": "Beauty", "slug": "beauty", "icon": "Sparkles", "color": "#d946ef", "description": "Salon, spa, cosmetic, skincare and beauty templates", "sort_order": 13},
    {"name": "Legal", "slug": "legal", "icon": "Scale", "color": "#64748b", "description": "Law firm, lawyer, legal advisory and notary templates", "sort_order": 14},
    {"name": "NGO & Charity", "slug": "ngo-charity", "icon": "HeartHandshake", "color": "#059669", "description": "Nonprofit, charity, foundation and volunteer templates", "sort_order": 15},
    {"name": "Automotive", "slug": "automotive", "icon": "Car", "color": "#ea580c", "description": "Car dealer, garage, auto repair and automotive templates", "sort_order": 16},
    {"name": "Blog & Magazine", "slug": "blog-magazine", "icon": "Newspaper", "color": "#4f46e5", "description": "Personal blog, editorial, news and magazine templates", "sort_order": 17},
    {"name": "Gaming", "slug": "gaming", "icon": "Gamepad2", "color": "#9333ea", "description": "eSports, streamer, gaming clan and game studio templates", "sort_order": 18},
    {"name": "Finance", "slug": "finance", "icon": "Coins", "color": "#16a34a", "description": "FinTech, banking, investment, crypto and loan templates", "sort_order": 19},
    {"name": "Entertainment", "slug": "entertainment", "icon": "Film", "color": "#c026d3", "description": "Music, podcast, movies, streaming and media templates", "sort_order": 20},
    {"name": "Landing Pages", "slug": "landing-pages", "icon": "Rocket", "color": "#2563eb", "description": "High-converting product launch and lead capture landing pages", "sort_order": 21},
    {"name": "Dashboards", "slug": "dashboards", "icon": "LayoutDashboard", "color": "#7c3aed", "description": "Admin portals, analytics dashboards and CRM templates", "sort_order": 22},
    {"name": "Documentation", "slug": "documentation", "icon": "BookOpen", "color": "#0284c7", "description": "API docs, developer guides and knowledge base templates", "sort_order": 23},
    {"name": "Authentication", "slug": "authentication", "icon": "Lock", "color": "#475569", "description": "Login, register, account security and auth portal templates", "sort_order": 24},
    {"name": "Marketplace", "slug": "marketplace", "icon": "Store", "color": "#f97316", "description": "Multi-vendor and digital product marketplace templates", "sort_order": 25},
]


@router.get("", response_model=List[CategoryResponse])
async def list_categories(
    response: Response = None,
    db: AsyncSession = Depends(get_db)
):
    """Return all active top-level categories with their children (cached in Redis)."""
    cache_key = CacheKeys.categories()
    cached = await cache_get(cache_key)
    if cached is not None and len(cached) >= len(ALL_STANDARD_CATEGORIES):
        if response:
            response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
        return [CategoryResponse.model_validate(c) for c in cached]

    repo = CategoryRepository(db)
    categories = await repo.get_all_active()

    # Ensure all 25 standard categories are present
    existing_slugs = {c.slug for c in categories}
    created_any = False
    for std_cat in ALL_STANDARD_CATEGORIES:
        if std_cat["slug"] not in existing_slugs:
            new_cat = Category(
                name=std_cat["name"],
                slug=std_cat["slug"],
                icon=std_cat["icon"],
                color=std_cat["color"],
                description=std_cat["description"],
                sort_order=std_cat["sort_order"],
                is_active=True,
                is_featured=True,
            )
            db.add(new_cat)
            created_any = True
    
    if created_any:
        await db.commit()
        categories = await repo.get_all_active()
        await cache_delete(cache_key)

    import asyncio
    async def fetch_cat_data(cat):
        cat_resp = CategoryResponse.model_validate(cat)
        cat_resp.template_count = await repo.count_templates(cat.id)
        return cat_resp

    result = list(await asyncio.gather(*[fetch_cat_data(cat) for cat in categories]))

    await cache_set(
        cache_key,
        [c.model_dump(mode="json") for c in result],
        ttl=CacheKeys.CACHE_TTL_LONG,
    )
    if response:
        response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
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
