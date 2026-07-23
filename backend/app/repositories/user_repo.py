"""
User repository — database access layer for User entities.
"""

import uuid
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.google_id == google_id))
        return result.scalar_one_or_none()

    async def get_by_facebook_id(self, facebook_id: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.facebook_id == facebook_id))
        return result.scalar_one_or_none()

    async def get_by_github_id(self, github_id: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.github_id == github_id))
        return result.scalar_one_or_none()

    async def create(self, data: UserCreate) -> User:
        user = User(**data.model_dump(exclude_unset=True))
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update(self, user: User, data: UserUpdate | dict) -> User:
        update_data = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.flush()

    async def list_all(self, skip: int = 0, limit: int = 50) -> List[User]:
        result = await self.db.execute(
            select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        from sqlalchemy import func
        result = await self.db.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def upsert_oauth_user(self, provider: str, provider_id: str, email: str, full_name: Optional[str] = None, avatar_url: Optional[str] = None, role: str = "buyer") -> User:
        """Create or update user from OAuth payload."""
        from app.models.user import UserRole
        
        user = None
        if provider == "google":
            user = await self.get_by_google_id(provider_id)
        elif provider == "facebook":
            user = await self.get_by_facebook_id(provider_id)
        elif provider == "github":
            user = await self.get_by_github_id(provider_id)

        if not user:
            # Fallback to email lookup if user exists but hasn't linked this OAuth provider
            user = await self.get_by_email(email)

        if user:
            # Link account and update details
            if provider == "google":
                user.google_id = provider_id
            elif provider == "facebook":
                user.facebook_id = provider_id
            elif provider == "github":
                user.github_id = provider_id
            
            # Don't overwrite existing user's role on login
            user.email = email
            if full_name:
                user.full_name = full_name
            if avatar_url:
                user.avatar_url = avatar_url
            await self.db.flush()
            await self.db.refresh(user)
        else:
            # Create new user
            base_username = email.split("@")[0]
            unique_username = await self.get_unique_username(base_username)
            kwargs = {
                "email": email,
                "username": unique_username,
                "full_name": full_name,
                "avatar_url": avatar_url,
                "role": UserRole.SELLER if role.lower() == "seller" else UserRole.BUYER
            }
            if provider == "google":
                kwargs["google_id"] = provider_id
            elif provider == "facebook":
                kwargs["facebook_id"] = provider_id
            elif provider == "github":
                kwargs["github_id"] = provider_id
                
            user = User(**kwargs)
            self.db.add(user)
            await self.db.flush()
            await self.db.refresh(user)
        return user

    async def get_unique_username(self, base_username: str) -> str:
        import re
        cleaned = re.sub(r'[^a-zA-Z0-9_]', '', base_username)
        if not cleaned:
            cleaned = "user"
        username = cleaned
        counter = 1
        while True:
            result = await self.db.execute(select(User).where(User.username == username))
            if not result.scalar_one_or_none():
                return username
            username = f"{cleaned}_{counter}"
            counter += 1
