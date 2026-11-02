import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.template import Template
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Template))
        templates = res.scalars().all()
        for t in templates:
            print(f"ID: {t.id} | Slug: {t.slug} | Price: {t.price} | IsFree: {t.is_free} | Status: {t.status}")

if __name__ == "__main__":
    asyncio.run(main())
