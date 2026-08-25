"""
Reindexing script — recreates Qdrant templates collection and syncs all database templates.

Usage:
    cd backend
    python scripts/reindex_templates.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.template import Template, TemplateStatus
from app.models.category import Category
from app.services.search_service import SearchService


async def reindex_templates():
    print("[Reindex] Starting template vector database sync...")

    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    engine_kwargs = {}
    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        search_service = SearchService(db)

        # 1. Verify/recreate collection
        print("  -> Verifying/Recreating Qdrant collection...")
        await search_service._ensure_collection()

        # 2. Fetch all templates
        print("  -> Fetching published templates from database...")
        result = await db.execute(
            select(Template)
            .options(selectinload(Template.category))
            .where(Template.status == TemplateStatus.PUBLISHED)
        )
        templates = result.scalars().all()
        print(f"  -> Found {len(templates)} templates to index.")

        # 3. Index each template
        indexed_count = 0
        for t in templates:
            print(f"     * Indexing template: {t.title} (ID: {t.id})...")
            try:
                # Compile metadata payload
                metadata = {
                    "title": t.title,
                    "category": t.category.name if t.category else "",
                    "industry": t.industry or "",
                    "tags": t.tags or [],
                    "framework": t.framework.value if t.framework else "",
                    "color_scheme": t.color_scheme or "",
                    "seo_keywords": t.seo_keywords or []
                }

                
                await search_service.index_template(
                    template_id=t.id,
                    text=t.description or "",
                    metadata=metadata
                )
                indexed_count += 1
            except Exception as e:
                print(f"     [ERROR] Failed to index {t.title}: {e}")

        print(f"  -> Successfully indexed {indexed_count}/{len(templates)} templates in Qdrant.")

    await engine.dispose()
    print("[Reindex] Complete!")


if __name__ == "__main__":
    asyncio.run(reindex_templates())
