"""
Review repository.
"""

import uuid
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewUpdate


class ReviewRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, review_id: uuid.UUID) -> Optional[Review]:
        result = await self.db.execute(
            select(Review)
            .options(selectinload(Review.user), selectinload(Review.template))
            .where(Review.id == review_id)
        )
        return result.scalar_one_or_none()

    async def get_by_template(
        self, template_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Review], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(Review).where(
                Review.template_id == template_id, Review.is_approved == True
            )
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Review)
            .options(selectinload(Review.user), selectinload(Review.template))
            .where(Review.template_id == template_id, Review.is_approved == True)
            .order_by(Review.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_user_review_for_template(
        self, user_id: uuid.UUID, template_id: uuid.UUID
    ) -> Optional[Review]:
        result = await self.db.execute(
            select(Review).where(Review.user_id == user_id, Review.template_id == template_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: uuid.UUID, data: ReviewCreate, is_verified: bool) -> Review:
        review = Review(
            user_id=user_id,
            template_id=data.template_id,
            rating=data.rating,
            title=data.title,
            body=data.body,
            is_verified_purchase=is_verified,
        )
        self.db.add(review)
        await self.db.flush()
        # Re-fetch with eager loading so relationships are available
        # without triggering lazy loads (which fail in async context)
        result = await self.db.execute(
            select(Review)
            .options(selectinload(Review.user), selectinload(Review.template))
            .where(Review.id == review.id)
        )
        return result.scalar_one()

    async def update(self, review: Review, data: ReviewUpdate) -> Review:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(review, field, value)
        await self.db.flush()
        result = await self.db.execute(
            select(Review)
            .options(selectinload(Review.user), selectinload(Review.template))
            .where(Review.id == review.id)
        )
        return result.scalar_one()

    async def delete(self, review: Review) -> None:
        await self.db.delete(review)
        await self.db.flush()

    async def get_rating_stats(self, template_id: uuid.UUID) -> Tuple[float, int]:
        """Returns (avg_rating, total_count) for a template."""
        result = await self.db.execute(
            select(func.avg(Review.rating), func.count(Review.id))
            .where(Review.template_id == template_id, Review.is_approved == True)
        )
        row = result.one()
        avg = float(row[0]) if row[0] else 0.0
        count = row[1] or 0
        return round(avg, 2), count

    async def get_by_seller(
        self, seller_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Review], int]:
        """Get reviews for templates uploaded by a specific seller."""
        from app.models.template import Template
        
        count_result = await self.db.execute(
            select(func.count(Review.id))
            .join(Template)
            .where(Template.seller_id == seller_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Review)
            .join(Template)
            .options(selectinload(Review.user), selectinload(Review.template))
            .where(Template.seller_id == seller_id)
            .order_by(Review.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_all_reviews(
        self, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Review], int]:
        """[Admin] Get all reviews on the platform for moderation."""
        count_result = await self.db.execute(select(func.count(Review.id)))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Review)
            .options(selectinload(Review.user), selectinload(Review.template))
            .order_by(Review.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_by_user(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Review], int]:
        """Get reviews submitted by a specific user (buyer)."""
        count_result = await self.db.execute(
            select(func.count(Review.id)).where(Review.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Review)
            .options(selectinload(Review.user), selectinload(Review.template))
            .where(Review.user_id == user_id)
            .order_by(Review.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total
