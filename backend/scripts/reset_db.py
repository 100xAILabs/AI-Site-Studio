"""
Database reset script — drops all tables, recreates them, and seeds only categories.
Leaves the database completely clean of templates and users.

Usage:
    cd backend
    python scripts/reset_db.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings
from app.core.database import Base
from app.models.category import Category
from app.models import *  # noqa: F401 — register all ORM models

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

async def reset_db():
    print("[Clean] Dropping and recreating database tables...")
    
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    engine_kwargs = {}
    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        
    engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
    
    async with engine.begin() as conn:
        # Drop all tables
        await conn.run_sync(Base.metadata.drop_all)
        print("  -> Dropped all tables.")
        
        # Recreate tables
        await conn.run_sync(Base.metadata.create_all)
        print("  -> Recreated all tables.")
        
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with SessionLocal() as db:
        print("Seeding categories...")
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
        print(f"  -> Seeded {len(CATEGORIES)} categories.")

    await engine.dispose()
    print("Database reset and category seeding complete!")

if __name__ == "__main__":
    asyncio.run(reset_db())
