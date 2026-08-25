import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.core.database import engine

async def wipe():
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE templates, reviews, wishlist_items, favorites, order_items, downloads CASCADE;"))
    print("Successfully deleted all demo templates!")

if __name__ == "__main__":
    asyncio.run(wipe())
