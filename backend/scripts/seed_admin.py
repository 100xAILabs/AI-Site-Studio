"""
Seed Admin User Script — creates/resets the default SUPER_ADMIN user.

Usage:
    cd backend
    python scripts/seed_admin.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password


ADMIN_EMAIL = "developer@aisitestudio.com"
ADMIN_PASSWORD = "Admin@123456"


async def seed_admin():
    print(f"[START] Seeding admin user ({ADMIN_EMAIL})...")
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        admin = res.scalar_one_or_none()
        if not admin:
            admin = User(
                email=ADMIN_EMAIL,
                full_name="Super Admin",
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                is_email_verified=True,
            )
            db.add(admin)

        admin.hashed_password = hash_password(ADMIN_PASSWORD)
        admin.role = UserRole.SUPER_ADMIN
        admin.is_active = True
        admin.is_email_verified = True
        await db.commit()
        print(f"[SUCCESS] Admin account ready!\nEmail: {ADMIN_EMAIL}\nPassword: {ADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
