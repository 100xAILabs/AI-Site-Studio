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


async def init_db() -> None:
    """
    Initialize the database connection and ensure tables exist.
    Also automatically seeds core categories if they don't exist.
    """
    import app.models  # noqa: F401 — register all ORM models
    from app.models.category import Category
    from sqlalchemy import select, text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Self-healing migration: Ensure deployments table has custom_domain column
        try:
            if conn.dialect.name == "sqlite":
                await conn.execute(text("ALTER TABLE deployments ADD COLUMN custom_domain VARCHAR(255)"))
            else:
                await conn.execute(text("ALTER TABLE deployments ADD COLUMN IF NOT EXISTS custom_domain VARCHAR(255)"))
        except Exception:
            pass # Column already exists, safe to ignore

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
