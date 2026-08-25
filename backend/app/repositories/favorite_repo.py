"""
Favorite and Wishlist repositories.
"""

import uuid
from typing import List, Optional

from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.favorite import Favorite
from app.models.wishlist import WishlistItem
from app.models.template import Template


class FavoriteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def toggle(self, user_id: uuid.UUID, template_id: uuid.UUID) -> bool:
        """Toggle favorite. Returns True if added, False if removed."""
        result = await self.db.execute(
            select(Favorite).where(
                Favorite.user_id == user_id, Favorite.template_id == template_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await self.db.delete(existing)
            await self.db.flush()
            return False
        else:
            self.db.add(Favorite(user_id=user_id, template_id=template_id))
            await self.db.flush()
            return True

    async def is_favorited(self, user_id: uuid.UUID, template_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(exists().where(
                Favorite.user_id == user_id, Favorite.template_id == template_id
            ))
        )
        return result.scalar_one()

    async def get_user_favorites(self, user_id: uuid.UUID) -> List[Template]:
        result = await self.db.execute(
            select(Template)
            .join(Favorite, Favorite.template_id == Template.id)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_favorited_ids(self, user_id: uuid.UUID) -> List[uuid.UUID]:
        result = await self.db.execute(
            select(Favorite.template_id).where(Favorite.user_id == user_id)
        )
        return list(result.scalars().all())


class WishlistRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def toggle(self, user_id: uuid.UUID, template_id: uuid.UUID) -> bool:
        """Toggle wishlist. Returns True if added, False if removed."""
        result = await self.db.execute(
            select(WishlistItem).where(
                WishlistItem.user_id == user_id, WishlistItem.template_id == template_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await self.db.delete(existing)
            await self.db.flush()
            return False
        else:
            self.db.add(WishlistItem(user_id=user_id, template_id=template_id))
            await self.db.flush()
            return True

    async def is_wishlisted(self, user_id: uuid.UUID, template_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(exists().where(
                WishlistItem.user_id == user_id, WishlistItem.template_id == template_id
            ))
        )
        return result.scalar_one()

    async def get_user_wishlist(self, user_id: uuid.UUID) -> List[Template]:
        result = await self.db.execute(
            select(Template)
            .join(WishlistItem, WishlistItem.template_id == Template.id)
            .where(WishlistItem.user_id == user_id)
            .order_by(WishlistItem.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_wishlisted_ids(self, user_id: uuid.UUID) -> List[uuid.UUID]:
        result = await self.db.execute(
            select(WishlistItem.template_id).where(WishlistItem.user_id == user_id)
        )
        return list(result.scalars().all())
