"""
Follows routes.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.follow import Follow
from app.schemas.user import UserPublicResponse

router = APIRouter()


@router.get("/status/{seller_id}")
async def get_follow_status(
    seller_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if the current user is following a seller."""
    result = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user.id,
            Follow.seller_id == seller_id
        )
    )
    follow = result.scalar_one_or_none()
    return {"is_following": follow is not None}


@router.post("/toggle/{seller_id}")
async def toggle_follow(
    seller_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle following status for a seller."""
    if current_user.id == seller_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow yourself"
        )

    # Verify that the target is a creator (seller, admin)
    result = await db.execute(select(User).where(User.id == seller_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller profile not found"
        )

    # Check if already following
    result = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user.id,
            Follow.seller_id == seller_id
        )
    )
    existing_follow = result.scalar_one_or_none()

    if existing_follow:
        # Unfollow
        await db.execute(delete(Follow).where(Follow.id == existing_follow.id))
        await db.commit()
        return {"is_following": False}
    else:
        # Follow
        follow = Follow(follower_id=current_user.id, seller_id=seller_id)
        db.add(follow)
        await db.commit()
        return {"is_following": True}


@router.get("/followers", response_model=List[UserPublicResponse])
async def get_followers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the list of profiles following the current seller."""
    if current_user.role.value not in ("seller", "admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creators and administrators can view followers lists"
        )

    result = await db.execute(
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.seller_id == current_user.id)
        .order_by(Follow.created_at.desc())
    )
    followers = result.scalars().all()
    return followers


@router.get("/following", response_model=List[UserPublicResponse])
async def get_following(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the list of sellers/profiles that the current user follows."""
    result = await db.execute(
        select(User)
        .join(Follow, Follow.seller_id == User.id)
        .where(Follow.follower_id == current_user.id)
        .order_by(Follow.created_at.desc())
    )
    following = result.scalars().all()
    return following
