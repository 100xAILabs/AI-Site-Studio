"""
AI Site Studio — FastAPI Application Entry Point (Active: Gemini 3.5 Models)

This module creates and configures the FastAPI application with:
- CORS middleware
- Global exception handlers
- API v1 router registration
- Health check endpoint
- Lifespan context (DB + Redis startup/shutdown)
"""
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.redis import get_redis_client
from app.api.v1.router import api_router
from app.models.deployment import Deployment, Domain


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup → yield → shutdown."""
    # Startup
    await init_db()
    from app.core.commerce_database import commerce_engine, init_commerce_db
    await init_commerce_db()
    try:
        from app.core.redis import check_redis_health
        health_info = await check_redis_health()
        if health_info.get("status") == "connected":
            app.state.redis = await get_redis_client()
            print(f"[REDIS OK] Site Studio API started | Redis connected ({health_info.get('latency_ms')}ms) | env={settings.ENVIRONMENT}")
        elif health_info.get("status") == "unconfigured":
            app.state.redis = None
            print(f"[REDIS INFO] Site Studio API started | Redis unconfigured (L1 memory cache active) | env={settings.ENVIRONMENT}")
        else:
            app.state.redis = None
            print(f"[REDIS WARN] Site Studio API started | Redis unreachable: {health_info.get('error')} | env={settings.ENVIRONMENT}")
    except Exception as e_redis:
        app.state.redis = None
        print(f"[REDIS WARN] Site Studio API started | Redis check error: {e_redis} | env={settings.ENVIRONMENT}")

    # Verify or auto-spawn Ollama daemon in background with CUDA
    try:
        import httpx, shutil, subprocess
        ollama_alive = False
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                resp = await client.get("http://localhost:11434/api/tags")
                if resp.status_code == 200:
                    ollama_alive = True
        except Exception:
            ollama_alive = False

        if not ollama_alive and shutil.which("ollama"):
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags
            )
            print("🚀 [Ollama Engine] Auto-initialized background service with CUDA GPU acceleration.")
        elif ollama_alive:
            print("⚡ [Ollama Engine] Local AI service connected (CUDA enabled).")
    except Exception as e_ollama:
        print(f"⚠️ [Ollama Engine] Startup check notice: {e_ollama}")

    yield
    # Shutdown
    if getattr(app.state, "redis", None) is not None:
        try:
            await app.state.redis.aclose()
        except Exception:
            pass
    if commerce_engine is not None:
        await commerce_engine.dispose()
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
            allowed_hosts=[
                "aisitestudio.com",
                "*.aisitestudio.com",
                "*.railway.app",
                "*.up.railway.app",
                "onrender.com",
                "*.onrender.com",
                "*.vercel.app",
                "api",
                "localhost",
                "127.0.0.1",
                "0.0.0.0",
                "testserver",
            ],
        )

    @app.middleware("http")
    async def custom_domain_host_middleware(request: Request, call_next):
        # Always let CORS preflight through — OPTIONS must reach CORSMiddleware
        if request.method == "OPTIONS":
            return await call_next(request)

        raw_host = request.headers.get("host", "").split(":")[0].strip().lower()
        platform_hosts = {
            "localhost", "127.0.0.1", "0.0.0.0", "testserver",
            "api",
            # Render.com internal hosts
            "onrender.com",
        }

        path = request.url.path
        # Allow platform calls, API endpoints, docs, and direct asset routes to proceed normally
        if (
            raw_host in platform_hosts
            or raw_host.endswith(".onrender.com")
            or raw_host.endswith(".vercel.app")
            or path.startswith("/api/")
            or path.startswith("/internal/")
            or path.startswith("/docs")
            or path.startswith("/openapi")
            or path.startswith("/static")
            or path.startswith("/sites/")
        ):
            return await call_next(request)

        # Resolve custom domain or tenant subdomain directly to tenant workload
        from app.api.v1.routes.site_router import serve_tenant_workload
        try:
            return await serve_tenant_workload(site_identifier=raw_host, filepath=path.lstrip("/"), request=request)
        except Exception:
            return await call_next(request)

    @app.get("/internal/tls-authorize", include_in_schema=False)
    async def authorize_on_demand_tls(domain: str = ""):
        """Allow Caddy to issue certificates only for platform or verified tenant domains."""
        try:
            clean_domain = domain.strip().lower().rstrip(".").encode("idna").decode("ascii")
        except (UnicodeError, AttributeError):
            return PlainTextResponse("denied", status_code=403)
        if not clean_domain or len(clean_domain) > 253:
            return PlainTextResponse("denied", status_code=403)
        if clean_domain == "aisitestudio.com" or clean_domain.endswith(".aisitestudio.com"):
            return PlainTextResponse("ok", status_code=200)
        base_domain = clean_domain[4:] if clean_domain.startswith("www.") else clean_domain
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Domain.id)
                .join(Deployment, Deployment.id == Domain.deployment_id)
                .where(
                    Domain.domain == base_domain,
                    Domain.verification_status == "verified",
                    Deployment.provider == "local",
                )
                .limit(1)
            )
            if result.scalar_one_or_none():
                return PlainTextResponse("ok", status_code=200)
        return PlainTextResponse("denied", status_code=403)

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

    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None)
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

    @app.api_route("/", methods=["GET", "HEAD"], tags=["Root"])
    async def root() -> dict:
        return {
            "message": "Welcome to Site Studio API",
            "docs": "/docs",
            "health": "/health"
        }

    @app.api_route("/health", methods=["GET", "HEAD"], tags=["Health"])
    async def health_check() -> dict:
        from app.core.redis import check_redis_health
        redis_info = await check_redis_health()
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "redis": redis_info,
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
