import asyncio
import os
import sys

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.template import Template
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Template.id, Template.title, Template.slug, Template.status, Template.seller_id))
        rows = res.all()
        print(f"Total templates in DB: {len(rows)}")
        for r in rows:
            print(f"- ID: {r[0]} | Title: '{r[1]}' | Slug: '{r[2]}' | Status: {r[3]} | Seller: {r[4]}")

if __name__ == "__main__":
    asyncio.run(main())
