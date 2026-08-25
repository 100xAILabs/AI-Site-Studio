"""
Search routes — keyword and AI/semantic search.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user_optional
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
    Search templates.

    - **q**: Search query (required)
    - **semantic**: If true, uses OpenAI/Gemini embeddings + Qdrant for semantic similarity search.
      Example: "I need a website for a coffee shop" → returns cafe/restaurant templates.
    - **semantic=false**: Standard keyword search via PostgreSQL ILIKE.
    """
    service = SearchService(db)

    if semantic:
        return await service.semantic_search(q, limit=page_size, category_filter=category, user=current_user)
    else:
        return await service.keyword_search(q, page=page, page_size=page_size)
