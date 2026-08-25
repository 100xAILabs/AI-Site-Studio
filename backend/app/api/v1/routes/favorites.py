"""
Favorites routes.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.repositories.favorite_repo import FavoriteRepository
from app.schemas.template import TemplateCardResponse
from app.schemas.common import MessageResponse

router = APIRouter()


@router.post("/{template_id}", response_model=MessageResponse)
async def toggle_favorite(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle favorite status for a template. Adds if not favorited, removes if already favorited."""
    repo = FavoriteRepository(db)
    added = await repo.toggle(current_user.id, template_id)
    return MessageResponse(
        message="Added to favorites" if added else "Removed from favorites",
        success=True,
    )


@router.get("", response_model=List[TemplateCardResponse])
async def get_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all templates the current user has favorited."""
    repo = FavoriteRepository(db)
    templates = await repo.get_user_favorites(current_user.id)
    return [TemplateCardResponse.model_validate(t) for t in templates]
