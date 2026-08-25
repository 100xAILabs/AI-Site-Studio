"""
Dashboard routes — user-facing stats and data aggregation.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.download import Download
from app.models.template import Template

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregated stats for the current user's dashboard."""
    # Purchases count
    purchases = await db.execute(
        select(func.count(Order.id)).where(
            Order.user_id == current_user.id,
            Order.status == OrderStatus.COMPLETED,
        )
    )
    purchase_count = purchases.scalar_one()

    # Downloads count
    downloads = await db.execute(
        select(func.count(Download.id)).where(Download.user_id == current_user.id)
    )
    download_count = downloads.scalar_one()

    # Wishlist count
    from app.models.wishlist import WishlistItem
    wishlist = await db.execute(
        select(func.count(WishlistItem.id)).where(WishlistItem.user_id == current_user.id)
    )
    wishlist_count = wishlist.scalar_one()

    # Favorites count
    from app.models.favorite import Favorite
    favorites = await db.execute(
        select(func.count(Favorite.id)).where(Favorite.user_id == current_user.id)
    )
    favorite_count = favorites.scalar_one()

    # Uploaded / Generated templates count
    from app.models.template import Template
    seller_tmpl = await db.execute(
        select(func.count(Template.id)).where(Template.seller_id == current_user.id)
    )
    uploaded_templates_count = seller_tmpl.scalar_one()

    return {
        "purchases": purchase_count,
        "downloads": download_count,
        "wishlist": wishlist_count,
        "favorites": favorite_count,
        "uploaded_templates": uploaded_templates_count,
    }
