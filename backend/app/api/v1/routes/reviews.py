"""
Reviews routes.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.repositories.review_repo import ReviewRepository
from app.repositories.template_repo import TemplateRepository
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewResponse
from app.schemas.common import PaginatedResponse
from math import ceil

router = APIRouter()


@router.get("/template/{template_id}", response_model=PaginatedResponse[ReviewResponse])
async def get_template_reviews(
    template_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated reviews for a template."""
    repo = ReviewRepository(db)
    reviews, total = await repo.get_by_template(template_id, page, page_size)
    return PaginatedResponse(
        items=[ReviewResponse.model_validate(r) for r in reviews],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 1,
    )


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    data: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a review for a template. One review per user per template."""
    repo = ReviewRepository(db)

    # Check for duplicate
    existing = await repo.get_user_review_for_template(current_user.id, data.template_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this template",
        )

    # Check if verified purchase
    from app.models.order import Order, OrderItem, OrderStatus
    from sqlalchemy import select

    verified_stmt = (
        select(OrderItem.id)
        .join(Order)
        .where(
            Order.user_id == current_user.id,
            Order.status == OrderStatus.COMPLETED,
            OrderItem.template_id == data.template_id
        )
    )
    verified_res = await db.execute(verified_stmt)
    is_verified = verified_res.first() is not None

    review = await repo.create(current_user.id, data, is_verified)

    # Update template rating
    avg, count = await repo.get_rating_stats(data.template_id)
    template_repo = TemplateRepository(db)
    await template_repo.update_rating(data.template_id, avg, count)

    return ReviewResponse.model_validate(review)


@router.get("/buyer", response_model=PaginatedResponse[ReviewResponse])
async def get_buyer_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated reviews submitted by the current buyer/user."""
    repo = ReviewRepository(db)
    reviews, total = await repo.get_by_user(current_user.id, page, page_size)
    return PaginatedResponse(
        items=[ReviewResponse.model_validate(r) for r in reviews],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 1,
    )


@router.get("/seller", response_model=PaginatedResponse[ReviewResponse])
async def get_seller_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated reviews for templates uploaded by the current seller."""
    if current_user.role.value not in ("seller", "admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only sellers and administrators can view seller reviews",
        )
    repo = ReviewRepository(db)
    reviews, total = await repo.get_by_seller(current_user.id, page, page_size)
    return PaginatedResponse(
        items=[ReviewResponse.model_validate(r) for r in reviews],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 1,
    )


@router.get("/admin", response_model=PaginatedResponse[ReviewResponse])
async def get_admin_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[Admin] Get all reviews on the platform for moderation."""
    if current_user.role.value not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view admin reviews",
        )
    repo = ReviewRepository(db)
    reviews, total = await repo.get_all_reviews(page, page_size)
    return PaginatedResponse(
        items=[ReviewResponse.model_validate(r) for r in reviews],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 1,
    )


@router.patch("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: uuid.UUID,
    data: ReviewUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update your own review."""
    repo = ReviewRepository(db)
    review = await repo.get_by_id(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot edit another user's review")

    review = await repo.update(review, data)

    # Recalculate rating
    avg, count = await repo.get_rating_stats(review.template_id)
    template_repo = TemplateRepository(db)
    await template_repo.update_rating(review.template_id, avg, count)

    return ReviewResponse.model_validate(review)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete your own review."""
    repo = ReviewRepository(db)
    review = await repo.get_by_id(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.user_id != current_user.id and current_user.role.value not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Cannot delete another user's review")

    template_id = review.template_id
    await repo.delete(review)

    avg, count = await repo.get_rating_stats(template_id)
    template_repo = TemplateRepository(db)
    await template_repo.update_rating(template_id, avg, count)


@router.patch("/{review_id}/approve", response_model=ReviewResponse)
async def toggle_review_approval(
    review_id: uuid.UUID,
    is_approved: bool = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[Admin] Toggle review approval status to show/hide it from template listings."""
    if current_user.role.value not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can toggle review approval",
        )
    repo = ReviewRepository(db)
    review = await repo.get_by_id(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    review.is_approved = is_approved
    await db.flush()
    await db.commit()
    
    # Recalculate rating
    avg, count = await repo.get_rating_stats(review.template_id)
    template_repo = TemplateRepository(db)
    await template_repo.update_rating(review.template_id, avg, count)
    
    return ReviewResponse.model_validate(review)
