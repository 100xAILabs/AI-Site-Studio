"""
Wishlist routes.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.repositories.favorite_repo import WishlistRepository
from app.schemas.template import TemplateCardResponse
from app.schemas.common import MessageResponse

router = APIRouter()


@router.post("/{template_id}", response_model=MessageResponse)
async def toggle_wishlist(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle wishlist status for a template."""
    repo = WishlistRepository(db)
    added = await repo.toggle(current_user.id, template_id)
    return MessageResponse(
        message="Added to wishlist" if added else "Removed from wishlist",
        success=True,
    )


@router.get("", response_model=List[TemplateCardResponse])
async def get_wishlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all templates in the current user's wishlist."""
    repo = WishlistRepository(db)
    templates = await repo.get_user_wishlist(current_user.id)
    return [TemplateCardResponse.model_validate(t) for t in templates]
