"""
Search routes — keyword and AI/semantic search with Redis caching.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user_optional
from app.core.redis import CacheKeys, cache_get, cache_set
from app.models.user import User
from app.services.search_service import SearchService
from app.schemas.template import TemplateCardResponse

router = APIRouter()


@router.get("", response_model=List[TemplateCardResponse])
async def search_templates(
    q: str = Query(..., min_length=1, description="Search query"),
    semantic: bool = Query(False, description="Use AI semantic search"),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Search templates with Redis caching for AI semantic embeddings and keyword lookups.

    - **q**: Search query (required)
    - **semantic**: If true, uses OpenAI/Gemini embeddings + Qdrant for semantic similarity search.
    - **semantic=false**: Standard keyword search via PostgreSQL ILIKE.
    """
    service = SearchService(db)

    # For unauthenticated users, cache search queries to save Gemini embedding quota and DB queries
    cache_key = None
    if not current_user:
        cache_key = CacheKeys.search(q, f"{semantic}:{category}:{page}:{page_size}")
        cached = await cache_get(cache_key)
        if cached is not None:
            return [TemplateCardResponse.model_validate(item) for item in cached]

    if semantic:
        results = await service.semantic_search(q, limit=page_size, category_filter=category, user=current_user)
    else:
        results = await service.keyword_search(q, page=page, page_size=page_size)

    if cache_key and results:
        # Cache for 5 minutes (300 seconds)
        await cache_set(
            cache_key,
            [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in results],
            ttl=CacheKeys.CACHE_TTL_MEDIUM,
        )

    return results
