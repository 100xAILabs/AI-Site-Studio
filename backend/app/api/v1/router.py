"""
Main API v1 router — aggregates all sub-routers.
"""

from fastapi import APIRouter

from app.api.v1.routes import (
    auth, templates, categories, search,
    orders, payment, reviews, favorites,
    wishlist, dashboard, admin, preview, ai, files, follows, deployments,
    payouts, ws, figma, incidents,
)

api_router = APIRouter()

api_router.include_router(auth.router,       prefix="/auth",       tags=["Auth"])
api_router.include_router(templates.router,  prefix="/templates",  tags=["Templates"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(search.router,     prefix="/search",     tags=["Search"])
api_router.include_router(orders.router,     prefix="/orders",     tags=["Orders"])
api_router.include_router(payment.router,    prefix="/payment",    tags=["Payment"])
api_router.include_router(reviews.router,    prefix="/reviews",    tags=["Reviews"])
api_router.include_router(favorites.router,  prefix="/favorites",  tags=["Favorites"])
api_router.include_router(wishlist.router,   prefix="/wishlist",   tags=["Wishlist"])
api_router.include_router(dashboard.router,  prefix="/dashboard",  tags=["Dashboard"])
api_router.include_router(admin.router,      prefix="/admin",      tags=["Admin"])
api_router.include_router(preview.router,    prefix="/preview",    tags=["Preview"])
api_router.include_router(ai.router,         prefix="/ai",         tags=["AI"])
api_router.include_router(files.router,      prefix="/files",      tags=["Files"])
api_router.include_router(follows.router,    prefix="/follows",    tags=["Follows"])
api_router.include_router(deployments.router, prefix="/deployments", tags=["Deployments"])
api_router.include_router(payouts.router,     prefix="/payouts",     tags=["Payouts"])
api_router.include_router(ws.router,          prefix="/ws",          tags=["WebSocket"])
api_router.include_router(figma.router,       prefix="/figma",       tags=["Figma"])
api_router.include_router(incidents.router,   prefix="/incidents",   tags=["Incidents"])
