"""
Repositories package.
"""

from app.repositories.user_repo import UserRepository
from app.repositories.template_repo import TemplateRepository
from app.repositories.category_repo import CategoryRepository
from app.repositories.review_repo import ReviewRepository
from app.repositories.favorite_repo import FavoriteRepository, WishlistRepository

__all__ = [
    "UserRepository",
    "TemplateRepository",
    "CategoryRepository",
    "ReviewRepository",
    "FavoriteRepository",
    "WishlistRepository",
]
