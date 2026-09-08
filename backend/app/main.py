"""
AI Site Studio — FastAPI Application Entry Point (Active: Gemini 3.5 Models)

This module creates and configures the FastAPI application with:
- CORS middleware
- Global exception handlers
- API v1 router registration
- Health check endpoint
- Lifespan context (DB + Redis startup/shutdown)
"""
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.database import init_db
from app.core.redis import get_redis_client
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup → yield → shutdown."""
    # Startup
    await init_db()
    redis = await get_redis_client()
    app.state.redis = redis
    print(f"Site Studio API started | env={settings.ENVIRONMENT}")
    yield
    # Shutdown
    if hasattr(app.state, "redis"):
        await app.state.redis.aclose()
    print("🛑 Site Studio API shutting down")


def create_application() -> FastAPI:
    """Factory function to create the FastAPI app."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered Website Template Marketplace API",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    from starlette.middleware.sessions import SessionMiddleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie="aisitestudio_session",
        same_site="lax",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS_LIST,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.ENVIRONMENT == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*.aisitestudio.com", "localhost"],
        )

    # ── Exception Handlers ────────────────────────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        import pprint
        from fastapi.encoders import jsonable_encoder
        print("--- VALIDATION ERROR ---")
        pprint.pprint(exc.errors())
        print("------------------------")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": jsonable_encoder(exc.errors()),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        import traceback
        print(f"[SERVER EXCEPTION] {traceback.format_exc()}", flush=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    from app.api.v1.routes.site_router import router as site_workload_router
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(site_workload_router)

    from fastapi.staticfiles import StaticFiles
    import os
    os.makedirs("static", exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/", tags=["Root"])
    async def root() -> dict:
        return {
            "message": "Welcome to Site Studio API",
            "docs": "/docs",
            "health": "/health"
        }

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }

    # ── Frontend Soft Navigation Redirects ─────────────────────────────────────
    @app.get("/marketplace", include_in_schema=False)
    @app.get("/marketplace/{path:path}", include_in_schema=False)
    async def redirect_marketplace(request: Request, path: str = ""):
        from fastapi.responses import RedirectResponse
        target = f"{settings.FRONTEND_URL}/marketplace"
        if path:
            target += f"/{path}"
        if request.url.query:
            target += f"?{request.url.query}"
        return RedirectResponse(url=target, status_code=307)

    @app.get("/preview", include_in_schema=False)
    @app.get("/checkout", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    async def redirect_frontend_pages(request: Request):
        from fastapi.responses import RedirectResponse
        target = f"{settings.FRONTEND_URL}{request.url.path}"
        if request.url.query:
            target += f"?{request.url.query}"
        return RedirectResponse(url=target, status_code=307)

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
