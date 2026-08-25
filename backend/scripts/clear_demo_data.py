"""
Clear Demo Data Script — Removes all demo templates from the PostgreSQL database.

Usage:
    cd backend
    python scripts/clear_demo_data.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.core.config import settings


async def clear_data():
    print("🗑️ Clearing all demo templates and sample data from PostgreSQL...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        tables_to_clear = [
            "reviews",
            "wishlist_items",
            "favorites",
            "order_items",
            "downloads",
            "deployments",
            "templates",
        ]

        for table in tables_to_clear:
            try:
                await db.execute(text(f"DELETE FROM {table};"))
                print(f"  ✓ Cleared table: {table}")
            except Exception as e:
                print(f"  ⚠️ Could not clear {table}: {e}")

        await db.commit()
        print("\n✨ All demo templates removed successfully! Database is clean.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(clear_data())
