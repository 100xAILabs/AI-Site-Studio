"""
SQLAlchemy async database engine and session factory.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# Create async engine
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine_kwargs = {
    "echo": False,
}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 300,  # Recycle connections every 5 mins to prevent PostgreSQL idle timeouts
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "connect_args": {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "command_timeout": 60,
        },
    })

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def _ensure_db_service_running() -> None:
    """Helper to auto-start Docker services if PostgreSQL is not yet accepting connections."""
    import asyncio
    import os
    import subprocess
    import sys
    from pathlib import Path
    from sqlalchemy import text

    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return  # Connection successful
        except Exception:
            print(f"[Attempt {attempt}/{max_attempts}] Waiting for PostgreSQL connection...")
            if attempt == 1:
                # 1. Attempt launching Docker Desktop on Windows if active process is not detected
                if sys.platform == "win32":
                    try:
                        user_docker = os.path.expandvars(r"%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe")
                        prog_docker = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
                        docker_exe = user_docker if os.path.exists(user_docker) else (prog_docker if os.path.exists(prog_docker) else None)
                        if docker_exe:
                            print(f"[Auto-start] Launching Docker Desktop ({docker_exe})...")
                            subprocess.Popen([docker_exe], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
                    except Exception as err:
                        print(f"Notice: Could not auto-launch Docker Desktop executable: {err}")

                print("[Auto-start] Starting Docker services (postgres, redis)...")
                project_root = Path(__file__).resolve().parents[2]
                for cmd in [
                    ["docker", "compose", "up", "-d", "postgres", "redis"],
                    ["docker-compose", "up", "-d", "postgres", "redis"],
                ]:
                    try:
                        subprocess.run(cmd, cwd=project_root, capture_output=True, timeout=15)
                        break
                    except Exception:
                        continue
            await asyncio.sleep(2.0)


async def init_db() -> None:
    """
    Initialize the database connection and ensure tables exist.
    Also automatically seeds core categories if they don't exist.
    """
    import app.models  # noqa: F401 — register all ORM models
    from app.models.category import Category
    from sqlalchemy import select, text

    await _ensure_db_service_running()

    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        try:
            await conn.execute(text("ALTER TYPE paymentgateway ADD VALUE IF NOT EXISTS 'upi';"))
        except Exception:
            pass

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # Enum type might not exist if using VARCHAR fallback
        
        # Self-healing migration: Ensure deployments table has all multi-tenant columns
        columns_to_add = [
            ("custom_domain", "VARCHAR(255)"),
            ("site_id", "VARCHAR(50)"),
            ("current_version", "VARCHAR(50) DEFAULT 'v1.0'"),
            ("deployment_type", "VARCHAR(50) DEFAULT 'static'"),
            ("health_status", "VARCHAR(50) DEFAULT 'healthy'"),
            ("deployment_path", "VARCHAR(500)"),
            ("env_vars", "JSON"),
            ("is_suspended", "BOOLEAN DEFAULT FALSE"),
        ]
        for col_name, col_type in columns_to_add:
            try:
                if conn.dialect.name == "sqlite":
                    await conn.execute(text(f"ALTER TABLE deployments ADD COLUMN {col_name} {col_type}"))
                else:
                    await conn.execute(text(f"ALTER TABLE deployments ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
            except Exception:
                pass  # Column already exists, safe to ignore

        # Self-healing migration: Ensure users table has location and currency columns
        user_columns_to_add = [
            ("country", "VARCHAR(100)"),
            ("country_code", "VARCHAR(10)"),
            ("city", "VARCHAR(100)"),
            ("currency", "VARCHAR(10) DEFAULT 'USD'"),
            ("detected_ip", "VARCHAR(45)"),
        ]
        for col_name, col_type in user_columns_to_add:
            try:
                if conn.dialect.name == "sqlite":
                    await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                else:
                    await conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
            except Exception:
                pass  # Column already exists, safe to ignore

    print("Database connected and tables verified")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Category).limit(1))
        existing_cat = result.scalar_one_or_none()
        if not existing_cat:
            print("Categories table is empty. Auto-seeding core categories...")
            CATEGORIES = [
                {"name": "Business", "slug": "business", "icon": "Briefcase", "color": "#6366f1", "description": "Professional business and corporate templates"},
                {"name": "E-Commerce", "slug": "ecommerce", "icon": "ShoppingCart", "color": "#8b5cf6", "description": "Online store and shopping templates"},
                {"name": "Portfolio", "slug": "portfolio", "icon": "Palette", "color": "#ec4899", "description": "Creative portfolio and personal brand templates"},
                {"name": "Restaurant", "slug": "restaurant", "icon": "UtensilsCrossed", "color": "#f59e0b", "description": "Food, cafe, and restaurant templates"},
                {"name": "Healthcare", "slug": "healthcare", "icon": "Heart", "color": "#10b981", "description": "Medical, clinic, and wellness templates"},
                {"name": "Real Estate", "slug": "real-estate", "icon": "Home", "color": "#3b82f6", "description": "Property listing and real estate templates"},
                {"name": "Education", "slug": "education", "icon": "GraduationCap", "color": "#14b8a6", "description": "Course, LMS, and education templates"},
                {"name": "Technology", "slug": "technology", "icon": "Cpu", "color": "#f43f5e", "description": "SaaS, startup, and tech product templates"},
                {"name": "Travel", "slug": "travel", "icon": "Plane", "color": "#06b6d4", "description": "Travel agency, hotel, and tourism templates"},
                {"name": "Agency", "slug": "agency", "icon": "Building2", "color": "#a855f7", "description": "Creative agency and studio templates"},
            ]
            for i, cat_data in enumerate(CATEGORIES):
                cat = Category(
                    name=cat_data["name"],
                    slug=cat_data["slug"],
                    icon=cat_data["icon"],
                    color=cat_data["color"],
                    description=cat_data["description"],
                    is_active=True,
                    is_featured=True,
                    sort_order=i,
                )
                db.add(cat)
            await db.commit()
            print(f"Auto-seeded {len(CATEGORIES)} categories on database initialization.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
