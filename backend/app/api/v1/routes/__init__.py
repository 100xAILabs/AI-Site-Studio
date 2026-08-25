"""
Routes package init — exports all route modules.
"""

from . import (
    auth,
    templates,
    categories,
    search,
    orders,
    payment,
    reviews,
    favorites,
    wishlist,
    dashboard,
    admin,
    preview,
    ai,
    files,
)

__all__ = [
    "auth",
    "templates",
    "categories",
    "search",
    "orders",
    "payment",
    "reviews",
    "favorites",
    "wishlist",
    "dashboard",
    "admin",
    "preview",
    "ai",
    "files",
]
